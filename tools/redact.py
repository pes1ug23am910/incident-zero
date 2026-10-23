"""Remove incident-setting disclosures from telemetry; never read setting state.

This module contains a static denylist only. It performs no I/O and never imports
the injector. Names cover the demo's known incident controls and legacy aliases.
"""

import re


FLAG_NAMES = (
    "paymentFailure", "paymentUnreachable", "cartFailure", "productCatalogFailure",
    "recommendationCacheFailure", "adHighCpu", "adManualGc", "adFailure",
    "loadGeneratorFloodHomepage", "imageSlowLoad", "kafkaQueueProblems",
    "llmInaccurateResponse", "llmRateLimitError", "llmTimeoutError",
)
_SENSITIVE = re.compile(
    r"feature[_.\s-]*flag|flagd|defaultVariant|demo\.flagd\.json|ofrep|"
    r"(?:app|demo)\.recommendation\.cache_enabled|"
    r"High CPU-Load problempattern enabled|"
    + "|".join(re.escape(name) for name in FLAG_NAMES), re.IGNORECASE,
)
_CONTAINER_EVIDENCE = re.compile(
    r"container:([A-Za-z0-9][A-Za-z0-9_.-]*):(Status|RestartCount|OOMKilled|StartedAt|Created|NanoCpus|Memory|health)=([^\n]*)$"
)


def is_sensitive_evidence(identifier):
    """Container liveness/resource metadata is allowed for every demo container."""
    match = _CONTAINER_EVIDENCE.fullmatch(identifier)
    if match and (match[1] == "flagd" or not is_sensitive(match[1])) and not is_sensitive(match[3]):
        return False
    return is_sensitive(identifier)


def _safe_container_record(value):
    return ("Status" in value or "status" in value or
            value.get("field") in {"Status", "RestartCount", "OOMKilled", "StartedAt", "Created", "NanoCpus", "Memory", "health"} or
            value.get("kind") in {"Created", "StartedAt"})


def is_sensitive(value):
    """Recognize disclosure keys and values without consulting external state."""
    if isinstance(value, str):
        return bool(_SENSITIVE.search(value))
    if isinstance(value, dict):
        return any(is_sensitive(key) or is_sensitive(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(is_sensitive(item) for item in value)
    return False


def redact_text(text):
    """Drop a complete revealing log line, rather than leaving its setting value."""
    return None if is_sensitive(text) else text


def redact_metric_series(series):
    """Drop control metrics and series naming the control backend."""
    labels = series.get("metric", {})
    if is_sensitive(labels):
        return None
    return _clean_dict(series)


def scrub_trace(trace):
    """Remove backend spans, sensitive tags/events, and dangling references."""
    processes = trace.get("processes", {})
    blocked = {pid for pid, process in processes.items()
               if is_sensitive(process.get("serviceName", ""))}
    kept = []
    for span in trace.get("spans", []):
        if span.get("processID") in blocked or is_sensitive(span.get("operationName", "")):
            continue
        clean = _clean_dict(span)
        if clean:
            kept.append(clean)
    if not kept:
        return None
    allowed_ids = {span.get("spanID") for span in kept}
    for span in kept:
        if "references" in span:
            span["references"] = [ref for ref in span["references"]
                                  if ref.get("traceID") != trace.get("traceID")
                                  or ref.get("spanID") in allowed_ids]
    clean = _clean_dict({key: value for key, value in trace.items()
                         if key not in ("spans", "processes")})
    clean["spans"] = kept
    used = {span.get("processID") for span in kept}
    clean["processes"] = {pid: _clean_dict(process) for pid, process in processes.items()
                          if pid in used and pid not in blocked}
    return clean


def _clean_dict(value):
    clean = {}
    for key, item in value.items():
        if is_sensitive(key) and not (isinstance(key, str) and key.startswith("container:") and not is_sensitive_evidence(key)):
            continue
        if key in {"name", "service", "container"} and item == "flagd" and _safe_container_record(value):
            result = item
        elif key in {"id", "evidence_id"} and isinstance(item, str) and not is_sensitive_evidence(item):
            result = item
        elif key == "evidence_ids" and isinstance(item, list):
            result = [identifier for identifier in item if not is_sensitive_evidence(identifier)]
        else:
            result = _clean(item)
        if result is not None or item is None:
            clean[key] = result
        elif key in {"query", "message", "type"}:
            clean[key] = "[redacted]"
    return clean


def _clean(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (list, tuple)):
        return [result for item in value if (result := _clean(item)) is not None or item is None]
    if not isinstance(value, dict):
        return value
    if "spans" in value and "processes" in value:
        return scrub_trace(value)
    if "metric" in value and isinstance(value["metric"], dict):
        return redact_metric_series(value)
    if "key" in value and "value" in value and is_sensitive(value):
        return None
    if "fields" in value and is_sensitive(value["fields"]):
        return None
    if any(is_sensitive(value.get(key, "")) and not
           (key in {"name", "service", "container"} and value.get(key) == "flagd" and _safe_container_record(value))
           for key in ("body", "msg", "service", "serviceName", "name", "container", "operationName")):
        return None
    return _clean_dict(value)


def sanitize(value):
    """Return a fresh safe structure, retaining a tool envelope's required keys.

    List members containing disclosures are omitted; sensitive query/error text
    becomes a placeholder. Trace and metric records receive structural filtering.
    """
    return _clean(value)
