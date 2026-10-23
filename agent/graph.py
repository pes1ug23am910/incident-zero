"""Checkpointed observe-investigate-diagnose-policy graph, with no executor."""
from __future__ import annotations
import json
import time
from pathlib import Path
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from jsonschema.exceptions import ValidationError as JSONValidationError
import tools
from detect.core import anomalies
from .state import IncidentState
from .policy import SERVICES, propose
from .risk import assess
from .contracts import FUNCTIONS
from .evidence import registry, validate_causes, uncovered, data_projection, PlantedEvidence
from .llm_router import now, ModelUnavailable
from .prompts import SYSTEM, PROMPT_SHA256

ROOT = Path(__file__).resolve().parents[1]


def route_investigate(state):
    if state.get('stop_signal') or state.get('done') or state.get('stopped_because') in ('budget', 'error'):
        return 'diagnose'
    return 'investigate'


def route_proposal(state):
    return 'dry_run' if state['report'].get('proposed_actions') else 'report'


class Investigation:
    def __init__(self, run_dir, router, max_tools=12, toolset=None):
        self.run_dir = Path(run_dir)
        self.router = router
        self.max_tools = min(max(int(max_tools), 1), 12)
        self.toolset = toolset or {name: getattr(tools, name) for name in
                                  ('health_table', 'get_traces', 'get_logs', 'get_metrics', 'get_container_health', 'get_deploy_history')}
        self.started = time.monotonic()

    def read(self, name, arguments, why, step):
        result = self.toolset[name](**arguments, run_dir=self.run_dir)
        # The full immutable returned envelope is the offline replay fixture.
        with (self.run_dir / 'tools.jsonl').open('a', encoding='utf-8') as output:
            output.write(json.dumps({'step': step, 'tool': name, 'arguments': arguments, 'why': why, 'result': result}) + '\n')
        evidence = registry(result)
        data = result.get('data', [])
        if name == 'health_table':
            data = [row for row in data if row.get('service') in SERVICES]
        compact = {'tool': name, 'data': data, 'evidence_ids': list(evidence)}
        if result.get('error'):
            compact['error'] = result['error']
        for key in ('warnings', 'warning', 'telemetry_available', 'truncated'):
            if key in result:
                compact[key] = result[key]
        if name == 'get_metrics':
            compact['data'] = [{**s, 'values': s['values'][::max(1,len(s['values'])//8)][:10]} for s in data]
        finding = {'step': step, 'tool': name, 'arguments': arguments, 'why': why, 'result': compact}
        return finding, evidence, result

    def observe(self, state):
        finding, evidence, result = self.read('health_table', {'lookback_s': 120}, 'Locate every service anomaly before selecting a focused read.', 1)
        active = anomalies(result)
        # Resource limits remain visible even below the detector threshold.
        services = {a['service'] for a in active if a['service'] in SERVICES}
        if state['alert'].get('signal') != 'no_alert' and state['alert'].get('service') in SERVICES:
            services.add(state['alert']['service'])
            services.update(a['service'] for a in state['alert'].get('anomalies', []) if a['service'] in SERVICES)
        services = sorted(services)
        clean = not services and result.get('telemetry_available', False) and any(r.get('service') == 'frontend' and (r.get('rps') or 0) > 0 for r in result['data'])
        return {'findings': [finding], 'evidence': evidence, 'health': result, 'tool_calls_used': 1,
                'unexplained': services, 'symptom_services': services, 'hypotheses': [], 'seen_calls': [], 'done': False, 'clean': clean,
                'audit': [{'node': 'observe', 'ts': now()}]}

    def investigate(self, state):
        if (ROOT / 'STOP').exists():
            return {'stop_signal': True, 'stopped_because': 'stop_signal'}
        if state['tool_calls_used'] >= self.max_tools:
            return {'stopped_because': 'budget'}
        safe_alert = {key: state['alert'].get(key) for key in ('signal', 'service', 'observed', 'threshold', 'window_s', 'baseline')}
        context = {'alert': safe_alert, 'findings': state['findings'], 'current_hypotheses': state.get('hypotheses', []),
                   'unexplained_services': state['unexplained'], 'tool_calls_left': self.max_tools-state['tool_calls_used'],
                   'last_validation_error': state.get('validation_error', '')}
        messages = [{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': '<telemetry>\n' + json.dumps(data_projection(context), separators=(',', ':')) + '\n</telemetry>'}]
        try:
            functions = [f for f in FUNCTIONS if not state.get('finish_blocked') or f['function']['name'] != 'finish']
            decision = self.router.complete(messages, functions)
            name, args = decision['name'], dict(decision['arguments'])
            why = args.pop('reason')
            raw_causes = args.pop('hypotheses')
            all_symptoms = set(state.get('symptom_services', [])) or {a['service'] for a in anomalies(state['health']) if a['service'] in SERVICES}
            if not all_symptoms:
                all_symptoms = {state['alert'].get('service', 'frontend')}
            causes = validate_causes(raw_causes, state['evidence'], all_symptoms)
            unexplained = uncovered(causes, all_symptoms)
            update = {'hypotheses': causes, 'unexplained': unexplained, 'validation_error': '',
                      'audit': [{'node': 'investigate', 'ts': now(), 'choice': name, 'why': why}]}
            if name == 'finish':
                clean = bool(args.get('no_incident')) and state['clean'] and any(f['tool']=='get_traces' and f['result']['data'] and not any(t.get('first_error_span') for t in f['result']['data']) for f in state['findings'])
                if not clean and (not causes or unexplained or any(c['confidence'] < .75 for c in causes)):
                    return {**update, 'done': False, 'finish_blocked': True,
                            'validation_error': 'Finish refused: gather another independent positive source for each cause and investigate uncovered services: ' + ', '.join(unexplained)}
                update.update(done=True, clean=clean, stopped_because='confident' if (clean or causes and not unexplained) else 'budget')
                return update
            if name not in self.toolset or name == 'health_table':
                raise ValueError('Unknown investigation tool')
            # Only declared arguments are ever dispatched to a read tool.
            schema = next(f['function']['parameters'] for f in FUNCTIONS if f['function']['name']==name)
            from jsonschema import validate
            validate(decision['arguments'], schema)
            if name in ('get_traces', 'get_logs'):
                args.setdefault('lookback_s', 120)
            if name == 'get_traces':
                args.setdefault('limit', 5)
            identity = json.dumps([name, args], sort_keys=True)
            if identity in state.get('seen_calls', []):
                return {**update, 'done': True, 'stopped_because': 'budget', 'validation_error': 'Repeated identical read stopped for lack of progress.'}
            finding, evidence, result = self.read(name, args, why, state['tool_calls_used'] + 1)
            update.update(findings=[finding], evidence=evidence, tool_calls_used=state['tool_calls_used'] + 1, finish_blocked=False,
                          seen_calls=state.get('seen_calls', []) + [identity], last_call=identity)
            return update
        except (PlantedEvidence, ValueError, TypeError, KeyError, JSONValidationError) as exc:
            # One repair request, then abstain without admitting fabricated claims.
            if state.get('validation_error'):
                return {'done': True, 'stopped_because': 'error', 'validation_error': str(exc)[:300]}
            return {'validation_error': str(exc)[:300], 'audit': [{'node': 'validation_repair', 'ts': now()}]}
        except ModelUnavailable as exc:
            return {'done': True, 'stopped_because': 'error', 'validation_error': str(exc)}

    def diagnose(self, state):
        from .reporting import build_report
        report = build_report(state, self.router.summary(), time.monotonic()-self.started)
        return {'report': report, 'status': report['status'], 'audit': [{'node': 'diagnose', 'ts': now()}]}

    def assess_risk(self, state):
        report = dict(state['report'])
        report['impact'] = assess(report)
        return {'report': report, 'impact': report['impact']}

    def propose(self, state):
        report = propose(state['report'])
        return {'report': report, 'proposal': report['proposed_actions'], 'status': report['status']}


def dry_run(state):
    # This is a local preview only. The next session supplies authoritative preconditions.
    return {'dry_run': {'available': False, 'plans': state['proposal'],
                        'note': 'Action API is not built in this session; no execution or authoritative dry run occurred.'}}


def approval(state):
    decision = interrupt({'run_id': state['run_id'], 'tier': state['impact']['tier'],
                          'diagnosis': state['report']['root_causes'], 'evidence': state['report']['evidence'],
                          'plan': state['dry_run'], 'execution_available': False})
    return {'decision': decision}


def execute(state):
    # Deliberately fail closed: no transport or mutation code exists in this build.
    report = dict(state['report'])
    report['status'] = 'needs_human'
    report['escalation_note'] = 'Execution is unavailable in this brain-only build. No action occurred.'
    return {'report': report, 'status': 'needs_human'}


def verify(state):
    return {'verification': state['report']['verification']}


def build_graph(investigation, checkpointer):
    graph = StateGraph(IncidentState)
    for name in ('observe', 'investigate', 'diagnose', 'assess_risk', 'propose'):
        graph.add_node(name, getattr(investigation, name))
    for name, node in {'dry_run': dry_run, 'approval': approval, 'execute': execute,
                       'verify': verify, 'report': lambda state: {}}.items():
        graph.add_node(name, node)
    graph.add_edge(START, 'observe')
    graph.add_edge('observe', 'investigate')
    graph.add_conditional_edges('investigate', route_investigate, {'investigate': 'investigate', 'diagnose': 'diagnose'})
    graph.add_edge('diagnose', 'assess_risk')
    graph.add_edge('assess_risk', 'propose')
    graph.add_conditional_edges('propose', route_proposal, {'dry_run': 'dry_run', 'report': 'report'})
    graph.add_edge('dry_run', 'approval')
    graph.add_edge('approval', 'execute')
    graph.add_edge('execute', 'verify')
    graph.add_edge('verify', 'report')
    graph.add_edge('report', END)
    return graph.compile(checkpointer=checkpointer)
