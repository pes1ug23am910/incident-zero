"""Real checkpoint, ActionService and HTTP wiring with virtual telemetry only."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import threading

from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver
import pytest

from action_api.app import create_app
from agent.respond import abort_pending, config_for, pending_checkpoint, resume, save_bundle
from agent.reporting import write_bundle
from schema.validate import validate_report
from test_action_api import env, execute, pause_brain, synthetic_report


@pytest.fixture(autouse=True)
def no_live_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Integration wiring fixtures must not read the live stack')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('subprocess.Popen', forbidden)
    monkeypatch.setattr('subprocess.run', forbidden)
    monkeypatch.setattr('socket.create_connection', forbidden)


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


def prepare_real_preview(api, report):
    """Upgrade a retained brain fixture exactly as the live response graph does."""
    from agent.respond import build_graph
    with SqliteSaver.from_conn_string(str(api.root / 'runs/checkpoints.sqlite')) as saver:
        graph = build_graph(None, saver, api)
        config = config_for(report['run_id'])
        graph.update_state(config, {'action_index': 0, 'action_results': []}, as_node='propose')
        graph.invoke(None, config)
        return graph.get_state(config).values['dry_run']


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
        from tools.evidence import find_bundle_snapshot
        assert validate_report(saved, resolver=lambda identifier: find_bundle_snapshot(identifier, path.parent)) == []
        with SqliteSaver.from_conn_string(str(api.root / 'runs/checkpoints.sqlite')) as saver:
            from agent.respond import build_graph
            state = build_graph(None, saver, api).get_state(config_for(report['run_id']))
            assert not state.next and state.values['report']['status'] == status
        # The browser can also finish before the terminal reaches resume at all.
        # Only the exact original diagnosis may join the completed response.
        joined = resume(report, root=api.root, service=api, report_path=path,
                        input_fn=lambda _: pytest.fail('A completed browser decision was prompted again'))
        assert joined['status'] == status
        with pytest.raises(ValueError, match='not waiting at approval'):
            resume(saved, root=api.root, service=api)
        assert len(executor.mutations) == int(approved)
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


def test_terminal_joins_browser_already_verifying_before_terminal_entry(env, monkeypatch):
    api, executor, _, sample = env
    report, path = bundle(api, monkeypatch, 'integration-browser-first')
    verifying, release, terminal_started = threading.Event(), threading.Event(), threading.Event()
    def sampler(alert, run_id):
        if executor.mutations and not release.is_set():
            verifying.set()
            assert release.wait(10)
        return deepcopy(sample)
    api.verifier.sampler = sampler
    app = create_app(api, reports_dir=api.root / 'reports')
    results, errors = [], []
    def terminal():
        terminal_started.set()
        try:
            results.append(resume(report, root=api.root, service=api, report_path=path,
                                  input_fn=lambda _: pytest.fail('Browser-owned response requested terminal approval')))
        except Exception as exc:
            errors.append(exc)
    thread = threading.Thread(target=terminal)
    try:
        with TestClient(app) as client:
            pending = client.get('/api/approvals').json()['pending'][0]
            response = client.post('/api/approvals/' + pending['id'] + '/approve', json={
                'operator': 'Browser reviewer', 'confirmation': 'yes', 'revision': pending['revision']})
            assert response.status_code == 200, response.text
            assert verifying.wait(10)
            altered = deepcopy(report)
            altered['root_cause']['cause'] = 'An unreviewed replacement diagnosis'
            with pytest.raises(ValueError, match='not waiting at approval'):
                resume(altered, root=api.root, service=api)
            thread.start()
            assert terminal_started.wait(10)
            # While the browser owns verification, the terminal must wait so its
            # caller cannot enter operator cleanup and reset the live incident.
            thread.join(.2)
            assert thread.is_alive() and not results and not errors
            release.set()
            thread.join(10)
            app.state.control_room.backend().pool.shutdown(wait=True)
    finally:
        release.set()
        if thread.ident:
            thread.join(10)
    assert not errors and not thread.is_alive()
    assert results[0]['status'] == 'fixed'
    assert json.loads(path.read_text(encoding='utf-8'))['status'] == 'fixed'
    assert len(executor.mutations) == 1 and len(api.attempts()) == 1


@pytest.mark.parametrize('after_listing', [False, True])
def test_browser_cannot_rebind_checkpoint_diagnosis_to_changed_world(env, monkeypatch, after_listing):
    api, executor, _, _ = env
    report, _ = bundle(api, monkeypatch, 'integration-world-change')
    original = prepare_real_preview(api, report)
    app = create_app(api, reports_dir=api.root / 'reports')
    with TestClient(app) as client:
        if after_listing:
            pending = client.get('/api/approvals').json()['pending'][0]
            for field in ('plan_digest', 'report_digest', 'world_state_hash'):
                assert pending['preview'][field] == original[field]
        executor.world['switch'] = 'operator reset after diagnosis'
        if after_listing:
            response = client.post('/api/approvals/' + pending['id'] + '/approve', json={
                'operator': 'Browser reviewer', 'confirmation': 'yes', 'revision': pending['revision']})
            assert response.status_code == 409
        queue = client.get('/api/approvals').json()
        assert not queue['pending']
        assert any(item.get('reason') == 'WORLD_OR_PLAN_CHANGED' for item in queue['history'])
        assert not executor.mutations and not api.attempts()
    app.state.control_room.backend().pool.shutdown(wait=True)


@pytest.mark.parametrize('stop_url', ['/api/stop', '/stop'])
def test_stop_closes_pending_approval_and_persists_aborted_without_execution(env, monkeypatch, stop_url):
    api, executor, _, _ = env
    report, path = bundle(api, monkeypatch, 'integration-pending-stop')
    prepare_real_preview(api, report)
    with pytest.raises(ValueError, match='STOP must be latched'):
        abort_pending(report, root=api.root, service=api, report_path=path)
    app = create_app(api, reports_dir=api.root / 'reports')
    with TestClient(app) as client:
        assert client.get('/api/approvals').json()['pending']
        stopped = client.post(stop_url, json={'operator': 'Test operator'})
        assert stopped.status_code == 200 and stopped.json()['stopped']
        saved = json.loads(path.read_text(encoding='utf-8'))
        assert saved['status'] == 'aborted' and not saved['action']['executed']
        assert saved['approval']['approved'] is None
        assert 'approval_aborted' in (path.parent / 'action-log.jsonl').read_text(encoding='utf-8')
        assert not executor.mutations and not api.attempts()
        assert not client.get('/api/approvals').json()['pending']
        # A terminal arriving just after STOP joins this same canonical result.
        assert resume(report, root=api.root, service=api)['status'] == 'aborted'
    app.state.control_room.backend().pool.shutdown(wait=True)


def test_terminal_poll_notices_cli_stop_and_aborts_pending_checkpoint(env, monkeypatch):
    import agent.respond as response
    api, executor, _, _ = env
    report, path = bundle(api, monkeypatch, 'integration-terminal-stop')
    prepare_real_preview(api, report)
    entered, stopped = threading.Event(), threading.Event()
    def polling_input(prompt, changed):
        entered.set()
        assert stopped.wait(10)
        assert changed()
        raise response._ResponseElsewhere()
    monkeypatch.setattr(response, '_terminal_input', polling_input)
    results, errors = [], []
    def terminal():
        try:
            results.append(resume(report, root=api.root, service=api, report_path=path))
        except Exception as exc:
            errors.append(exc)
    thread = threading.Thread(target=terminal)
    thread.start()
    assert entered.wait(10)
    api.stop('Test terminal operator')
    stopped.set()
    thread.join(10)
    assert not errors and not thread.is_alive()
    assert results[0]['status'] == 'aborted'
    assert not executor.mutations and not api.attempts()
    assert json.loads(path.read_text(encoding='utf-8'))['status'] == 'aborted'


def test_bundle_retains_global_safety_events_only_within_its_action_interval(env, monkeypatch):
    from tools.evidence import find_bundle_snapshot
    api, _, _, _ = env
    report, path = bundle(api, monkeypatch, 'integration-global-stop-audit')
    api.log('stop', actor='Before this run')
    first = api.log('dry_run', report_id=report['run_id'])
    stop = api.log('stop', actor='Operator during this run')
    api.log('health')
    clear = api.log('clear_stop', actor='Operator during this run')
    last = api.log('verification', report_id=report['run_id'], result={'outcome': 'blocked'})
    api.log('stop', actor='After this run')
    api.log('execute_started', report_id='runs/unrelated')
    save_bundle(report, path, api)
    entries = [json.loads(line) for line in (path.parent / 'action-log.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [item['event'] for item in entries] == ['dry_run', 'stop', 'clear_stop', 'verification']
    assert [item['line_no'] for item in entries] == [int(identifier.split(':')[1]) for identifier in (first, stop, clear, last)]
    for identifier, event in ((stop, 'stop'), (clear, 'clear_stop')):
        snapshot = find_bundle_snapshot(identifier, path.parent)
        assert snapshot['source'] == 'action_log' and snapshot['data']['event'] == event
        assert snapshot['data']['complete'] is True


@pytest.mark.parametrize('failure,phase,reason', [
    ('stop', 'aborted', 'STOP_LATCHED'),
    ('callback', 'uncertain', 'VERIFY_OR_ROLLBACK_UNCERTAIN'),
])
def test_interrupted_verification_retains_actual_partial_samples_without_recovery(env, failure, phase, reason):
    api, executor, _, sample = env
    execute(api, synthetic_report())
    observed = []
    def progress(point):
        observed.append(deepcopy(point))
        if failure == 'stop':
            api.stop('Test interruption')
        else:
            raise RuntimeError('Simulated progress consumer failure')
    verification = api.verify('attempt-1', progress=progress)
    assert verification['outcome'] == 'blocked' and verification['recovered'] is False
    assert verification['rolled_back'] is False and verification['after'] is None
    assert verification['rollback_note'] == reason
    assert verification['samples'] == observed and len(observed) == 1
    assert verification['samples'][0]['elapsed_s'] == 0
    assert verification['requests_observed'] == sample['requests_observed']
    assert api.attempts()[0]['phase'] == phase
    assert not executor.rollbacks
    logged = [json.loads(line) for line in api.log_path.read_text(encoding='utf-8').splitlines()]
    assert logged[-1]['event'] == 'verification' and logged[-1]['result']['samples'] == observed


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
