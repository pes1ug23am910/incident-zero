"""Provenance tests use fake execution; they never authorize live changes."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from test_action_api import env, synthetic_report, pause_brain
from action_api.safety import digest
from agent.respond import resume, save_bundle
from reports.approval_provenance import migrate_bundle
from reports.render import approval_summary, render_report
from schema.validate import validate_report


@pytest.mark.parametrize('surface', ['cli', 'browser', 'test'])
def test_fake_approvals_always_record_test_mode_and_public_token_id(env, surface):
    api, _, _, _ = env
    report = synthetic_report()
    plan = report['proposed_actions'][0]
    decision = api.approve(plan, report, api.dry_run(plan, report), 'Named operator',
                           input_fn=lambda _: 'yes', output=lambda _: None, surface=surface)
    stored = api.get('approvals', digest(decision['token']))
    assert decision['mode'] == stored['mode'] == 'test'
    assert decision['surface'] == stored['surface'] == surface
    assert decision['approved_by'] == 'test harness'
    assert decision['token_id'] == stored['token_id'] == 'sha256:' + digest(decision['token'])
    assert datetime.fromisoformat(decision['requested_at']) <= datetime.fromisoformat(decision['approved_at'])
    event = json.loads(api.log_path.read_text().splitlines()[-1])
    assert event['mode'] == 'test' and event['surface'] == surface
    assert event['token_id'] == decision['token_id']


def test_explicit_test_switch_is_identified_in_response_and_rendering(env, monkeypatch):
    api, _, _, _ = env
    monkeypatch.setenv('INCIDENT_ZERO_TEST', '1')
    report = synthetic_report()
    pause_brain(api, report)
    final = resume(report, root=api.root, service=api, operator='Yash Verma', auto_approve_for_tests=True)
    assert final['approval']['mode'] == 'test' and final['approval']['surface'] == 'test'
    assert final['action_history'][0]['decision']['mode'] == 'test'
    md = render_report(final)
    assert 'Approved in TEST mode by the test harness (not a human)' in md
    assert 'Approved by Yash Verma' not in md
    assert final['approval']['token_id'] in md


def test_renderer_never_guesses_human_approval_from_name():
    assert 'no human approval can be verified' in approval_summary({'approved': True, 'approved_by': 'Yash Verma'})
    assert approval_summary({'approved': True, 'mode': 'live', 'surface': 'cli', 'approved_by': 'Yash Verma'}) == 'Approved by Yash Verma'
    assert 'not a human' in approval_summary({'approved': True, 'mode': 'test', 'surface': 'browser', 'approved_by': 'Yash Verma'})


def test_rejection_has_provenance_but_no_token(env):
    api, _, _, _ = env
    report = synthetic_report()
    plan = report['proposed_actions'][0]
    decision = api.approve(plan, report, api.dry_run(plan, report), 'Tester',
                           input_fn=lambda _: 'no', output=lambda _: None)
    assert decision['decision'] == 'reject' and decision['mode'] == 'test'
    assert decision['token_id'] is None
    assert 'token' not in decision


@pytest.mark.parametrize('browser', [False, True])
def test_migration_preserves_log_and_is_idempotent(tmp_path, browser):
    report = synthetic_report()
    approval = {'required':True, 'requested_at':report['diagnosed_at'], 'approved':True,
                'approved_by':'Integration acceptance', 'approved_at':report['diagnosed_at'], 'token':'[redacted]'}
    report['approval'] = approval
    report['agent']['model'] = 'live model'
    report['limitations'] = []
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(report))
    event = {'event':'approval_granted','report_id':report['run_id'], 'actor':'Integration acceptance',
             'token_digest':'a'*64, 'mode':'human' if browser else 'test'}
    events = [event]
    if browser:
        events.append({'event':'ui_approval','report_id':report['run_id']})
    log = tmp_path / 'action-log.jsonl'
    log.write_text(''.join(json.dumps(event)+'\n' for event in events))
    before = log.read_bytes()
    first = migrate_bundle(path, automated_browser=browser)
    second = migrate_bundle(path, automated_browser=browser)
    assert first['changed'] and not second['changed']
    assert first['surface'] == ('browser' if browser else 'test') and first['mode'] == 'test'
    assert log.read_bytes() == before
    assert 'Approved by Integration acceptance' not in path.with_suffix('.md').read_text()
    saved = json.loads(path.read_text())
    assert saved['approval']['token_id'] == 'sha256:'+'a'*64


def test_unknown_legacy_human_label_is_not_upgraded(tmp_path):
    report = synthetic_report()
    report['agent']['model'] = 'live model'
    report['limitations'] = []
    report['approval'].update(approved=True, approved_by='Claimed operator', token='[redacted]')
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(report))
    (tmp_path/'action-log.jsonl').write_text(json.dumps({'event':'approval_granted',
        'report_id':report['run_id'], 'actor':'Claimed operator', 'token_digest':'a'*64, 'mode':'human'})+'\n')
    result = migrate_bundle(path)
    assert result['mode'] is None and result['surface'] is None
    assert 'no human approval can be verified' in path.with_suffix('.md').read_text()


def test_schema_requires_provenance_for_approved_report():
    report = synthetic_report()
    for proposal in [report['proposed_action'], *report.get('proposed_actions', [])]:
        for field in ('risk_tier', 'risk_reason_codes'):
            proposal.pop(field, None)
    report['approval'].update(approved=True, approved_by='Tester', requested_at=report['diagnosed_at'],
                              approved_at=report['diagnosed_at'], token='[redacted]')
    errors = validate_report(report, resolver=lambda identifier: {'source':'docker' if identifier.startswith('container:') else 'jaeger',
                                    'data':{'service':'payment'}})
    assert any('approval.mode' in error for error in errors)
    assert any('approval.surface' in error for error in errors)
    assert any('approval.token_id' in error for error in errors)
