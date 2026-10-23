"""Five evidence classes re-fetch synthetic backends, plus reject invented values."""

import importlib
import pytest

resolver = importlib.import_module("tools.resolve")
from tools.metrics import metric_id


def test_trace_and_span_requery_backend(monkeypatch):
    trace_id, span_id = "a" * 32, "b" * 16
    monkeypatch.setattr(resolver, "get_json", lambda url: {"data": [{"traceID": trace_id, "spans": [{"spanID": span_id}]}]})
    assert resolver.resolve(f"trace:{trace_id}")["data"]["traceID"] == trace_id
    assert resolver.resolve(f"span:{trace_id}/{span_id}")["data"]["spanID"] == span_id
    with pytest.raises(resolver.EvidenceNotFound):
        resolver.resolve(f"span:{trace_id}/" + "c" * 16)


def test_log_document_requery(monkeypatch):
    monkeypatch.setattr(resolver, "search_json", lambda path: {"found": True, "_id": "doc1", "_source": {"body": "fixture"}})
    assert resolver.resolve("log:otel/doc1")["data"]["body"] == "fixture"
    with pytest.raises(resolver.EvidenceNotFound):
        resolver.resolve("log:otel/invented")


def test_metric_query_and_value_are_verified(monkeypatch):
    query = 'sum by (service_name) (rate(calls_total{status_code="STATUS_CODE_ERROR"}[1m]))'
    identifier = metric_id({"service_name": "payment"}, [1000, 0.75], query)
    seen = []
    def request(url, params):
        seen.append(params)
        return {"data": {"result": [{"metric": {"service_name": "payment"}, "values": [[1000, "0.75"]]}]}}
    monkeypatch.setattr(resolver, "get_json", request)
    assert resolver.resolve(identifier)["data"]["value"] == .75
    assert seen[0]["query"] == query
    assert seen[0]["start"] == seen[0]["end"] == 1000
    with pytest.raises(resolver.EvidenceNotFound):
        resolver.resolve(identifier.replace("=0.75", "=0.99"))


def test_container_requery_and_changed_state(monkeypatch):
    monkeypatch.setattr(resolver, "inspect_rows", lambda names: [{"Name": "/payment", "State": {"Status": "running"},
        "RestartCount": 0, "Created": "2026-10-23T00:00:00Z", "NanoCpus": 0, "Memory": 100}])
    assert resolver.resolve("container:payment:Status=running")["data"]["value"] == "running"
    with pytest.raises(resolver.EvidenceNotFound, match="changed"):
        resolver.resolve("container:payment:Status=exited")


def test_action_journal_actual_line_number(monkeypatch):
    monkeypatch.setattr(resolver, "action_entries", lambda: [(3, {"action": "restart_service"})])
    assert resolver.resolve("action_log:3")["data"]["action"] == "restart_service"
    with pytest.raises(resolver.EvidenceNotFound):
        resolver.resolve("action_log:1")


@pytest.mark.parametrize("identity", ["invented", "trace:fake", "log:../doc", "metric:x{}@bad=1", "container:x:Config=secret"])
def test_invalid_identifiers_fail(identity):
    with pytest.raises(resolver.EvidenceNotFound):
        resolver.resolve(identity)
