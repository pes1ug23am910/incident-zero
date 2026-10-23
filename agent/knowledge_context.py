"""Optional retrieval plumbing. Hints never enter the evidence registry."""
from __future__ import annotations

from copy import deepcopy
import json
import os
import sqlite3

from jsonschema import validate, ValidationError

from .evidence import data_projection
from .llm_router import ModelUnavailable, now, load_env
from .prompts import KNOWLEDGE_SYSTEM, PLANNER_SYSTEM, KNOWLEDGE_PROMPT_SHA256


PLAN_FUNCTION = {'type': 'function', 'function': {
    'name': 'select_remediation',
    'description': 'Select a cited runbook remediation for each supported cause, or abstain.',
    'parameters': {'type': 'object', 'properties': {
        'selections': {'type': 'array', 'maxItems': 8, 'items': {
            'type': 'object', 'properties': {
                'citation_id': {'type': 'string'},
                'action_type': {'type': 'string', 'enum': ['toggle_flag', 'restart_service', 'throttle_load', 'escalate']},
                'target': {'type': 'string'},
            }, 'required': ['citation_id', 'action_type', 'target'], 'additionalProperties': False}},
    }, 'required': ['selections'], 'additionalProperties': False}}}


def enabled():
    return os.environ.get('INCIDENT_ZERO_KNOWLEDGE') == '1'


def index():
    from knowledge import KnowledgeIndex
    return KnowledgeIndex(os.environ.get('INCIDENT_ZERO_KNOWLEDGE_INDEX'))


def _search(query, *, section=None):
    try:
        result = index().search(query, section=section)
        return {**result, 'limitations': result.get('warnings', [])}
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        return {'mode': 'unavailable', 'runbook_refs': [], 'memory_refs': [], 'service_refs': [],
                'limitations': ['Knowledge retrieval unavailable: ' + type(exc).__name__]}


def _unique(refs):
    return list({ref['id']: ref for ref in refs}.values())


def retrieve_context(state):
    from memory import fingerprint
    # Metadata slugs, paths and operator inputs are deliberately absent.
    query = fingerprint({'alert': state['alert'], 'health': state.get('health', {}),
                         'symptom_services': state.get('symptom_services', []),
                         'findings': state.get('findings', [])})
    result = _search(query, section='investigation')
    block = {key: result[key] for key in ('mode', 'runbook_refs', 'memory_refs', 'service_refs', 'limitations')}
    block.update(enabled=True, queries=[query])
    return {'knowledge_context': block, 'audit': [{'node': 'retrieve_context', 'ts': now()}]}


def investigation_messages(context, state, system):
    """Keep the disabled path byte-for-byte compatible with the earlier prompt."""
    context = dict(context)
    if enabled() and state.get('knowledge_context', {}).get('enabled'):
        system += '\n' + KNOWLEDGE_SYSTEM
        context['relevant_runbooks_and_prior_incidents'] = state['knowledge_context']
    # Escape delimiters inside JSON strings so a retrieved document cannot close
    # the untrusted-data block and impersonate a new prompt section.
    payload = json.dumps(data_projection(context), separators=(',', ':'))
    if enabled() and state.get('knowledge_context', {}).get('enabled'):
        payload = payload.replace('<', '\\u003c').replace('>', '\\u003e')
    return [{'role': 'system', 'content': system},
            {'role': 'user', 'content': '<telemetry>\n' + payload + '\n</telemetry>'}]


def attach_context(report, state):
    block = state.get('knowledge_context')
    if not enabled() or not block or not block.get('enabled'):
        return report
    report = deepcopy(report)
    report['knowledge_consulted'] = deepcopy(block)
    report['runbook_refs'] = deepcopy(block['runbook_refs'])
    report['memory_refs'] = deepcopy(block['memory_refs'])
    report['limitations'].extend(block.get('limitations', []))
    report['agent']['prompt_sha256'] = KNOWLEDGE_PROMPT_SHA256
    return report


def prepare_plan(report, router):
    """Retrieve again from validated labels, then request a bounded cited plan."""
    if not enabled() or not report.get('knowledge_consulted', {}).get('enabled'):
        return report, None
    report = deepcopy(report)
    block = report['knowledge_consulted']
    causes = report.get('root_causes', [report['root_cause']])
    query = ' '.join(f"{c['component']} {c.get('category', '')}" for c in causes)
    result = _search(query, section='remediation')
    block['queries'].append(query)
    for key in ('runbook_refs', 'memory_refs', 'service_refs'):
        block[key] = _unique(block.get(key, []) + result[key])
    block['limitations'].extend(result['limitations'])
    report['runbook_refs'] = deepcopy(block['runbook_refs'])
    report['memory_refs'] = deepcopy(block['memory_refs'])
    report['limitations'].extend(result['limitations'])
    actual = {(c['component'], c['category']) for c in causes if c.get('confidence', 0) >= .6}
    for ref in block['memory_refs']:
        hint = (ref.get('component'), ref.get('category'))
        if actual and hint[0] and hint not in actual:
            report['limitations'].append(
                f"Evidence overrides memory {ref['id']}: its {hint[0]} / {hint[1]} hint "
                'does not match the current evidence-backed diagnosis; it was not used as evidence.')
    if report.get('status') in ('no_incident', 'needs_human', 'aborted') or report.get('impact', {}).get('tier') == 3 or not result['runbook_refs']:
        return report, []
    payload = json.dumps(data_projection({'validated_causes': causes,
        'relevant_runbooks_and_prior_incidents': block}), separators=(',', ':'))
    messages = [{'role': 'system', 'content': PLANNER_SYSTEM}, {'role': 'user',
        'content': '<telemetry>\n' + payload.replace('<', '\\u003c').replace('>', '\\u003e') + '\n</telemetry>'}]
    try:
        decision = router.complete(messages, [PLAN_FUNCTION], purpose='plan')
        if decision['name'] != 'select_remediation':
            raise ValueError('Unexpected planner function')
        validate(decision['arguments'], PLAN_FUNCTION['function']['parameters'])
        return report, decision['arguments']['selections']
    except (ModelUnavailable, ValueError, KeyError, TypeError, ValidationError) as exc:
        report['limitations'].append('Knowledge planner unavailable or invalid (' + type(exc).__name__ +
                                    '); policy retained the evidence-based proposal.')
        return report, []


def remember(state, *, secrets=()):
    """The terminal node validates again using retained evidence, never live I/O."""
    from memory import MemoryStore
    from tools.evidence import load_snapshot, snapshot_path
    report = state['report']
    if not enabled() or not report.get('knowledge_consulted', {}).get('enabled'):
        return {}
    def resolve(identifier):
        return load_snapshot(snapshot_path(report['run_id'], identifier), identifier)
    try:
        if not secrets:
            secrets = tuple(value for name, value in load_env().items()
                            if value and any(word in name.upper() for word in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET')))
        store = MemoryStore(root=os.environ.get('INCIDENT_ZERO_MEMORY_DIR'), index=index(), resolver=resolve, secrets=secrets)
        store.remember(report, report_path=state.get('report_path'))
        return {'audit': [{'node': 'remember', 'ts': now()}]}
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        report = deepcopy(report)
        report['limitations'].append('Incident memory was not written: ' + type(exc).__name__)
        return {'report': report, 'audit': [{'node': 'remember', 'ts': now(), 'stored': False}]}


def wire(graph, end, *, secrets=()):
    """Exactly two optional nodes, shared by diagnosis and response graphs."""
    if enabled():
        graph.add_node('retrieve_context', retrieve_context)
        graph.add_node('remember', lambda state: remember(state, secrets=secrets))
        graph.add_edge('observe', 'retrieve_context')
        graph.add_edge('retrieve_context', 'investigate')
        graph.add_edge('report', 'remember')
        graph.add_edge('remember', end)
    else:
        graph.add_edge('observe', 'investigate')
        graph.add_edge('report', end)
