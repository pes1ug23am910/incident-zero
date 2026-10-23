"""Exercise real query construction without contacting the demo stack."""
import pytest

from action_api.verify import LiveSampler, evaluate
from tools.queries import build_queries


@pytest.mark.parametrize('metric_name', ['traces_span_metrics_calls_total', 'calls_total'])
@pytest.mark.parametrize('sample_age,available', [(0, True), (44, True), (46, False), (-1, False)])
def test_live_sampler_accepts_actual_labelled_rate_query_and_requires_fresh_counts(monkeypatch, metric_name, sample_age, available):
    clock = 1_000_000
    captured = []
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
