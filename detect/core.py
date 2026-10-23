"""Threshold evaluation preserves every anomalous service and missing data."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import time

from tools import get_metrics, health_table

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Thresholds:
    error_rate: float = 0.05
    p95_ms: float = 1500
    restart_increase: int = 2
    restart_window_s: int = 300
    rps_multiplier: float = 3
    baseline_window_s: int = 600
    rate_window_s: int = 120
    debounce_s: int = 180
    cpu_percent: float = 90
    cpu_limit_saturation: float = 0.85
    resource_limit_reduction_ratio: float = 0.5
    memory_ratio: float = 0.95
    memory_growth_ratio: float = 1.25

    def __post_init__(self):
        for key, value in asdict(self).items():
            if not finite(value) or value <= 0:
                raise ValueError(f"{key} must be a positive finite number")
        if self.rate_window_s < 120:
            raise ValueError("rate_window_s must be at least 120 seconds")
        if self.error_rate > 1 or self.memory_ratio > 1 or self.resource_limit_reduction_ratio > 1:
            raise ValueError("Error and memory ratios cannot exceed one")
        if self.rate_window_s + self.baseline_window_s > 86400:
            raise ValueError("Combined rate and baseline window exceeds one day")


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_thresholds(path=None):
    """Read the intentionally flat numeric YAML without an extra parser dependency."""
    values = {}
    path = Path(path) if path else Path(__file__).with_name("thresholds.yaml")
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, separator, value = line.partition(":")
        if not separator or key.strip() in values:
            raise ValueError(f"Invalid or duplicate threshold at line {number}")
        values[key.strip()] = json.loads(value.strip())
    unknown = set(values) - {field.name for field in fields(Thresholds)}
    if unknown:
        raise ValueError("Unknown thresholds: " + ", ".join(sorted(unknown)))
    return Thresholds(**values)


def _container_value(table, row, field, *keys):
    for key in keys:
        if key in row:
            return row[key]
    prefix = f'container:{row["service"]}:{field}='
    for identifier in table.get("evidence_ids", []):
        if identifier.startswith(prefix):
            value = identifier[len(prefix):]
            try:
                return json.loads(value)
            except ValueError:
                return value
    return None


def _evidence_for(table, service):
    markers = (f"container:{service}:", f'service_name="{service}"', f'service="{service}"')
    return [identifier for identifier in table.get("evidence_ids", [])
            if any(marker in identifier for marker in markers)]


def anomalies(table, thresholds=None, *, baseline=None, restart_deltas=None, baseline_memory=None,
              baseline_limits=None):
    """Return all threshold crossings; no service or diagnosis is selected by name."""
    config = thresholds or Thresholds()
    baseline, restart_deltas = baseline or {}, restart_deltas or {}
    baseline_memory = baseline_memory or {}
    baseline_limits = baseline_limits or {}
    found = []
    for row in table.get("data", []):
        service = row.get("service")
        if not service:
            continue

        def add(signal, observed, threshold, window_s=None, prior=None):
            found.append({"signal": signal, "service": service, "observed": observed,
                          "threshold": threshold, "window_s": window_s or config.rate_window_s,
                          "baseline": prior, "evidence_ids": _evidence_for(table, service)})

        status = row.get("status")
        if status and status not in ("running", "unknown"):
            add("container_status", status, "running")
        if _container_value(table, row, "OOMKilled", "oom_killed", "OOMKilled") is True:
            add("oom_killed", True, False)
        if row.get("container_health", row.get("health")) == "unhealthy":
            add("container_health", "unhealthy", "healthy")
        delta = restart_deltas.get(service)
        if finite(delta) and delta >= config.restart_increase:
            add("restart_increase", delta, config.restart_increase, config.restart_window_s)
        for key, threshold in (("error_rate", config.error_rate), ("p95_ms", config.p95_ms)):
            value = row.get(key)
            if finite(value) and value >= threshold:
                add(key, value, threshold)
        rps, prior = row.get("rps"), baseline.get(service)
        if service == "frontend" and finite(rps) and finite(prior) and prior > 0:
            if rps >= prior * config.rps_multiplier:
                add("rps", rps, prior * config.rps_multiplier, prior=prior)
        cpu = row.get("cpu_percent")
        limit = _container_value(table, row, "NanoCpus", "cpu_limit_nanos", "NanoCpus")
        prior_limits = baseline_limits.get(service, {})
        for field, observed_limit in (("cpu_limit_nanos", limit), ("memory_limit_bytes",
                _container_value(table, row, "Memory", "memory_limit_bytes", "Memory"))):
            prior_limit = prior_limits.get(field)
            if (finite(observed_limit) and observed_limit > 0 and finite(prior_limit)
                    and (prior_limit == 0 or observed_limit <= prior_limit * config.resource_limit_reduction_ratio)):
                add(field + "_reduced", observed_limit,
                    prior_limit * config.resource_limit_reduction_ratio, prior=prior_limit)
        if finite(cpu) and cpu >= config.cpu_percent:
            add("cpu_percent", cpu, config.cpu_percent)
        if finite(cpu) and finite(limit) and limit > 0:
            saturation = cpu / (limit / 10_000_000)
            if saturation >= config.cpu_limit_saturation:
                add("cpu_limit_saturation", saturation, config.cpu_limit_saturation)
        memory = row.get("memory_mb")
        memory_limit = _container_value(table, row, "Memory", "memory_limit_bytes", "Memory")
        if finite(memory) and finite(memory_limit) and memory_limit > 0:
            ratio = memory * 1_000_000 / memory_limit
            prior_memory = baseline_memory.get(service)
            if (ratio >= config.memory_ratio and finite(prior_memory) and prior_memory > 0
                    and memory >= prior_memory * config.memory_growth_ratio):
                add("memory_ratio", ratio, config.memory_ratio)
    return found


def baseline_from_metrics(result, config):
    """Exclude the newest rate window so an emerging flood cannot define normal."""
    try:
        end = datetime.fromisoformat(result["window"]["to"]).timestamp() - config.rate_window_s
    except (KeyError, ValueError):
        return {}
    start = end - config.baseline_window_s
    result_values = {}
    for row in result.get("data", []):
        name = row.get("metric", {}).get("service_name", row.get("metric", {}).get("service"))
        values = [value for timestamp, value in row.get("values", [])
                  if start <= timestamp <= end and finite(value) and value > 0]
        # Require more than one export interval; one stale point is not a baseline.
        if name and len(values) >= 3:
            result_values[name] = statistics.median(values)
    return result_values


class Detector:
    def __init__(self, thresholds=None):
        self.thresholds = thresholds or Thresholds()
        self.history = defaultdict(deque)
        self.last_alert = {}
        self.baseline = {}
        self.baseline_memory = {}
        self.baseline_limits = {}
        self.last_health = None

    def prime_baseline(self, *, run_dir=None):
        response = get_metrics("rps_by_service", lookback_s=self.thresholds.baseline_window_s +
                               self.thresholds.rate_window_s, run_dir=run_dir)
        self.baseline = baseline_from_metrics(response, self.thresholds)
        return response

    def evaluate(self, table, *, now=None, debounce=True):
        now = time.time() if now is None else now
        self.last_health = table
        deltas = {}
        for row in table.get("data", []):
            service, count = row.get("service"), row.get("restarts")
            if service and finite(row.get("memory_mb")):
                self.baseline_memory.setdefault(service, row["memory_mb"])
            if service:
                limits = self.baseline_limits.setdefault(service, {})
                for key, field, aliases in (("cpu_limit_nanos", "NanoCpus", ("cpu_limit_nanos", "NanoCpus")),
                        ("memory_limit_bytes", "Memory", ("memory_limit_bytes", "Memory"))):
                    value = _container_value(table, row, field, *aliases)
                    if finite(value):
                        limits.setdefault(key, value)
            if not service or not finite(count):
                continue
            history = self.history[service]
            while history and history[0][0] < now - self.thresholds.restart_window_s:
                history.popleft()
            if history:
                deltas[service] = count - min(item[1] for item in history)
            history.append((now, count))
        found = anomalies(table, self.thresholds, baseline=self.baseline, restart_deltas=deltas,
                          baseline_memory=self.baseline_memory, baseline_limits=self.baseline_limits)
        eligible = [item for item in found if not debounce or
                    now - self.last_alert.get(item["service"], -math.inf) >= self.thresholds.debounce_s]
        if not eligible:
            return None
        if debounce:
            for item in eligible:
                self.last_alert[item["service"]] = now
        primary = eligible[0]
        signal = {"p95_ms": "latency_p95", "container_status": "container_health",
                  "oom_killed": "oom", "restart_increase": "restart_count", "rps": "traffic",
                  "cpu_percent": "resource_limits", "cpu_limit_saturation": "resource_limits",
                  "memory_ratio": "resource_limits", "cpu_limit_nanos_reduced": "resource_limits",
                  "memory_limit_bytes_reduced": "resource_limits"}.get(primary["signal"], primary["signal"])
        observed = primary["observed"] if finite(primary["observed"]) else 1
        threshold = primary["threshold"] if finite(primary["threshold"]) else 0
        return {"detected_at": datetime.fromtimestamp(now, timezone.utc).isoformat(), **primary,
                "signal": signal, "observed": observed, "threshold": threshold,
                "details": {"signal": primary["signal"], "observed": primary["observed"]},
                "anomalies": found, "telemetry_available": bool(table.get("telemetry_available")),
                "evidence_ids": list(dict.fromkeys(identifier for item in found for identifier in item["evidence_ids"])),
                "warnings": table.get("warnings", [])}

    def poll(self, *, run_dir=None, debounce=True):
        result = health_table(lookback_s=self.thresholds.rate_window_s, run_dir=run_dir)
        return self.evaluate(result, debounce=debounce)


def write_alert(alert, run_dir):
    from tools.evidence import run_path

    directory = run_path(run_dir, create=True)
    alert = {**alert, "run_id": directory.name}
    path = directory / "alert.json"
    path.write_text(json.dumps(alert, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path
