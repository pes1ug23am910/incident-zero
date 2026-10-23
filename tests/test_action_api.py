"""Hands acceptance with fakes only: no Docker, HTTP backend or real models."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import threading

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver

from action_api.app import create_app
from action_api.safety import Blocked, digest
from action_api.service import ActionService
from action_api.verify import Verifier, evaluate
from agent.policy import propose
from agent.respond import build_graph, config_for, resume, save_bundle

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.value = 1000.
        self.on_sleep = None
    def __call__(self):
        return self.value
    def sleep(self, seconds):
        self.value += seconds
        if self.on_sleep:
            self.on_sleep(self.value)


class FakeExecutor:
    def __init__(self):
        self.world = {'containers': {'recommendation': 'stopped'}, 'switch': 'on',
                      'load': {'users': 100, 'spawn_rate': 5}}
        self.mutations = []
        self.rollbacks = []
    def snapshot(self, plan):
        return deepcopy(self.world)
    def execute(self, plan, before):
        self.mutations.append(deepcopy(plan))
        if plan['action'] == 'restart_service':
            self.world['containers'][plan['target']] = 'running'
        elif plan['action'] == 'toggle_flag':
            self.world['switch'] = 'off'
        else:
            self.world['load'] = plan['parameters']
    def rollback(self, plan, before):
        self.rollbacks.append(deepcopy(plan))
        if plan['action'] == 'restart_service':
            return {'restored': False, 'reason': 'Restart cannot restore interrupted requests.'}
        self.world = deepcopy(before)
        return {'restored': True}


def synthetic_report(component='payment', category='application_flag', incident='mock-payment', confidence=.9):
    report = json.loads((ROOT / 'schema/examples/valid.json').read_text(encoding='utf-8'))
    identifiers = [f'container:{component}:Status=running', 'trace:' + 'a'*32]
    cause = {'component': component, 'category': category, 'cause': f'Synthetic {component} failure fixture.',
             'confidence_model': confidence, 'confidence_evidence': confidence, 'confidence': confidence,
             'evidence_ids': identifiers, 'explains_symptoms': [component], 'alternatives_considered': ['Synthetic dependency failure.']}
    report.update(incident_id=incident, run_id='runs/' + incident, status='diagnosed', root_cause=cause, root_causes=[cause],
                  detected_at='2026-10-23T00:00:00+00:00', diagnosed_at='2026-10-23T00:01:00+00:00',
                  alert={'signal':'error_rate','service':component,'observed':.9,'threshold':.05,'window_s':120},
                  symptoms=[{'service':component,'signal':'error_rate','observed':'Synthetic error rate .9','evidence_ids':identifiers}],
                  evidence=[{'id':i,'source':s,'summary':f'Synthetic {component} evidence; not measured live.', 'raw_ref':'offline fixture'}
                            for i,s in zip(identifiers, ['docker','jaeger'])],
                  investigation=[{'step':1,'tool':'get_container_health','query':component,'why':'Synthetic fixture',
                                  'finding':'Synthetic observation','evidence_ids':identifiers[:1]}],
                  agent={'model':'none (mock fixtures)','tool_calls':0,'elapsed_s':0,'stopped_because':'confident'},
                  limitations=['SYNTHETIC MOCK ACCEPTANCE: no incident was injected; no model or live stack was used.'])
    return propose(report)


@pytest.fixture
def env(tmp_path):
    executor, clock = FakeExecutor(), Clock()
    sample = {'available':True,'values':[0.0],'requests_observed':40,'load_running':True,'evidence_ids':[]}
    verifier = Verifier(lambda alert, run: deepcopy(sample), clock=clock, sleep=clock.sleep)
    api = ActionService(tmp_path, executor, verifier, clock=clock)
    return api, executor, clock, sample


def approval(api, report, answer='yes'):
    plan = report['proposed_actions'][0]
    preview = api.dry_run(plan, report)
    return api.approve(plan, report, preview, 'Test operator', input_fn=lambda _:answer, output=lambda _:None)


def execute(api, report, key='attempt-1'):
    decision = approval(api, report, 'y' if report['impact']['tier'] == 1 else 'yes')
    return api.execute(report['proposed_actions'][0], report, decision['token'], key), decision


def test_http_required_403_409_423_and_forbidden_code(env):
    api, executor, _, _ = env
    report = synthetic_report()
    body = {**report['proposed_actions'][0], 'report':report, 'idempotency_key':'one'}
    with TestClient(create_app(api, input_fn=lambda _: 'yes')) as client:
        assert client.post('/actions/execute', json=body).status_code == 403
        forbidden = client.post('/actions/execute', json={**body, 'action':'delete_database'})
        assert forbidden.status_code == 403
        assert forbidden.json()['reason_codes'] == ['FORBIDDEN_OPERATION']
        preview = client.post('/actions/dry-run', json=body).json()
        token = client.post('/approvals', json={**body,'preview':preview,'operator':'Tester'}).json()['token']
        executor.world['switch'] = 'changed'
        assert client.post('/actions/execute', json={**body,'token':token}).status_code == 409
        client.post('/stop', json={'operator':'Tester'})
        assert client.post('/actions/execute', json={**body,'token':token}).status_code == 423
        assert client.delete('/stop', params={}).status_code == 422
    assert executor.mutations == []


def test_dry_run_changes_no_world_state_and_never_executes(env):
    api, executor, _, _ = env
    report = synthetic_report()
    before = deepcopy(executor.world)
    result = api.dry_run(report['proposed_actions'][0], report)
    assert result['world_state_hash'] == digest(before)
    assert executor.world == before and executor.mutations == []


def test_rollback_restores_previous_settings_and_records_unresolved(env):
    api, executor, _, sample = env
    before = deepcopy(executor.world)
    sample['values'] = [.8]
    execute(api, synthetic_report())
    result = api.verify('attempt-1')
    assert result['outcome'] == 'unresolved' and result['rolled_back']
    assert executor.world == before
    assert len(executor.rollbacks) == 1
    assert len(result['samples']) == 7 and result['samples'][-1]['elapsed_s'] == 180


def test_restart_nonrecovery_escalates_without_claiming_rollback(env):
    api, executor, _, sample = env
    sample['values'] = [.8]
    execute(api, synthetic_report('recommendation','container_down'))
    result = api.verify('attempt-1')
    assert not result['rolled_back'] and not result['recovered']
    assert 'interrupted requests' in result['rollback_note']


def test_tier_three_never_reaches_execution_even_with_forged_tier(env):
    api, executor, _, _ = env
    report = synthetic_report(confidence=.5)
    assert report['proposed_actions'] == [] and report['proposed_action'] is None
    report['impact']['tier'] = 1
    with pytest.raises(Blocked, match='TIER_3_ESCALATE'):
        api.dry_run({'action':'toggle_flag','target':'payment','parameters':{'service':'payment'}}, report)
    assert executor.mutations == []


def test_plan_edit_expiry_and_token_single_use(env):
    api, executor, clock, _ = env
    report = synthetic_report('load-generator','load')
    token = approval(api, report, 'y')['token']
    changed = deepcopy(report['proposed_actions'][0])
    changed['parameters']['users'] = 2
    with pytest.raises(Blocked, match='PLAN_OR_REPORT_CHANGED'):
        api.execute(changed, report, token, 'one')
    clock.value += 601
    with pytest.raises(Blocked, match='APPROVAL_EXPIRED'):
        api.execute(report['proposed_actions'][0], report, token, 'one')
    assert executor.mutations == []


def test_idempotency_survives_new_service_instance_and_blocks_second_key(env):
    api, executor, clock, _ = env
    report = synthetic_report()
    first, decision = execute(api, report)
    other = ActionService(api.root, executor, api.verifier, clock=clock)
    assert other.execute(report['proposed_actions'][0], report, decision['token'], 'attempt-1') == first
    with pytest.raises(Blocked, match='APPROVAL_ALREADY_USED'):
        other.execute(report['proposed_actions'][0], report, decision['token'], 'attempt-2')
    assert len(executor.mutations) == 1


def test_global_serialization_and_target_cooldown(env):
    api, executor, clock, _ = env
    report = synthetic_report()
    execute(api, report)
    other = synthetic_report('ad', incident='other')
    with pytest.raises(Blocked, match='MUTATION_IN_FLIGHT'):
        api.dry_run(other['proposed_actions'][0], other)
    api.verify('attempt-1')
    with pytest.raises(Blocked, match='TARGET_COOLDOWN'):
        api.dry_run(report['proposed_actions'][0], report)
    clock.value += 300
    assert api.dry_run(report['proposed_actions'][0], report)['preconditions_ok']


def test_stop_mid_verification_aborts_and_does_not_rollback(env):
    api, executor, clock, _ = env
    execute(api, synthetic_report())
    clock.on_sleep = lambda _: api.stop_path.touch()
    result = api.verify('attempt-1')
    assert result['outcome'] == 'blocked' and not result['rolled_back']
    assert executor.rollbacks == []
    with pytest.raises(Blocked, match='STOP_CLEAR_CONFIRMATION_REQUIRED'):
        api.clear_stop('yes', 'Tester')
    api.clear_stop('I confirm the incident is over', 'Tester')
    assert not api.stop_path.exists()


@pytest.mark.parametrize('patch', [{'requests_observed':0}, {'requests_observed':19},
                                   {'load_running':False}, {'available':False}, {'values':[]}])
def test_traffic_or_telemetry_drop_is_never_recovery(env, patch):
    api, executor, _, sample = env
    execute(api, synthetic_report())
    sample.update(patch)
    assert not api.verify('attempt-1')['recovered']


def test_all_alert_signals_must_recover(env):
    api, _, _, sample = env
    report = synthetic_report()
    report['alert']['anomalies'] = [report['alert'].copy(), {'service':'frontend','signal':'p95_ms','threshold':500}]
    sample['values'] = [0, 900]
    execute(api, report)
    assert not api.verify('attempt-1')['recovered']


def test_verification_unavailable_blocks_before_approval(env):
    api, executor, _, sample = env
    sample['available'] = False
    with pytest.raises(Blocked, match='VERIFICATION_UNAVAILABLE'):
        approval(api, synthetic_report())
    assert executor.mutations == []


def test_rollback_does_not_overwrite_concurrent_world_change(env):
    api, executor, clock, sample = env
    sample['values'] = [.9]
    execute(api, synthetic_report())
    clock.on_sleep = lambda _: executor.world.update(switch='operator changed it')
    result = api.verify('attempt-1')
    assert result['rollback_note'] == 'ROLLBACK_WORLD_CHANGED'
    assert not result['rolled_back'] and executor.rollbacks == []


def test_test_approval_requires_both_switches_and_policy_is_empty(env, monkeypatch):
    api, executor, _, _ = env
    report = synthetic_report()
    plan = report['proposed_actions'][0]
    preview = api.dry_run(plan, report)
    monkeypatch.delenv('INCIDENT_ZERO_TEST', raising=False)
    with pytest.raises(Blocked, match='TEST_APPROVAL_DISABLED'):
        api.approve(plan, report, preview, 'Tester', auto_approve_for_tests=True)
    monkeypatch.setenv('INCIDENT_ZERO_TEST','1')
    messages = []
    decision = api.approve(plan, report, preview, 'Tester', auto_approve_for_tests=True, output=messages.append)
    assert decision['token'] and any('TEST ONLY' in line for line in messages)
    with pytest.raises(Blocked, match='POLICY_APPROVAL_DISABLED'):
        api.approve(plan, report, preview, 'Tester', policy_approval=True)
    assert executor.mutations == []


def pause_brain(api, report):
    from agent.graph import build_graph as brain_graph
    class Investigation:
        def observe(self, state): return {}
        def investigate(self, state): return {'done':True}
        def diagnose(self, state): return {'report':report}
        def assess_risk(self, state): return {'impact':report['impact']}
        def propose(self, state): return {'proposal':report['proposed_actions']}
    with SqliteSaver.from_conn_string(str(api.root/'runs/checkpoints.sqlite')) as saver:
        graph = brain_graph(Investigation(), saver)
        graph.invoke({'run_id':report['run_id'], 'incident_id':report['incident_id']}, config_for(report['run_id']))
        assert graph.get_state(config_for(report['run_id'])).next == ('approval',)


@pytest.mark.parametrize('component,category,answer,expected', [
    ('payment','application_flag','yes','fixed'), ('payment','application_flag','no','needs_human'),
    ('recommendation','container_down','yes','fixed'), ('load-generator','load','y','fixed')])
def test_existing_brain_checkpoint_full_loop(env, component, category, answer, expected):
    api, executor, _, _ = env
    report = synthetic_report(component,category)
    pause_brain(api,report)
    prompts = []
    def human(text): prompts.append(text); return answer
    final = resume(report, root=api.root, service=api, operator='Tester', input_fn=human)
    assert final['status'] == expected
    assert len(prompts) == 1
    assert len(executor.mutations) == int(expected == 'fixed')
    with pytest.raises(ValueError, match='not waiting at approval'):
        resume(final, root=api.root, service=api)


def test_checkpoint_report_and_thread_mismatch_refused(env):
    api, executor, _, _ = env
    report = synthetic_report()
    pause_brain(api,report)
    edited = deepcopy(report)
    edited['proposed_actions'][0]['target'] = 'ad'
    with pytest.raises(ValueError, match='differs'):
        resume(edited, root=api.root, service=api)
    report['run_id'] = 'runs/wrong'
    with pytest.raises(ValueError, match='not waiting'):
        resume(report, root=api.root, service=api)
    assert executor.mutations == []


@pytest.mark.parametrize('case,component,category,answer,expected', [
    ('payment-approved','payment','application_flag','yes','fixed'),
    ('payment-rejected','payment','application_flag','no','needs_human'),
    ('recommendation-restart','recommendation','container_down','yes','fixed'),
    ('homepage-throttle','load-generator','load','y','fixed'),
    ('stop-mid-run','payment','application_flag','yes','aborted'),
    ('non-recovery','payment','application_flag','yes','rolled_back'),
])
def test_mock_acceptance_bundles(env, monkeypatch, case, component, category, answer, expected):
    from tools.evidence import begin_run, end_run, capture_evidence, persist_envelope
    from tools.evidence import find_bundle_snapshot
    from schema.validate import validate_report
    api, executor, clock, sample = env
    report = synthetic_report(component, category, incident='mock-' + case)
    # Actual fixture capture time must precede diagnosis.
    report['detected_at'] = datetime.now(timezone.utc).isoformat()
    current, token = begin_run(report['run_id'])
    try:
        for row in report['evidence']:
            capture_evidence(row['id'], row['source'], {'service':component, 'complete':True,
                             'observation':'Synthetic fixture; not live telemetry.'})
        persist_envelope({'evidence_ids':[row['id'] for row in report['evidence']], 'data':[]}, current)
    finally:
        end_run(token)
    report['diagnosed_at'] = datetime.now(timezone.utc).isoformat()
    if case == 'non-recovery':
        sample['values'] = [.8]
    if case == 'stop-mid-run':
        clock.on_sleep = lambda _: api.stop_path.touch()
    pause_brain(api, report)
    final = resume(report, root=api.root, service=api, operator='Mock operator', input_fn=lambda _:answer)
    assert final['status'] == expected
    output = api.root / 'reports' / report['incident_id'] / 'report.json'
    save_bundle(final, output, api)
    assert validate_report(final, resolver=lambda i:find_bundle_snapshot(i, output.parent)) == []
    actual = json.loads(output.read_text(encoding='utf-8'))
    assert validate_report(actual, resolver=lambda i:find_bundle_snapshot(i, output.parent)) == []
    assert actual['status'] == expected
    assert (output.parent/'action-log.jsonl').read_text(encoding='utf-8').strip()
    if final['action']['executed']:
        assert find_bundle_snapshot(final['action']['action_log_ref'], output.parent)['source'] == 'action_log'
    # Optional export is for this mocked acceptance run only, never a live hook.
    export = os.environ.get('INCIDENT_ZERO_MOCK_BUNDLES')
    if export:
        destination = Path(export).resolve()
        assert destination == (ROOT/'reports').resolve()
        shutil.copytree(output.parent, destination/report['incident_id'], dirs_exist_ok=True)


def test_second_concurrent_executor_cannot_enter(env, monkeypatch):
    api, executor, clock, _ = env
    report = synthetic_report()
    token = approval(api, report)['token']
    other = ActionService(api.root, executor, api.verifier, clock=clock)
    entered, release = threading.Event(), threading.Event()
    original = executor.execute
    def hold(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(executor, 'execute', hold)
    errors = []
    def worker():
        try: api.execute(report['proposed_actions'][0], report, token, 'one')
        except Exception as exc: errors.append(exc)
    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(5)
    try:
        with pytest.raises(Blocked, match='MUTATION_IN_FLIGHT'):
            other.execute(report['proposed_actions'][0], report, token, 'two')
    finally:
        release.set()
        thread.join(5)
    assert not errors and len(executor.mutations) == 1


def test_switch_executor_uses_mounted_fixture_and_restores_exact_variants(tmp_path):
    from action_api.flags import Switches, MAPPING
    path = tmp_path / '.state' / 'flags' / 'demo.flagd.json'
    path.parent.mkdir(parents=True)
    document = {'flags':{name:{'variants':{'off':False,'on':True},'defaultVariant':'on'}
                         for name in MAPPING['payment']}}
    path.write_text(json.dumps(document), encoding='utf-8')
    switches = Switches(lambda _: {'Mounts':[{'Destination':'/etc/flagd','Source':str(path.parent)}]}, path)
    before = switches.snapshot('payment')
    switches.apply('payment')
    assert all(v == 'off' for v in switches.snapshot('payment')['prior'].values())
    switches.apply('payment', before['prior'])
    assert json.loads(path.read_text()) == document


def test_switch_executor_refuses_official_source_writes(tmp_path):
    from action_api.flags import Switches
    path = tmp_path/'demo.flagd.json'
    path.write_text('{"flags":{}}')
    switches = Switches(lambda _: {'Mounts':[{'Destination':'/etc/flagd','Source':str(tmp_path)}]},path)
    assert switches.snapshot()['sha256']
    with pytest.raises(Blocked, match='OPERATOR_OVERLAY_REQUIRED'):
        switches.apply('payment')


def test_tier_two_rejects_a_single_key_and_prompt_order(env):
    api, _, _, _ = env
    report = synthetic_report()
    plan = report['proposed_actions'][0]
    lines = []
    result = api.approve(plan, report, api.dry_run(plan,report), 'Tester', input_fn=lambda _:'y', output=lines.append)
    assert result['decision'] == 'reject'
    headers = ['Affected service:', 'Diagnosis:', 'Evidence IDs:', 'Exact operation:', 'Risk:',
               'Expected effect:', 'Rollback limits:', 'Verification:']
    indices = [next(i for i,l in enumerate(lines) if l.startswith(h)) for h in headers]
    assert indices == sorted(indices)


@pytest.mark.parametrize('plan,code', [
    ({'action':'restart_service','target':'payment; shutdown','parameters':{}}, 'INVALID_TARGET'),
    ({'action':'restart_service','target':'payment','parameters':{'service':'ad'}}, 'INVALID_PARAMETERS'),
    ({'action':'throttle_load','target':'load-generator','parameters':{'users':0,'spawn_rate':1}}, 'INVALID_PARAMETERS'),
    ({'action':'throttle_load','target':'load-generator','parameters':{'users':True,'spawn_rate':1}}, 'INVALID_PARAMETERS'),
    ({'action':'scale_service','target':'payment','parameters':{}}, 'NOT_AVAILABLE_ON_COMPOSE')])
def test_closed_operations_targets_and_parameters(env, plan, code):
    api, executor, _, _ = env
    with TestClient(create_app(api)) as client:
        response = client.post('/actions/execute', json={**plan,'report':synthetic_report(),'idempotency_key':'x'})
        assert response.status_code == 403 and response.json()['reason_codes'] == [code]
    assert executor.mutations == []


def test_failed_attempt_cannot_be_reapproved_from_the_same_report(env):
    api, _, clock, sample = env
    sample['values'] = [.9]
    report = synthetic_report()
    execute(api,report)
    api.verify('attempt-1')
    clock.value += 301
    with pytest.raises(Blocked, match='PREVIOUS_ATTEMPT_FAILED'):
        approval(api, report)


def test_world_changes_during_human_prompt_invalidates_approval(env):
    api, executor, _, _ = env
    report = synthetic_report()
    plan = report['proposed_actions'][0]
    preview = api.dry_run(plan,report)
    def human(_):
        executor.world['switch'] = 'changed while waiting'
        return 'yes'
    with pytest.raises(Blocked, match='WORLD_STATE_CHANGED'):
        api.approve(plan,report,preview,'Tester',input_fn=human,output=lambda _:None)
    assert executor.mutations == []


def test_future_diagnostic_evidence_and_false_fixed_outcome_rejected():
    from schema.validate import validate_report
    report = synthetic_report()
    errors = validate_report(report, resolver=lambda i:{'source':'docker' if i.startswith('container:') else 'jaeger',
                'captured_at':'2099-01-01T00:00:00+00:00','data':{'service':'payment'}})
    assert any('timestamp follows diagnosed_at' in e for e in errors)


def test_policy_approval_banner_when_explicitly_configured(env):
    api, _, clock, _ = env
    policy = deepcopy(api.policy)
    policy['auto_approve_tiers'] = [1]
    other = ActionService(api.root, api.executor, api.verifier, clock=clock, policy=policy)
    report = synthetic_report('ad')
    plan = report['proposed_actions'][0]
    messages=[]
    decision=other.approve(plan,report,other.dry_run(plan,report),'Policy owner',policy_approval=True,output=messages.append)
    assert decision['token']
    assert 'policy approval, outside the event rules' in messages
    assert api.policy['auto_approve_tiers'] == []


def test_resume_accepts_exact_sanitized_brain_bundle(env):
    from agent.llm_router import scrub
    api, executor, _, _ = env
    report = synthetic_report()
    pause_brain(api,report)
    saved = scrub(report)
    assert saved['approval']['token'] == '[redacted]'
    final = resume(saved, root=api.root, service=api, input_fn=lambda _:'yes')
    assert final['status'] == 'fixed' and len(executor.mutations) == 1


def test_explicit_rejection_needs_no_live_preconditions(env):
    api, executor, _, sample = env
    report=synthetic_report()
    pause_brain(api,report)
    sample['available']=False
    final=resume(report, {'decision':'reject'}, root=api.root, service=api)
    assert final['status']=='needs_human' and final['approval']['approved'] is False
    assert executor.mutations==[]
