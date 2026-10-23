"""Control backends cannot become diagnostic rows or retained evidence."""
import json

import pytest

from tools import containers, deploy, summarize
from tools.redact import is_sensitive


def inspect_row(name):
    return {'Name': '/' + name, 'State': {'Status': 'running', 'StartedAt': '2026-10-23T12:00:00Z'},
            'RestartCount': 0, 'Created': '2026-10-23T11:59:00Z', 'NanoCpus': 0, 'Memory': 0}


@pytest.mark.parametrize('names', [None, ['payment', 'flagd'], ['flagd']])
def test_container_filter_precedes_reads_and_evidence_capture(monkeypatch, tmp_path, names):
    monkeypatch.setattr(containers, 'container_names', lambda: ['payment', 'flagd'])
    calls = []
    def read(*arguments):
        calls.append(arguments)
        assert 'flagd' not in arguments
        if arguments[0] == 'stats':
            return ''
        # Even an unexpected extra backend row must be rejected before capture.
        return '\n'.join(json.dumps(inspect_row(name)) for name in ['payment', 'flagd'])
    monkeypatch.setattr(containers, 'docker', read)
    result = containers.get_container_health(names, run_dir='filtered-health')
    assert not result.get('error')
    assert not is_sensitive(result)
    assert [row['name'] for row in result['data']] == ([] if names == ['flagd'] else ['payment'])
    files = list((tmp_path / 'runs' / 'filtered-health' / 'evidence').glob('*.json'))
    assert len(files) == (0 if names == ['flagd'] else 6)
    assert all(not is_sensitive(json.loads(path.read_text(encoding='utf-8'))) for path in files)
    if names == ['flagd']:
        assert not calls


def test_inspect_rows_and_deploy_history_drop_control_lifecycle(monkeypatch, tmp_path):
    source = [inspect_row('payment'), inspect_row('flagd')]
    monkeypatch.setattr(containers, 'container_names', lambda: ['payment', 'flagd'])
    def read(*arguments):
        assert 'flagd' not in arguments
        return '\n'.join(json.dumps(row) for row in source)
    monkeypatch.setattr(containers, 'docker', read)
    assert [row['Name'] for row in containers.inspect_rows()] == ['/payment']
    monkeypatch.setattr(deploy, 'inspect_rows', lambda: source)
    monkeypatch.setattr(deploy, 'action_entries', lambda: [])
    monkeypatch.setattr(deploy, 'window', lambda _: {'from': '2026-10-23T11:00:00+00:00', 'to': '2026-10-23T13:00:00+00:00'})
    result = deploy.get_deploy_history(run_dir='filtered-deploy')
    assert not result.get('error')
    assert len(result['data']) == len(result['evidence_ids']) == 2
    assert {row['container'] for row in result['data']} == {'payment'}
    files = list((tmp_path / 'runs' / 'filtered-deploy' / 'evidence').glob('*.json'))
    assert len(files) == 2
    assert all(not is_sensitive(json.loads(path.read_text(encoding='utf-8'))) for path in files)


@pytest.mark.parametrize('application_present', [False, True])
def test_health_join_excludes_control_rows_metrics_and_evidence(monkeypatch, application_present):
    names = ['flagd'] + (['payment'] if application_present else [])
    monkeypatch.setattr(summarize, 'get_container_health', lambda: {
        'data': [{'name': name, 'RestartCount': 0, 'Status': 'running', 'cpu_percent': 1, 'memory_mb': 10} for name in names],
        'evidence_ids': [f'container:{name}:Status=running' for name in names]})
    monkeypatch.setattr(summarize, 'get_metrics', lambda *args: {
        'data': [{'metric': {'service_name': name}, 'values': [[1, 1]],
                  'latest_evidence_id': f'metric:requests{{service_name="{name}"}}@1=1'} for name in names],
        'truncated': False})
    # Inspect the join before generic sanitization could hide a missed filter.
    result = summarize.health_table.__wrapped__()
    assert not is_sensitive(result)
    assert [row['service'] for row in result['data']] == (['payment'] if application_present else [])
    assert result['telemetry_available'] is application_present
