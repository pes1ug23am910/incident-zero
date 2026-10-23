"""Keep structured logger provenance available without exposing excluded telemetry."""
import pytest

from tools import logs
from tools.redact import is_sensitive


@pytest.mark.parametrize("record,expected", [
    ({"instrumentationScope": {"name": "shop.storage.RedisClient"}}, "shop.storage.RedisClient"),
    ({"instrumentation_scope": {"name": "db.Pool"}}, "db.Pool"),
    ({"scope.name": "broker.Connection"}, "broker.Connection"),
    ({"logger": {"name": "store.Client"}}, "store.Client"),
    ({"logger_name": "transport.Retry"}, "transport.Retry"),
    ({"logger": "service.Database"}, "service.Database"),
    ({"instrumentationScope": {"name": "flagd.evaluation"}}, None),
])
def test_logger_scope_shapes(record, expected):
    assert logs.logger_scope(record) == expected


def test_opensearch_scope_preserves_origin_and_severity_with_redaction(monkeypatch):
    fields = {"service_filter": "resource.service.name", "time": "@timestamp",
              "severity": "severity.number", "severity_text": "severity.text",
              "body": "body", "trace": "traceId"}
    base = {"@timestamp": "2026-10-23T12:12:23Z", "resource": {"service.name": "cart"},
            "severity": {"number": 9, "text": "Information"},
            "body": "Connection failed. Disposing the object"}
    raw = {"hits": {"total": {"value": 2}, "hits": [
        {"_index": "otel", "_id": "safe", "_source": {
            **base, "instrumentationScope": {"name": "shop.storage.RedisClient"}}},
        {"_index": "otel", "_id": "excluded", "_source": {
            **base, "instrumentationScope": {"name": "flagd.evaluation"}}},
    ]}}
    captured = []
    monkeypatch.setattr(logs, "log_index", lambda: "otel")
    monkeypatch.setattr(logs, "discover_fields", lambda index: fields)
    monkeypatch.setattr(logs, "search_json", lambda *args: raw)
    monkeypatch.setattr(logs, "capture_evidence", lambda *args: captured.append(args))
    result = logs._opensearch_logs("cart", None, {"from": "2026-10-23T12:12:00Z",
                                  "to": "2026-10-23T12:14:00Z"}, "INFO", 50, 50)
    assert len(result["data"]) == 1
    row = result["data"][0]
    assert row["logger_scope"] == "shop.storage.RedisClient"
    assert row["severity"] == "Information"
    assert row["body"] == base["body"]
    assert row["evidence_id"] == "log:otel/safe"
    assert captured[0][1] == "opensearch"
    assert captured[0][2]["instrumentationScope"]["name"] == row["logger_scope"]
    assert not is_sensitive(result)
