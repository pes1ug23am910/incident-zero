"""Bounded summaries from the trace backend."""

import json
from datetime import datetime, timedelta, timezone
from .common import bounded, envelope, get_json, jaeger_json, window, BackendError
from .redact import is_sensitive, scrub_trace
from .evidence import capture_evidence


def tags(span):
    result = {tag["key"]: tag.get("value") for tag in span.get("tags", [])}
    for log in span.get("logs", []):
        for field in log.get("fields", []):
            key = field.get("key", "")
            if key.startswith("exception.") or key in ("message", "error.object"):
                result[key] = field.get("value")
    return result


def is_error(span):
    values = tags(span)
    return values.get("error") in (True, "true") or values.get("otel.status_code") == "ERROR"


def span_summary(span, processes):
    attributes = tags(span)
    return {
        "span_id": span.get("spanID"),
        "service": processes.get(span.get("processID"), {}).get("serviceName", "unknown"),
        "operation": span.get("operationName", "")[:200],
        "duration_ms": span.get("duration", 0) / 1000,
        "status_message": str(attributes.get("otel.status_description", attributes.get("rpc.grpc.status_code", attributes.get("message", ""))))[:300],
        "exception": {k: str(v)[:300] for k, v in attributes.items() if k.startswith("exception.")},
    }


def trace_summary(trace):
    trace = scrub_trace(trace)
    if trace is None:
        return None
    spans = trace.get("spans", [])
    processes = trace.get("processes", {})
    ordered = sorted(spans, key=lambda s: s.get("startTime", 0))
    root = next((s for s in ordered if not any(r.get("refType") == "CHILD_OF" for r in s.get("references", []))), ordered[0] if ordered else {})
    # A caller's error is usually propagated from a deeper failed operation.
    # Select origins from the full graph before applying any presentation limit.
    by_id = {s.get("spanID"): s for s in spans}
    parents = {s.get("spanID"): [r.get("spanID") for r in s.get("references", [])
               if r.get("refType") == "CHILD_OF"
               and r.get("traceID", trace["traceID"]) == trace["traceID"]] for s in spans}
    errors = [s for s in spans if is_error(s)]
    error_parents = {parent for s in errors for parent in parents[s.get("spanID")]}

    def depth(span_id, seen=frozenset()):
        if span_id in seen or span_id not in by_id:
            return 0
        return 1 + max((depth(parent, seen | {span_id}) for parent in parents[span_id]), default=0)

    errors.sort(key=lambda s: (-depth(s.get("spanID")), s.get("startTime", 0), s.get("spanID", "")))
    origins = [s for s in errors if s.get("spanID") not in error_parents]
    timed_spans = [s for s in spans if isinstance(s.get("startTime"), (int, float))]
    start = min((s["startTime"] for s in timed_spans), default=0)
    end = max((s["startTime"] + s.get("duration", 0) for s in timed_spans), default=start)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return {"trace_id": trace["traceID"], "duration_ms": (end - start) / 1000,
            "started_at": (epoch + timedelta(microseconds=start)).isoformat() if timed_spans else None,
            "ended_at": (epoch + timedelta(microseconds=end)).isoformat() if timed_spans else None,
            "root_span": span_summary(root, processes),
            "first_error_span": span_summary(origins[0], processes) if origins else None,
            "origin_error_spans": [span_summary(s, processes) for s in origins],
            "error_spans": [span_summary(s, processes) for s in errors],
            "services": sorted(set(p.get("serviceName", "unknown") for p in processes.values()))}


@bounded("jaeger")
def list_services():
    raw = jaeger_json("/services", fetch=get_json)
    if raw.get("errors"):
        raise BackendError(str(raw["errors"]))
    services = [service for service in raw.get("data", []) if not is_sensitive(service)]
    return envelope("list_services", "jaeger", "services", window(), services)


@bounded("jaeger")
def get_traces(service, lookback_s=300, errors_only=True, limit=20, operation=None):
    span = window(lookback_s)
    if is_sensitive(service) or (operation and is_sensitive(operation)):
        raise ValueError("The requested selector contains excluded telemetry")
    requested = max(1, min(int(limit), 50))
    params = {"service": service, "limit": requested,
              "start": int(datetime.fromisoformat(span["from"]).timestamp() * 1e6),
              "end": int(datetime.fromisoformat(span["to"]).timestamp() * 1e6)}
    if errors_only:
        params["tags"] = json.dumps({"error": "true"})
    if operation:
        params["operation"] = operation
    raw = jaeger_json("/traces", params=params, fetch=get_json)
    if raw.get("errors"):
        raise BackendError(str(raw["errors"]))
    traces = raw.get("data") or []
    data, ids = [], []
    for trace in traces[:requested]:
        trace = scrub_trace(trace)
        if trace is None:
            continue
        summary = trace_summary(trace)
        if summary is None:
            continue
        data.append(summary)
        trace_id = "trace:" + trace["traceID"]
        ids.append(trace_id)
        capture_evidence(trace_id, "jaeger", trace)
        for origin in summary["origin_error_spans"]:
            span_id = origin["span_id"]
            evidence_id = f'span:{trace["traceID"]}/{span_id}'
            ids.append(evidence_id)
            observed_span = next(item for item in trace["spans"] if item.get("spanID") == span_id)
            capture_evidence(evidence_id, "jaeger", {
                **observed_span, "process": trace["processes"].get(observed_span.get("processID"), {})})
    return envelope("get_traces", "jaeger", json.dumps(params, sort_keys=True), span, data, ids,
                    len(traces) >= requested or limit > 50)
