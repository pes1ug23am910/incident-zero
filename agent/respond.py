"""Continue the diagnosis thread through approval, action and verification.

Merge interface: import build_graph from this module in agent.run. Existing
brain checkpoints at approval are supported without editing that module.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from .state import IncidentState
from .graph import route_investigate, route_proposal
from action_api.service import ActionService
from action_api.safety import Blocked, digest, now

ROOT = Path(__file__).resolve().parents[1]


class ResponseState(IncidentState, total=False):
    action_index: int
    action_results: list[dict]
    execution_result: dict
    response_error: dict


def config_for(run_id):
    return {'configurable': {'thread_id': run_id}, 'recursion_limit': 60}


class Response:
    def __init__(self, service):
        self.api = service

    def dry_run(self, state):
        index = state.get('action_index', 0)
        try:
            self.api.bind_alert(state['report'], state.get('alert'))
            preview = self.api.dry_run(state['report']['proposed_actions'][index], state['report'])
            return {'dry_run': preview, 'response_error': {}}
        except Blocked as exc:
            return {'response_error': exc.payload(), 'dry_run': {}}

    def approval(self, state):
        decision = interrupt({'run_id': state['run_id'], 'tier': state['report']['impact']['tier'],
                              'diagnosis': state['report']['root_causes'], 'evidence': state['report']['evidence'],
                              'plan': state['dry_run'], 'execution_available': True})
        return {'decision': decision}

    def execute(self, state):
        decision = state['decision']
        if decision.get('decision') != 'approve':
            return {'execution_result': {'rejected': True}, 'response_error': {}}
        index = state.get('action_index', 0)
        key = f"{state['run_id']}:{index}:{digest(decision.get('token'))[:16]}"
        try:
            result = self.api.execute(state['report']['proposed_actions'][index], state['report'], decision.get('token'), key)
            return {'execution_result': result, 'response_error': {}}
        except Blocked as exc:
            return {'execution_result': {}, 'response_error': exc.payload()}

    def verify(self, state):
        result = state.get('execution_result', {})
        if not result.get('executed'):
            return {}
        verification = self.api.verify(result['idempotency_key'], progress=lambda p: print(json.dumps({
            'verify_elapsed_s': p['elapsed_s'], 'recovery_sample': p['qualified_recovery']}), flush=True))
        return {'verification': verification}

    def record_action(self, state):
        result = {'index': state.get('action_index', 0), 'decision': state.get('decision', {}),
                  'execution': state.get('execution_result', {}), 'verification': state.get('verification', {}),
                  'error': state.get('response_error', {})}
        return {'action_results': state.get('action_results', []) + [result],
                'action_index': state.get('action_index', 0) + 1,
                'decision': {}, 'execution_result': {}, 'verification': {}}

    def report(self, state):
        report = deepcopy(state['report'])
        results = state.get('action_results', [])
        for result in results:
            report['proposed_actions'][result['index']]['dry_run']['performed'] = True
        report['proposed_action'] = report['proposed_actions'][0] if report['proposed_actions'] else None
        if not results:
            if state.get('response_error'):
                report['status'] = 'aborted' if self.api.stop_path.exists() else 'needs_human'
                report['escalation_note'] = 'Action blocked: ' + json.dumps(state['response_error'])
            return {'report': report, 'status': report['status']}
        executed = [r for r in results if r['execution'].get('executed')]
        chosen = executed[-1] if executed else results[-1]
        decision = chosen['decision']
        approved = decision.get('decision') == 'approve'
        report['approval'] = {'required': True, 'requested_at': decision.get('requested_at', now()),
                              'approved': approved, 'approved_by': decision.get('approved_by'),
                              'approved_at': decision.get('approved_at') if approved else None,
                              'token': 'sha256:' + digest(decision['token']) if approved else None}
        if executed:
            report['action'] = {k: chosen['execution'][k] for k in ('executed', 'started_at', 'finished_at', 'action_log_ref')}
            report['verification'] = chosen['verification']
        all_recovered = len(executed) == len(report['proposed_actions']) and all(r['verification'].get('recovered') for r in executed)
        if self.api.stop_path.exists():
            report['status'] = 'aborted'
        elif all_recovered:
            report['status'] = 'fixed'
            report['resolved_at'] = now()
        elif report['verification'].get('rolled_back'):
            report['status'] = 'rolled_back'
        else:
            report['status'] = 'needs_human'
        report['escalation_note'] = None if all_recovered else 'Operator review required: rejected, blocked, unverified or rolled back remediation. Inspect action history and all alert signals before a new attempt.'
        report['action_history'] = []
        for item in results:
            safe = deepcopy(item)
            if safe['decision'].get('token'):
                safe['decision']['token'] = 'sha256:' + digest(safe['decision']['token'])
            report['action_history'].append(safe)
        report['limitations'] = [s for s in report.get('limitations', []) if not s.startswith('Actions are proposals only.')]
        report['limitations'].append('Recovery verifies observed signals and request counts; interrupted requests cannot be restored.')
        return {'report': report, 'status': report['status']}


def build_graph(investigation, checkpointer, service=None):
    """Same thread/state and investigation nodes, with the response tail."""
    response = Response(service or ActionService())
    graph = StateGraph(ResponseState)
    for name in ('observe', 'investigate', 'diagnose', 'assess_risk', 'propose'):
        graph.add_node(name, getattr(investigation, name) if investigation else lambda s: {})
    for name in ('dry_run', 'approval', 'execute', 'verify', 'record_action', 'report'):
        graph.add_node(name, getattr(response, name))
    graph.add_edge(START, 'observe')
    graph.add_edge('observe', 'investigate')
    graph.add_conditional_edges('investigate', route_investigate, {'investigate': 'investigate', 'diagnose': 'diagnose'})
    graph.add_edge('diagnose', 'assess_risk')
    graph.add_edge('assess_risk', 'propose')
    graph.add_conditional_edges('propose', route_proposal, {'dry_run': 'dry_run', 'report': 'report'})
    graph.add_conditional_edges('dry_run', lambda s: 'report' if s.get('response_error') else 'approval', {'report': 'report', 'approval': 'approval'})
    graph.add_edge('approval', 'execute')
    graph.add_edge('execute', 'verify')
    graph.add_edge('verify', 'record_action')
    def next_action(s):
        last = s['action_results'][-1]
        if last['error'] or last['execution'].get('executed') and not last['verification'].get('recovered'):
            return 'report'
        return 'dry_run' if s['action_index'] < len(s['report']['proposed_actions']) else 'report'
    graph.add_conditional_edges('record_action', next_action, {'dry_run': 'dry_run', 'report': 'report'})
    graph.add_edge('report', END)
    return graph.compile(checkpointer=checkpointer)


def resume(report, decision=None, *, root=ROOT, service=None, operator='local operator', input_fn=input,
           auto_approve_for_tests=False):
    root = Path(root)
    service = service or ActionService(root)
    with SqliteSaver.from_conn_string(str(root / 'runs' / 'checkpoints.sqlite')) as saver:
        graph = build_graph(None, saver, service)
        config = config_for(report['run_id'])
        snapshot = graph.get_state(config)
        if snapshot.next != ('approval',):
            raise ValueError('Checkpoint is not waiting at approval; refusing a mismatched resume')
        if snapshot.values.get('report') != report:
            raise ValueError('Report differs from the paused checkpoint; refusing an edited plan')
        if not snapshot.values.get('dry_run', {}).get('preconditions_ok'):
            graph.update_state(config, {'action_index': 0, 'action_results': []}, as_node='propose')
            graph.invoke(None, config)
        while graph.get_state(config).next == ('approval',):
            state = graph.get_state(config).values
            if decision and decision.get('decision') == 'reject':
                answer = {'decision': 'reject', 'approved_by': operator, 'requested_at': now()}
                service.log('approval_rejected', report_id=report['run_id'], actor=operator)
            elif decision and decision.get('token'):
                answer = decision
            else:
                try:
                    answer = service.approve(state['report']['proposed_actions'][state.get('action_index', 0)],
                                             state['report'], state['dry_run'], operator, input_fn=input_fn,
                                             auto_approve_for_tests=auto_approve_for_tests)
                except Blocked as exc:
                    graph.update_state(config, {'response_error': exc.payload()}, as_node='dry_run')
                    graph.invoke(None, config)
                    break
            graph.invoke(Command(resume=answer), config)
            decision = None
        return graph.get_state(config).values['report']


def save_bundle(report, output, service, external_schema=None):
    from .reporting import write_bundle
    from tools.evidence import begin_run, end_run, capture_evidence, persist_envelope
    run_dir = service.root / report['run_id']
    entries = []
    if service.log_path.exists():
        for number, line in enumerate(service.log_path.read_text(encoding='utf-8').splitlines(), 1):
            value = json.loads(line)
            if value.get('report_id') == report['run_id']:
                entries.append((number, value))
    current, token = begin_run(run_dir)
    try:
        for number, entry in entries:
            capture_evidence(f'action_log:{number}', 'action_log', {**entry, 'complete': True})
        persist_envelope({'data': [], 'evidence_ids': [f'action_log:{n}' for n, _ in entries]}, current)
    finally:
        end_run(token)
    write_bundle(report, service.verification_alert(report), run_dir, output, external_schema=external_schema)
    bundle = Path(output).parent
    (bundle / 'action-log.jsonl').write_text(''.join(json.dumps({'line_no': n, **entry}) + '\n' for n, entry in entries), encoding='utf-8')
    for path in (run_dir / 'evidence').glob('*.json'):
        shutil.copy2(path, bundle / 'evidence' / path.name)
    # The existing tools snapshot reader has a closed v1 envelope. Keep its
    # bytes immutable and place explicit completeness alongside the content hash.
    import hashlib
    manifest = []
    for path in (bundle / 'evidence').glob('*.json'):
        record = json.loads(path.read_text(encoding='utf-8'))
        manifest.append({'id': record['id'], 'file': path.name,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'complete': record['data'].get('complete', False) if isinstance(record['data'], dict) else False})
    (bundle / 'evidence-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--operator', default='local operator')
    parser.add_argument('--reject', action='store_true')
    parser.add_argument('--auto-approve-for-tests', action='store_true')
    parser.add_argument('--external-schema', type=Path)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding='utf-8'))
    try:
        service = ActionService()
        result = resume(report, {'decision': 'reject'} if args.reject else None, service=service,
                        operator=args.operator, auto_approve_for_tests=args.auto_approve_for_tests)
        save_bundle(result, args.report, service, args.external_schema)
        from schema.validate import validate_report
        errors = validate_report(result, bundle_dir=args.report.parent)
        if errors:
            raise ValueError('Report validation failed: ' + '; '.join(errors[:5]))
        print(json.dumps({'status': result['status'], 'report': str(args.report)}))
        return 0
    except (ValueError, OSError, Blocked) as exc:
        print(str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
