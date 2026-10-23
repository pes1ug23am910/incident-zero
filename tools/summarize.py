"""Join observable measurements without interpreting missing telemetry as healthy."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from .common import bounded, envelope, window
from .metrics import get_metrics
from .containers import get_container_health


@bounded("prometheus")
def health_table(lookback_s=120):
    span = window(lookback_s)
    queries = {"error_rate": "error_rate_by_service", "p95_ms": "p95_latency_by_service", "rps": "rps_by_service"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {key: pool.submit(copy_context().run, get_metrics, value, lookback_s)
                   for key, value in queries.items()}
        health_future = pool.submit(copy_context().run, get_container_health)
        results = {key: future.result() for key, future in futures.items()}
        health = health_future.result()
    rows = {}
    ids, warnings = [], []
    for item in health["data"]:
        rows[item["name"]] = {"service": item["name"], "error_rate": None, "p95_ms": None, "rps": None,
                              "restarts": item["RestartCount"], "status": item["Status"],
                              "cpu_percent": item["cpu_percent"], "memory_mb": item["memory_mb"]}
    for field, result in results.items():
        for series in result["data"]:
            name = series["metric"].get("service_name", series["metric"].get("service"))
            if not name:
                continue
            row = rows.setdefault(name, {"service": name, "error_rate": None, "p95_ms": None, "rps": None,
                                         "restarts": None, "status": "unknown", "cpu_percent": None, "memory_mb": None})
            values = series["values"]
            row[field] = values[-1][1] if values else None
            # Health reports the final point, whose proof must match that point.
            if series.get("latest_evidence_id"):
                ids.append(series["latest_evidence_id"])
        if result.get("error"):
            warnings.append(f"{field}: {result['error']['message']}")
        elif result.get("warning"):
            warnings.append(f"{field}: {result['warning']}")
    ids.extend(health["evidence_ids"])
    if health.get("error"):
        warnings.append("containers: " + health["error"]["message"])
    warnings.extend(health.get("warnings", []))
    return envelope("health_table", "prometheus", "named service queries + container health", span,
                    sorted(rows.values(), key=lambda r: r["service"]), ids,
                    any(r["truncated"] for r in results.values()), warnings=warnings,
                    telemetry_available=any(row["rps"] is not None for row in rows.values()))
