"""Exercise real query construction without contacting the demo stack."""
import pytest
import requests
from datetime import datetime
from unittest.mock import Mock

from action_api.verify import LiveSampler, evaluate
from tools.queries import build_queries


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Live sampler tests must use mocked HTTP')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)


def mock_load(monkeypatch, payload=None, error=None):
    response = Mock()
    response.json.return_value = payload if payload is not None else {'state': 'running', 'user_count': 21}
    get = Mock(return_value=response, side_effect=error)
    monkeypatch.setattr('action_api.verify.requests.get', get)
    return get


@pytest.mark.parametrize('metric_name', ['traces_span_metrics_calls_total', 'calls_total'])
@pytest.mark.parametrize('sample_age,available', [(0, True), (44, True), (46, False), (-1, False)])
def test_live_sampler_accepts_actual_labelled_rate_query_and_requires_fresh_counts(monkeypatch, metric_name, sample_age, available):
    clock = 1_000_000
    captured = []
    get = mock_load(monkeypatch)
    monkeypatch.setattr('action_api.verify.time.time', lambda: clock)
    monkeypatch.setattr('tools.queries.named_query', lambda name: build_queries([metric_name])[name])
    monkeypatch.setattr('tools.health_table', lambda **kwargs: {
        'telemetry_available': True,
        'data': [{'service': 'payment', 'error_rate': .01}, {'service': 'load-generator', 'status': 'running'}],
        'evidence_ids': ['container:load-generator:Status=running'],
    })
    def get_metrics(query, **kwargs):
        captured.append(query)
        return {'data': [{'values': [[clock - sample_age, 42]]}], 'evidence_ids': ['metric:requests']}
    monkeypatch.setattr('tools.get_metrics', get_metrics)
    alert = {'service': 'payment', 'signal': 'error_rate', 'threshold': .05}
    sample = LiveSampler()(alert, 'runs/sample')
    assert captured == [f'sum(increase({metric_name}{{service_name="frontend",span_kind="SPAN_KIND_SERVER"}}[2m]))']
    assert sample['available'] is available
    assert evaluate(alert, sample) == (available, available)
    assert sample['requests_observed'] == (42 if available else 0)
    get.assert_called_once_with('http://localhost:8080/loadgen/stats/requests', timeout=10,
                                headers={'Cache-Control': 'no-cache'})
    assert sample['load_state'] == 'running' and sample['load_user_count'] == 21
    assert sample['load_available'] and sample['load_container_running'] and sample['load_running']
    assert datetime.fromisoformat(sample['load_observed_at']).tzinfo is not None


@pytest.mark.parametrize('state,users,container,available,recovered', [
    ('running', 21, 'running', True, True),
    ('running', 0, 'running', True, False),
    ('stopped', 0, 'running', True, False),
    ('stopped', 21, 'running', True, False),
    ('running', 21, 'exited', True, False),
    ('unrecognized', 21, 'running', False, False),
])
def test_live_sampler_requires_actual_active_swarm_despite_residual_requests(monkeypatch, state, users, container, available, recovered):
    clock = 1_000_000
    mock_load(monkeypatch, {'state': state, 'user_count': users})
    monkeypatch.setattr('action_api.verify.time.time', lambda: clock)
    monkeypatch.setattr('tools.queries.named_query', lambda name: build_queries(['calls_total'])[name])
    monkeypatch.setattr('tools.health_table', lambda **kwargs: {
        'telemetry_available': True,
        'data': [{'service': 'payment', 'error_rate': 0}, {'service': 'load-generator', 'status': container}],
    })
    monkeypatch.setattr('tools.get_metrics', lambda *args, **kwargs: {'data': [{'values': [[clock, 70]]}]})
    alert = {'service': 'payment', 'signal': 'error_rate', 'threshold': .05}
    sample = LiveSampler()(alert, 'runs/stopped-swarm')
    assert sample['requests_observed'] == 70
    assert sample['load_state'] == state and sample['load_user_count'] == users
    assert sample['load_running'] is recovered
    assert evaluate(alert, sample) == (available, recovered)


@pytest.mark.parametrize('payload', [
    [], {}, {'state': 'running'}, {'user_count': 21},
    {'state': None, 'user_count': 21}, {'state': '', 'user_count': 21},
    {'state': 'running', 'user_count': True}, {'state': 'running', 'user_count': -1},
    {'state': 'running', 'user_count': '21'}, {'state': 'running', 'user_count': float('nan')},
])
def test_malformed_swarm_observation_fails_closed(monkeypatch, payload):
    mock_load(monkeypatch, payload)
    sample = LiveSampler().load_snapshot()
    assert sample['load_available'] is False
    assert sample['load_state'] is None and sample['load_user_count'] is None
    assert sample['load_observed_at'] is None


@pytest.mark.parametrize('failure', ['timeout', 'http', 'json'])
def test_unavailable_swarm_observation_fails_closed(monkeypatch, failure):
    get = mock_load(monkeypatch, error=requests.Timeout() if failure == 'timeout' else None)
    if failure == 'http':
        get.return_value.raise_for_status.side_effect = requests.HTTPError()
    if failure == 'json':
        get.return_value.json.side_effect = ValueError()
    assert LiveSampler().load_snapshot() == {
        'load_state': None, 'load_user_count': None, 'load_observed_at': None, 'load_available': False}
