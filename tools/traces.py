"""Bounded summaries from the trace backend."""

import json
from datetime import datetime
from .common import bounded, envelope, get_json, jaeger, window, BackendError
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
    first_error = next((s for s in ordered if is_error(s)), None)
    start = min((s.get("startTime", 0) for s in spans), default=0)
    end = max((s.get("startTime", 0) + s.get("duration", 0) for s in spans), default=start)
    return {"trace_id": trace["traceID"], "duration_ms": (end - start) / 1000,
            "root_span": span_summary(root, processes),
            "first_error_span": span_summary(first_error, processes) if first_error else None,
            "services": sorted(set(p.get("serviceName", "unknown") for p in processes.values()))}


@bounded("jaeger")
def list_services():
    raw = get_json(jaeger() + "/services")
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
    raw = get_json(jaeger() + "/traces", params=params)
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
        if summary["first_error_span"]:
            span_id = summary["first_error_span"]["span_id"]
            evidence_id = f'span:{trace["traceID"]}/{span_id}'
            ids.append(evidence_id)
            observed_span = next(item for item in trace["spans"] if item.get("spanID") == span_id)
            capture_evidence(evidence_id, "jaeger", observed_span)
    return envelope("get_traces", "jaeger", json.dumps(params, sort_keys=True), span, data, ids,
                    len(traces) >= requested or limit > 50)
