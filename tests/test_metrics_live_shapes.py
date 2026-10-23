"""Regression checks for shapes discovered on the live 2.0.2 stack."""

from datetime import datetime

import pytest

from tools import metrics, summarize, traces
from tools.queries import build_queries


def test_discovered_otlp_names_and_minute_export_cadence():
    queries = build_queries([
        "traces_span_metrics_calls_total",
        "traces_span_metrics_duration_milliseconds_bucket",
        "container_memory_usage_total_bytes",
    ])
    assert queries["container_memory"] == "container_memory_usage_total_bytes"
    for name in ("error_rate_by_service", "p95_latency_by_service", "rps_by_service"):
        assert "[1m]" not in queries[name]
        assert "[2m]" in queries[name]
    assert "or (0 *" in queries["error_rate_by_service"]


def test_latest_metric_proof_does_not_reuse_old_peak(monkeypatch):
    monkeypatch.setattr(metrics, "get_json", lambda *args, **kwargs: {
        "status": "success", "data": {"result": [{
            "metric": {"service_name": "checkout"},
            "values": [[1000, "0.6"], [1015, "0.0"]],
        }]},
    })
    result = metrics.get_metrics("sum by(service_name)(requests_total)")
    series = result["data"][0]
    assert series["peak_evidence_id"].endswith("@1000=0.6")
    assert series["latest_evidence_id"].endswith("@1015=0.0")
    assert set(result["evidence_ids"]) == {series["peak_evidence_id"], series["latest_evidence_id"]}


def test_health_traffic_measurements_have_current_proofs(monkeypatch):
    measures = {"error_rate_by_service": 0.0, "p95_latency_by_service": 4.7, "rps_by_service": 1.2}

    def read_metric(query, lookback):
        value = measures[query]
        return {"data": [{"metric": {"service_name": "frontend"},
                          "values": [[1000, 99.0], [1015, value]],
                          "peak_evidence_id": query + "-old",
                          "latest_evidence_id": query + "-current"}],
                "evidence_ids": [query + "-old", query + "-current"], "truncated": False}

    monkeypatch.setattr(summarize, "get_metrics", read_metric)
    monkeypatch.setattr(summarize, "get_container_health", lambda: {
        "data": [{"name": "frontend", "RestartCount": 0, "Status": "running",
                  "cpu_percent": 1.0, "memory_mb": 20.0}], "evidence_ids": []})
    result = summarize.health_table()
    row = result["data"][0]
    assert (row["error_rate"], row["p95_ms"], row["rps"]) == (0.0, 4.7, 1.2)
    assert result["telemetry_available"] is True
    assert set(result["evidence_ids"]) == {name + "-current" for name in measures}


def test_jaeger_search_uses_explicit_microsecond_window(monkeypatch):
    calls = []

    def fetch(url, params=None):
        calls.append((url, params))
        return {"data": []}

    monkeypatch.setattr(traces, "get_json", fetch)
    result = traces.get_traces("checkout", lookback_s=60)
    url, params = calls[0]
    assert url.endswith("/jaeger/ui/api/traces")
    assert "lookback" not in params
    assert params["end"] - params["start"] == pytest.approx(60_000_000, abs=2)
    assert params["start"] == int(datetime.fromisoformat(result["window"]["from"]).timestamp() * 1e6)
    assert params["end"] == int(datetime.fromisoformat(result["window"]["to"]).timestamp() * 1e6)
