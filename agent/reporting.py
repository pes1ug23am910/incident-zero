"""Construct a schema report from validated state and preserve its evidence."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
from detect.core import anomalies
from reports.render import render_report
from tools.evidence import snapshot_path
from .llm_router import now, scrub
from .policy import SERVICES
from .prompts import PROMPT_SHA256

ROOT = Path(__file__).resolve().parents[1]


def build_report(state, model_summary, elapsed):
    evidence = state.get('evidence', {})
    health = state.get('health', {})
    stopped = state.get('stopped_because', 'budget')
    symptoms = []
    for anomaly in anomalies(health):
        if anomaly['service'] not in SERVICES:
            continue
        ids = [i for i in anomaly.get('evidence_ids', []) if i in evidence and evidence[i]['strength'] >= .5][:3]
        symptoms.append({'service': anomaly['service'], 'signal': anomaly['signal'],
                         'observed': str(anomaly['observed']), 'evidence_ids': ids})
    for service in state.get('symptom_services', []):
        if not any(s['service'] == service for s in symptoms):
            ids = [i for i,e in evidence.items() if service in e['services'] and e['strength'] >= .5][:2]
            symptoms.append({'service': service, 'signal': 'alert_context', 'observed': 'Anomaly present in the detector alert; re-evaluated during investigation.', 'evidence_ids': ids})
    if not symptoms:
        row = next((r for r in health.get('data', []) if r['service'] == 'frontend'), {})
        ids = [i for i, e in evidence.items() if 'frontend' in e['services'] and (i.startswith('metric:') or ':Status=' in i)][:3]
        symptoms = [{'service': 'frontend', 'signal': 'observed_health', 'observed': json.dumps(row), 'evidence_ids': ids}]
    causes = state.get('hypotheses', [])
    if not causes:
        component = state['alert'].get('service', 'frontend')
        if component not in SERVICES:
            component = 'frontend'
        ids = [i for i, e in evidence.items() if component in e['services']][:3]
        if stopped == 'error':
            cause_text = 'Diagnosis failed before a cause was established; collected observations require human review.'
        else:
            cause_text = 'No active incident established in the observed window.' if state.get('clean') else 'The available observations do not establish a cause.'
        confidence = 0.0 if stopped == 'error' else .3
        causes = [{'component': component, 'category': 'unknown',
                   'cause': cause_text,
                   'confidence_model': confidence, 'confidence_evidence': .3, 'confidence': confidence,
                   'evidence_ids': ids, 'explains_symptoms': [],
                   'alternatives_considered': ['Missing, delayed or incomplete telemetry can hide an incident.']}]
    referenced = {i for cause in causes for i in cause['evidence_ids']}
    referenced.update(i for symptom in symptoms for i in symptom['evidence_ids'])
    investigation = []
    for finding in state.get('findings', []):
        result = finding['result']
        ids = [i for i in result['evidence_ids'] if i in referenced]
        if not ids:
            ids = [i for i in result['evidence_ids'] if i in evidence][:1]
        referenced.update(ids)
        if finding['tool'] == 'health_table':
            summary = f"Observed {len(result['data'])} service rows; {len(symptoms)} symptom entries."
        else:
            summary = json.dumps(result.get('data', []), ensure_ascii=False)[:1500] or 'No records returned.'
        investigation.append({'step': finding['step'], 'tool': finding['tool'],
                              'query': json.dumps(finding['arguments']), 'why': finding['why'],
                              'finding': summary, 'evidence_ids': ids})
    rows = []
    for identifier in sorted(referenced):
        record = evidence[identifier]
        rows.append({'id': identifier, 'source': record['source'],
                     'summary': json.dumps(record['data'], ensure_ascii=False)[:900],
                     'raw_ref': f"python -m tools.resolve '{identifier}' --run-dir '{state['run_id']}'"})
    status = 'aborted' if state.get('stop_signal') else 'needs_human' if stopped == 'error' else 'no_incident' if state.get('clean') and stopped=='confident' else 'diagnosed' if all(c['confidence'] >= .6 for c in causes) else 'needs_human'
    limitations = ['Actions are proposals only. No approval, execution or recovery was performed.',
                   'Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.',
                   'Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.']
    if state.get('unexplained') and status != 'no_incident':
        limitations.append('Unexplained symptom services: ' + ', '.join(state['unexplained']))
    if state.get('validation_error'):
        limitations.append('Structured decision limitation: ' + state['validation_error'])
    escalation = None
    if stopped == 'error':
        escalation = 'Diagnosis stopped on an error. Review the retained observations and resolve the reported decision failure before rerunning.'
    elif status in ('needs_human', 'aborted'):
        escalation = 'Inspect the unresolved observations and collect fresh component/dependency evidence.'
    alert = {k: state['alert'][k] for k in ('signal','service','observed','threshold','window_s','baseline') if k in state['alert']}
    return {'schema_version': '1.0', 'incident_id': state['incident_id'], 'run_id': state['run_id'],
            'detected_at': state['alert'].get('detected_at', now()), 'diagnosed_at': now(), 'resolved_at': None,
            'alert': alert, 'symptoms': symptoms, 'investigation': investigation,
            'root_cause': causes[0], 'root_causes': causes, 'evidence': rows,
            'proposed_action': None, 'proposed_actions': [],
            'approval': {'required': True, 'requested_at': None, 'approved': None, 'approved_by': None, 'approved_at': None, 'token': None},
            'action': {'executed': False, 'started_at': None, 'finished_at': None, 'action_log_ref': None},
            'verification': {'checked_at': None, 'signal': alert['signal'], 'before': None, 'after': None, 'recovered': None, 'rolled_back': False},
            'status': status, 'escalation_note': escalation,
            'prevention': 'Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.',
            'limitations': limitations, 'agent': {**model_summary, 'tool_calls': state.get('tool_calls_used',0),
                'elapsed_s': round(elapsed, 3), 'stopped_because': stopped, 'prompt_sha256': PROMPT_SHA256, 'framework': 'LangGraph StateGraph + SqliteSaver'}}


def write_bundle(report, alert, run_dir, output, secrets=(), external_schema=None):
    output, run_dir = Path(output), Path(run_dir)
    bundle = output.parent
    bundle.mkdir(parents=True, exist_ok=True)
    safe_report = scrub(report, secrets)
    output.write_text(json.dumps(safe_report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    output.with_suffix('.md').write_text(render_report(safe_report), encoding='utf-8')
    # Operator metadata never enters the model prompt; retain the alert for auditing.
    safe_alert = dict(alert)
    safe_alert['evidence_ids'] = [i for i in alert.get('evidence_ids',[]) if not i.startswith('container:') or i.split(':')[1] in SERVICES]
    safe_alert['anomalies'] = [a for a in alert.get('anomalies',[]) if a.get('service') in SERVICES]
    (bundle / 'alert.json').write_text(json.dumps(scrub(safe_alert,secrets),indent=2)+'\n',encoding='utf-8')
    (bundle / 'action-log.jsonl').write_text('',encoding='utf-8')
    for name in ('llm.jsonl','graph_updates.jsonl'):
        source = run_dir / name
        (bundle / name).write_text(scrub(source.read_text(encoding='utf-8'),secrets) if source.exists() else '',encoding='utf-8')
    (bundle / 'evidence').mkdir(exist_ok=True)
    for path in (run_dir/'evidence').glob('*.json'):
        payload = json.loads(path.read_text(encoding='utf-8'))
        identifier = payload['id']
        if identifier.startswith(('container:','dlog:')) and identifier.split(':')[1] not in SERVICES:
            continue
        shutil.copy2(path,bundle/'evidence'/path.name)
    if external_schema:
        from schema.adapter import to_external
        from jsonschema import validate
        target = json.loads(Path(external_schema).read_text(encoding='utf-8'))
        external = to_external(safe_report,target)
        validate(external,target)
        (bundle/'report.external.json').write_text(json.dumps(external,indent=2)+'\n',encoding='utf-8')
    return output
