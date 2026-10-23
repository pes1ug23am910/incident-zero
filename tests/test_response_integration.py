"""Real checkpoint, ActionService and HTTP wiring with virtual telemetry only."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import threading

from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver
import pytest

from action_api.app import create_app
from agent.respond import config_for, pending_checkpoint, resume
from agent.reporting import write_bundle
from schema.validate import validate_report
from test_action_api import env, pause_brain, synthetic_report


def bundle(api, monkeypatch, incident='integration-payment'):
    from tools import evidence
    monkeypatch.setattr(evidence, 'ROOT', api.root)
    report = synthetic_report(incident=incident)
    report['detected_at'] = datetime.now(timezone.utc).isoformat()
    run, token = evidence.begin_run(report['run_id'])
    try:
        for row in report['evidence']:
            evidence.capture_evidence(row['id'], row['source'], {
                'service': 'payment', 'observation': 'Synthetic integration fixture.', 'complete': True})
        evidence.persist_envelope({'data': [], 'evidence_ids': [r['id'] for r in report['evidence']]}, run)
    finally:
        evidence.end_run(token)
    report['diagnosed_at'] = datetime.now(timezone.utc).isoformat()
    pause_brain(api, report)
    path = api.root / 'reports' / incident / 'report.json'
    write_bundle(report, report['alert'], run.path, path)
    return report, path


@pytest.mark.parametrize('approved,status', [(True, 'fixed'), (False, 'needs_human')])
def test_browser_resumes_checkpoint_and_saves_verified_bundle(env, monkeypatch, approved, status):
    api, executor, _, _ = env
    report, path = bundle(api, monkeypatch)
    app = create_app(api, reports_dir=api.root / 'reports')
    with TestClient(app) as client:
        assert client.get('/').status_code == 200
        assert client.get('/health').json()['ok']
        assert 'restart_service' in str(client.get('/actions').json())
        pending = client.get('/api/approvals').json()['pending'][0]
        decision = {'operator': 'Browser reviewer', 'confirmation': 'yes',
                    'reason': '' if approved else 'Investigate before modifying the service.',
                    'revision': pending['revision']}
        response = client.post('/api/approvals/' + pending['id'] + ('/approve' if approved else '/reject'), json=decision)
        assert response.status_code == 200, response.text
        app.state.control_room.backend().pool.shutdown(wait=True)
        saved = json.loads(path.read_text(encoding='utf-8'))
        assert saved['status'] == status
        assert saved['approval']['approved'] is approved
        assert len(executor.mutations) == int(approved)
        assert saved['action_history']
        assert (path.parent / 'action-log.jsonl').read_text(encoding='utf-8').strip()
        assert validate_report(saved, bundle_dir=path.parent) == []
        with SqliteSaver.from_conn_string(str(api.root / 'runs/checkpoints.sqlite')) as saver:
            from agent.respond import build_graph
            state = build_graph(None, saver, api).get_state(config_for(report['run_id']))
            assert not state.next and state.values['report']['status'] == status
        assert not client.get('/api/approvals').json()['pending']
        assert client.post('/api/stop').json()['stopped']
        assert client.get('/health').json()['stopped']
        assert client.request('DELETE', '/stop', json={'confirmation': 'I confirm the incident is over', 'operator': 'Browser reviewer'}).status_code == 200
        assert not client.get('/api/stop').json()['stopped']
        public = ''.join(client.get(url).text for url in ('/api/log', '/api/incidents', '/api/approvals'))
        with api.connect() as db:
            tokens = [json.loads(row[0]) for row in db.execute('SELECT value FROM approvals')]
        assert all('token' not in token for token in tokens)
        assert 'token_urlsafe' not in public


def test_browser_wins_while_terminal_reads_prompt_without_duplicate_execution(env, monkeypatch):
    api, executor, _, _ = env
    report, path = bundle(api, monkeypatch, 'integration-shared-prompt')
    entered, release = threading.Event(), threading.Event()
    terminal_result, errors = [], []
    def human(_):
        entered.set()
        assert release.wait(10)
        return 'yes'
    def terminal():
        try:
            terminal_result.append(resume(report, root=api.root, service=api,
                                          input_fn=human, report_path=path))
        except Exception as exc:
            errors.append(exc)
    thread = threading.Thread(target=terminal)
    thread.start()
    assert entered.wait(10)
    app = create_app(api, reports_dir=api.root / 'reports')
    try:
        with TestClient(app) as client:
            pending = client.get('/api/approvals').json()['pending'][0]
            response = client.post('/api/approvals/' + pending['id'] + '/approve', json={
                'operator': 'Browser reviewer', 'confirmation': 'yes', 'revision': pending['revision']})
            assert response.status_code == 200, response.text
            app.state.control_room.backend().pool.shutdown(wait=True)
    finally:
        release.set()
        thread.join(10)
    assert not errors and not thread.is_alive()
    assert terminal_result[0]['status'] == 'fixed'
    assert len(executor.mutations) == 1 and len(api.attempts()) == 1


def test_run_graph_pauses_after_real_dry_run_without_mutating(env):
    from agent.run import build_graph
    api, executor, _, _ = env
    report = synthetic_report(incident='integration-run-import')
    class Investigation:
        def observe(self, state): return {}
        def investigate(self, state): return {'done': True}
        def diagnose(self, state): return {'report': report}
        def assess_risk(self, state): return {'impact': report['impact']}
        def propose(self, state): return {'proposal': report['proposed_actions']}
    with SqliteSaver.from_conn_string(str(api.root / 'runs/checkpoints.sqlite')) as saver:
        graph = build_graph(Investigation(), saver, api)
        graph.invoke({'run_id': report['run_id'], 'incident_id': report['incident_id'], 'alert': report['alert']}, config_for(report['run_id']))
        state = graph.get_state(config_for(report['run_id']))
        assert state.next == ('approval',)
        assert state.values['dry_run']['preconditions_ok']
        assert state.values['dry_run']['plan']['action'] == 'toggle_flag'
        assert not executor.mutations
    canonical = pending_checkpoint(deepcopy(report), root=api.root, service=api)
    assert canonical['report'] == report
    final = resume(report, root=api.root, service=api, input_fn=lambda _: 'yes')
    assert final['status'] == 'fixed' and len(executor.mutations) == 1
