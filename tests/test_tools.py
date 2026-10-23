"""Synthetic protocol fixtures test bounds and behavior; these are not live results."""

import json
import subprocess
from unittest.mock import Mock

import pytest

from tools import metrics, logs, traces, summarize, containers
from tools.common import BackendError
from tools.queries import build_queries
from tools.containers import memory_mb


def test_metric_cap_step_and_reproducible_peak(monkeypatch):
    response = {"status": "success", "data": {"result": [
        {"metric": {"service_name": f"service-{i}"}, "values": [[j, str(j)] for j in range(250)]}
        for i in range(25)]}}
    request = Mock(return_value=response)
    monkeypatch.setattr(metrics, "get_json", request)
    result = metrics.get_metrics("sum(rate(requests_total[1m]))", lookback_s=86400, step_s=1)
    assert len(result["data"]) == 20
    assert len(result["data"][0]["values"]) == 200
    assert result["truncated"] is True
    assert request.call_args.kwargs["params"]["step"] >= 86400 / 199
    assert result["evidence_ids"][0].endswith("@199=199.0")
    assert "__query__=" in result["evidence_ids"][0]


def test_no_measurements_does_not_mean_healthy(monkeypatch):
    monkeypatch.setattr(metrics, "get_json", lambda *a, **kw: {"status": "success", "data": {"result": []}})
    result = metrics.get_metrics("requests_total")
    assert result["data"] == [] and result["evidence_ids"] == []
    assert "missing" in result["warning"]


def test_nonfinite_measurements_are_null_without_evidence(monkeypatch):
    monkeypatch.setattr(metrics, "get_json", lambda *a, **kw: {"status": "success", "data": {"result": [
        {"metric": {}, "values": [[1, "NaN"], [2, "+Inf"]]}]}})
    result = metrics.get_metrics("requests_total")
    assert result["data"][0]["values"] == [[1, None], [2, None]]
    assert result["evidence_ids"] == []
    json.dumps(result, allow_nan=False)


def test_named_queries_use_discovered_variant():
    query = build_queries(["traces_span_metrics_calls_total"])["error_rate_by_service"]
    assert "traces_span_metrics_calls_total" in query
    assert "or (0 *" in query


def test_trace_summary_and_cap(monkeypatch):
    trace = {"traceID": "1" * 32, "processes": {"p1": {"serviceName": "checkout"}}, "spans": [
        {"spanID": "2" * 16, "processID": "p1", "operationName": "charge", "startTime": 1000,
         "duration": 5000, "tags": [{"key": "error", "value": True}], "references": [],
         "logs": [{"fields": [{"key": "exception.message", "value": "synthetic failure"}]}]}]}
    monkeypatch.setattr(traces, "get_json", lambda *a, **kw: {"data": [trace] * 51})
    result = traces.get_traces("checkout", limit=100)
    assert len(result["data"]) == 50
    assert result["truncated"] is True
    assert result["data"][0]["first_error_span"]["exception"]["exception.message"] == "synthetic failure"
    assert "span:" + "1" * 32 + "/" + "2" * 16 in result["evidence_ids"]


@pytest.fixture
def synthetic_mapping():
    return {"otel": {"mappings": {"properties": {
        "resource": {"properties": {"attributes": {"properties": {"service.name": {
            "type": "text", "fields": {"keyword": {"type": "keyword"}}}}}}},
        "time": {"type": "date"}, "severity_number": {"type": "integer"},
        "severity_text": {"type": "keyword"}, "body": {"type": "text"}, "trace_id": {"type": "keyword"}
    }}}}


def test_logs_discover_exact_fields_and_bound_results(monkeypatch, synthetic_mapping):
    seen = []
    def request(path, body=None):
        seen.append((path, body))
        if path.endswith("_mapping"):
            return synthetic_mapping
        return {"hits": {"total": {"value": 101}, "hits": [
            {"_index": "otel", "_id": str(i), "_source": {"time": "2026-10-23T00:00:00Z",
                "severity_number": 17, "severity_text": "ERROR", "body": "x" * 350,
                "resource": {"attributes": {"service.name": "payment"}}}} for i in range(101)]}}
    monkeypatch.setattr(logs, "search_json", request)
    result = logs.get_logs("payment", limit=999)
    assert len(result["data"]) == 100 and result["truncated"] is True
    assert len(result["data"][0]["body"]) == 300
    assert seen[-1][1]["query"]["bool"]["filter"][0] == {"term": {"resource.attributes.service.name.keyword": "payment"}}
    assert result["evidence_ids"][0] == "log:otel/0"
    assert logs.field_value({"resource": {"attributes": {"service.name": "payment"}}}, "resource.attributes.service.name") == "payment"


def test_missing_log_index_is_explicit_error(monkeypatch):
    def unavailable(*a, **kw):
        raise BackendError("HTTP 404 index_not_found_exception")
    monkeypatch.setattr(logs, "search_json", unavailable)
    result = logs.get_logs("payment")
    assert result["error"]["type"] == "BackendError"
    assert result["data"] == []


def test_health_table_retains_unknown_values(monkeypatch):
    monkeypatch.setattr(summarize, "get_metrics", lambda *a: {"data": [], "evidence_ids": [], "truncated": False, "warning": "No measurements"})
    monkeypatch.setattr(summarize, "get_container_health", lambda: {"data": [{"name": "frontend", "RestartCount": 0,
        "Status": "running", "cpu_percent": 1, "memory_mb": 10}], "evidence_ids": []})
    result = summarize.health_table()
    assert result["data"][0]["error_rate"] is None
    assert result["data"][0]["rps"] is None
    assert result["telemetry_available"] is False
    assert len(result["warnings"]) == 3


def test_memory_units():
    assert memory_mb("1GiB / 2GiB") == pytest.approx(1073.741824)
    assert memory_mb("64MB / 1GB") == 64
    assert memory_mb("unavailable") is None


def test_health_table_does_not_revive_stale_measurement(monkeypatch):
    monkeypatch.setattr(summarize, "get_metrics", lambda *a: {"data": [{"metric": {"service_name": "frontend"},
        "values": [[1, 0.0], [2, None]]}], "evidence_ids": [], "truncated": False})
    monkeypatch.setattr(summarize, "get_container_health", lambda: {"data": [], "evidence_ids": []})
    result = summarize.health_table()
    assert result["data"][0]["error_rate"] is None
    assert result["telemetry_available"] is False


def test_stats_timeout_preserves_inspected_state(monkeypatch):
    monkeypatch.setattr(containers, "container_names", lambda: ["payment"])
    def docker_read(*args):
        if args[0] == "stats":
            raise subprocess.TimeoutExpired("docker stats", 2)
        return json.dumps({"Name": "/payment", "State": {"Status": "exited"},
            "RestartCount": 0, "Created": "2026-10-23T00:00:00Z", "NanoCpus": 0, "Memory": 100})
    monkeypatch.setattr(containers, "docker", docker_read)
    result = containers.get_container_health()
    assert result["data"][0]["Status"] == "exited"
    assert result["data"][0]["cpu_percent"] is None
    assert result["warnings"]
