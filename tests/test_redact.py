"""Recorded telemetry plus labelled synthetic disclosure regression cases."""

import copy
import json
from pathlib import Path

from tools.redact import sanitize, scrub_trace, redact_text, redact_metric_series, is_sensitive, is_sensitive_evidence

FIXTURES = Path(__file__).parent / "fixtures"


def test_recorded_application_span_strips_disclosing_tags_and_events():
    recorded = json.loads((FIXTURES / "recorded_sensitive_span.json").read_text(encoding="utf-8"))
    assert recorded["provenance"]["synthetic"] is False
    original = copy.deepcopy(recorded["trace"])
    assert is_sensitive(original)
    result = scrub_trace(recorded["trace"])
    assert result and result["spans"]
    assert result["traceID"] == original["traceID"]
    assert not is_sensitive(result)
    assert recorded["trace"] == original


def test_recorded_log_is_preserved_and_disclosure_variants_are_removed():
    recorded = json.loads((FIXTURES / "recorded_log.json").read_text(encoding="utf-8"))
    assert recorded["provenance"]["synthetic"] is False
    source = recorded["document"]["_source"]
    assert sanitize(source) == source
    # Synthetic variants exercise enabled-state text absent from the clean run.
    for text in ('Feature Flag adManualGc enabled, performing a manual gc now',
                 'High CPU-Load problempattern enabled',
                 '{"feature_flag.key":"anything","value":true}',
                 'evaluation of paymentFailure returned enabled'):
        assert redact_text(text) is None
        assert sanitize({"body": text, "traceId": source["traceId"]}) is None


def test_backend_spans_and_control_metrics_are_removed():
    trace = {"traceID": "a" * 32, "processes": {"p1": {"serviceName": "checkout"},
        "p2": {"serviceName": "flagd"}}, "spans": [
        {"spanID": "1" * 16, "processID": "p1", "operationName": "PlaceOrder",
         "tags": [{"key": "feature_flag.variant", "value": "on"}, {"key": "error", "value": True}],
         "logs": [{"fields": [{"key": "event", "value": "exception"},
                               {"key": "exception.message", "value": "a real error"}]},
                  {"fields": [{"key": "feature_flag.key", "value": "paymentFailure"}]}]},
        {"spanID": "2" * 16, "processID": "p2", "operationName": "ResolveBoolean"}]}
    result = scrub_trace(trace)
    assert len(result["spans"]) == 1 and list(result["processes"]) == ["p1"]
    assert result["spans"][0]["tags"] == [{"key": "error", "value": True}]
    assert len(result["spans"][0]["logs"]) == 1
    assert redact_metric_series({"metric": {"__name__": "feature_flag_evaluations_total"}}) is None
    assert redact_metric_series({"metric": {"service_name": "flagd"}}) is None


def test_envelope_preserves_nulls_structure_and_container_metadata():
    evidence = "container:flagd:Status=running"
    envelope = {"tool": "get_container_health", "source": "docker", "query": "flagd diagnostic",
        "data": [{"name": "flagd", "Status": "running", "memory_mb": None}],
        "evidence_ids": [evidence], "values": [[1, None]]}
    result = sanitize(envelope)
    assert result["query"] == "[redacted]"
    assert result["data"][0]["name"] == "flagd"
    assert result["data"][0]["memory_mb"] is None
    assert result["evidence_ids"] == [evidence]
    assert result["values"] == [[1, None]]
    assert not is_sensitive_evidence(evidence)
    assert is_sensitive_evidence("metric:feature_flag_calls_total{}@1=1")


def test_all_container_evidence_paths_survive_envelope_redaction():
    names = ["flagd"] + ["service-" + str(number) for number in range(20)]
    ids = [f"container:{name}:Status=running" for name in names]
    paths = {identifier: "runs/example/evidence/" + str(i) + ".json" for i, identifier in enumerate(ids)}
    result = sanitize({"data": [{"name": name, "Status": "running"} for name in names],
                       "evidence_ids": ids, "evidence_paths": paths})
    assert len(result["data"]) == 21
    assert set(result["evidence_ids"]) == set(result["evidence_paths"]) == set(ids)


def test_application_cache_state_attribute_is_removed():
    record = {"tags": [{"key": "app.recommendation.cache_enabled", "value": True},
                       {"key": "demo.recommendation.cache_enabled", "value": False},
                       {"key": "app.products.count", "value": 10}]}
    assert sanitize(record) == {"tags": [{"key": "app.products.count", "value": 10}]}
