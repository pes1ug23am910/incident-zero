import json
from pathlib import Path

from tools import traces


def test_recorded_payment_origin_is_not_dropped_by_eight_span_cap(monkeypatch):
    trace = json.loads((Path(__file__).parent / "fixtures/payment_failure_trace.json").read_text())
    summary = traces.trace_summary(trace)
    origin = summary["origin_error_spans"][0]
    assert len(summary["error_spans"]) == 9
    assert origin["service"] == "payment"
    assert origin["operation"].endswith("PaymentService/Charge")
    assert "Payment request failed" in json.dumps(origin)
    assert summary["first_error_span"] == origin
    monkeypatch.setattr(traces, "get_json", lambda *a, **kw: {"data": [trace]})
    result = traces.get_traces("checkout")
    assert f'span:{trace["traceID"]}/{origin["span_id"]}' in result["evidence_ids"]


def test_origins_two_hops_down_and_independent_branch_are_deepest_first(monkeypatch):
    trace = {"traceID": "a" * 32, "processes": {}, "spans": []}
    for index, parent, service in [(1, None, "frontend"), (2, 1, "checkout"),
                                  (3, 2, "payment"), (4, 1, "recommendation")]:
        span_id = f"{index:016x}"
        trace["processes"][service] = {"serviceName": service}
        trace["spans"].append({"spanID": span_id, "processID": service,
            "operationName": "operation-" + service, "startTime": index, "duration": 100,
            "tags": [{"key": "error", "value": True},
                     {"key": "otel.status_description", "value": "failed " + service}],
            "logs": [{"fields": [{"key": "exception.message", "value": "failure " + service}]}],
            "references": [{"refType": "CHILD_OF", "traceID": trace["traceID"],
                            "spanID": f"{parent:016x}"}] if parent else []})
    # Reverse input order so selection cannot accidentally rely on array order.
    trace["spans"].reverse()
    summary = traces.trace_summary(trace)
    assert [s["service"] for s in summary["origin_error_spans"]] == ["payment", "recommendation"]
    assert summary["first_error_span"]["status_message"] == "failed payment"
    assert summary["first_error_span"]["exception"]["exception.message"] == "failure payment"
    monkeypatch.setattr(traces, "get_json", lambda *a, **kw: {"data": [trace]})
    result = traces.get_traces("frontend")
    assert set(i for i in result["evidence_ids"] if i.startswith("span:")) == {
        f'span:{trace["traceID"]}/{index:016x}' for index in (3, 4)}
