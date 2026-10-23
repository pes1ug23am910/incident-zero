"""Prometheus range reads with reproducible peak and latest-point evidence."""

from datetime import datetime
import json
import math

from .common import bounded, envelope, get_json, prometheus, window, BackendError
from .queries import QUERIES, named_query
from .redact import is_sensitive, redact_metric_series
from .evidence import capture_evidence


def metric_id(metric, point, query):
    labels = {k: str(v) for k, v in metric.items() if k != "__name__"}
    labels["__query__"] = query
    encoded = ",".join(f"{k}={json.dumps(v, ensure_ascii=True)}" for k, v in sorted(labels.items()))
    return f'metric:{metric.get("__name__", "query")}{{{encoded}}}@{point[0]}={point[1]}'


@bounded("prometheus")
def get_metrics(promql, lookback_s=300, step_s=15):
    span = window(lookback_s)
    if step_s <= 0:
        raise ValueError("step_s must be positive")
    query = named_query(promql) if promql in QUERIES else promql
    if not isinstance(query, str) or not query.strip() or len(query) > 8192:
        raise ValueError("A nonempty PromQL expression of at most 8192 characters is required")
    if is_sensitive(query):
        raise ValueError("The requested query contains excluded telemetry")
    step = max(float(step_s), math.ceil(lookback_s / 199))
    raw = get_json(prometheus() + "/api/v1/query_range", params={
        "query": query, "start": datetime.fromisoformat(span["from"]).timestamp(),
        "end": datetime.fromisoformat(span["to"]).timestamp(), "step": step})
    if raw.get("status") != "success":
        raise BackendError(str(raw.get("error", "Prometheus query failed")))
    series = [clean for item in raw.get("data", {}).get("result", [])
              if (clean := redact_metric_series(item)) is not None]
    truncated = len(series) > 20
    result, ids = [], []
    for item in series[:20]:
        values = item.get("values", [])
        truncated |= len(values) > 200
        points = [[ts, float(value) if math.isfinite(float(value)) else None]
                  for ts, value in values[:200]]
        numeric = [p for p in points if p[1] is not None]
        peak = max(numeric, key=lambda p: p[1]) if numeric else None
        evidence = metric_id(item.get("metric", {}), peak, query) if peak else None
        latest = metric_id(item.get("metric", {}), points[-1], query) if points and points[-1][1] is not None else None
        if evidence:
            ids.append(evidence)
            capture_evidence(evidence, "prometheus", {"metric": item.get("metric", {}),
                             "timestamp": peak[0], "value": peak[1], "query": query})
        if latest:
            ids.append(latest)
            capture_evidence(latest, "prometheus", {"metric": item.get("metric", {}),
                             "timestamp": points[-1][0], "value": points[-1][1], "query": query})
        result.append({"metric": item.get("metric", {}), "values": points,
                       "peak_evidence_id": evidence, "latest_evidence_id": latest})
    extra = {} if result else {"warning": "No metric series returned; telemetry is missing or the selector has no matches."}
    return envelope("get_metrics", "prometheus", query, span, result, ids, truncated, **extra)
