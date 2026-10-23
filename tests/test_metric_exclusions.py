import json

import pytest

from tools import metrics
import tools.resolve as resolution
from tools.queries import build_queries
from tools.redact import APPLICATION_SPAN_SELECTOR, is_sensitive


@pytest.mark.parametrize('name', ['error_rate_by_service', 'rps_by_service', 'p95_latency_by_service'])
def test_named_aggregations_exclude_control_spans(name):
    query = build_queries()[name]
    assert APPLICATION_SPAN_SELECTOR in query
    if name == 'error_rate_by_service':
        assert query.count(APPLICATION_SPAN_SELECTOR) == 3


def test_named_query_alias_is_safe_and_resolves_actual_filtered_query(monkeypatch):
    name = 'error_rate_by_service'
    query = build_queries()[name]
    seen = []
    def read(url, params=None):
        seen.append(params['query'])
        return {'status': 'success', 'data': {'result': [
            {'metric': {'service_name': 'payment'}, 'values': [[1, '.2']]}]}}
    monkeypatch.setattr(metrics, 'named_query', lambda _: query)
    monkeypatch.setattr(metrics, 'get_json', read)
    result = metrics.get_metrics(name)
    assert not result.get('error')
    assert not is_sensitive(result)
    identifier = result['evidence_ids'][0]
    assert 'named:error_rate_by_service' in identifier
    assert len(identifier) < 130
    monkeypatch.setattr(resolution, 'named_query', lambda _: query)
    monkeypatch.setattr(resolution, 'get_json', read)
    resolved = resolution._resolve(identifier)
    assert resolved['data']['value'] == .2
    assert not is_sensitive(resolved)
    assert seen == [query, query]


def test_sensitive_custom_query_remains_rejected():
    result = metrics.get_metrics('sum(calls_total{service_name="flagd"})')
    assert result.get('error') and not result['evidence_ids']


def test_named_metric_alias_preserves_positive_evidence_strength():
    from agent.evidence import strength
    assert strength('metric:query{}@1=0.2', {'query': 'named:error_rate_by_service', 'value': .2}) == .9
    assert strength('metric:query{}@1=900', {'query': 'named:p95_latency_by_service', 'value': 900}) == .8
