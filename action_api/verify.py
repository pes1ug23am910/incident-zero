"""Fresh, traffic-qualified verification of every signal in the original alert."""
import math
import time
import requests
from .safety import Blocked, now

FIELDS = {"error_rate": "error_rate", "latency_p95": "p95_ms", "p95_ms": "p95_ms",
          "traffic": "rps", "rps": "rps", "container_health": "status",
          "container_status": "status"}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def signals(alert):
    items = alert.get("anomalies") or [alert]
    return [{"service": item["service"], "signal": item["signal"],
             "threshold": item.get("threshold", 0)} for item in items]


class LiveSampler:
    def load_snapshot(self):
        observation = {"load_state": None, "load_user_count": None,
                       "load_observed_at": None, "load_available": False}
        try:
            response = requests.get("http://localhost:8080/loadgen/stats/requests",
                                    timeout=10, headers={"Cache-Control": "no-cache"})
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                return observation
            state, users = payload.get("state"), payload.get("user_count")
            if not isinstance(state, str) or not state or len(state) > 40:
                return observation
            if type(users) is not int or users < 0:
                return observation
            observation.update(load_state=state, load_user_count=users,
                               load_observed_at=now(), load_available=state in {"running", "stopped"})
        except (requests.RequestException, ValueError, TypeError):
            pass
        return observation

    def __call__(self, alert, run_id):
        from tools import health_table, get_metrics
        table = health_table(lookback_s=120, run_dir=run_id)
        # SERVER spans avoid counting every RPC in the shopping trace as a user
        # request. Increase over 2m is a measured count, not a rate extrapolation.
        from tools.queries import named_query
        rate_query = named_query("rps_by_service")
        import re
        match = re.search(r"rate\(\s*([A-Za-z_:][A-Za-z0-9_:]*)\s*(?:\{[^{}]*\})?\s*\[2m\]\s*\)", rate_query)
        if not match:
            raise Blocked("VERIFICATION_UNAVAILABLE", 409)
        query = 'sum(increase(' + match[1] + '{service_name="frontend",span_kind="SPAN_KIND_SERVER"}[2m]))'
        counts = get_metrics(query, lookback_s=120, run_dir=run_id)
        points = [row["values"][-1] for row in counts.get("data", []) if row.get("values")]
        load = self.load_snapshot()
        observed_at = time.time()
        fresh = bool(points) and all(finite(point[0]) and 0 <= observed_at - point[0] <= 45
                                     and finite(point[1]) for point in points)
        rows = {row["service"]: row for row in table.get("data", [])}
        values = []
        for signal in signals(alert):
            field = FIELDS.get(signal["signal"])
            if field is None:
                raise Blocked("VERIFICATION_UNAVAILABLE", 409, "Unsupported alert signal; operator verification required")
            values.append(rows.get(signal["service"], {}).get(field))
        container_running = rows.get("load-generator", {}).get("status") == "running"
        return {"available": bool(table.get("telemetry_available")) and fresh and not table.get("error") and load['load_available'],
                "values": values, "requests_observed": sum(p[1] for p in points) if fresh else 0,
                **load, "load_container_running": container_running,
                "load_running": container_running and load['load_available'] and load['load_state'] == 'running' and load['load_user_count'] > 0,
                "evidence_ids": table.get("evidence_ids", []) + counts.get("evidence_ids", [])}


def evaluate(alert, sample):
    checks = signals(alert)
    values = sample.get("values", [])
    available = bool(sample.get("available")) and len(values) == len(checks)
    good = []
    for signal, value in zip(checks, values):
        field = FIELDS.get(signal["signal"])
        if field == "status":
            available &= isinstance(value, str)
            good.append(value == "running")
        else:
            available &= field is not None and finite(value) and finite(signal["threshold"])
            good.append(finite(value) and finite(signal["threshold"]) and value < signal["threshold"])
    requests = sample.get("requests_observed", 0)
    qualified = available and sample.get("load_running") is True and finite(requests) and requests >= 20
    return available, bool(qualified and good and all(good))


class Verifier:
    def __init__(self, sampler=None, clock=time.monotonic, sleep=time.sleep, window_s=180):
        if window_s < 180:
            raise ValueError("Verification window must be at least 180 seconds")
        self.sampler = sampler or LiveSampler()
        self.clock, self.sleep, self.window_s = clock, sleep, window_s

    def preflight(self, alert, run_id):
        try:
            sample = self.sampler(alert, run_id)
            available, _ = evaluate(alert, sample)
        except Exception as exc:
            raise Blocked("VERIFICATION_UNAVAILABLE", 409) from exc
        if not available or sample.get("load_running") is not True:
            raise Blocked("VERIFICATION_UNAVAILABLE", 409)
        return sample

    def verify(self, alert, run_id, check_stop, progress=None):
        start = self.clock()
        samples, consecutive = [], 0
        while True:
            check_stop()
            try:
                sample = self.sampler(alert, run_id)
            except Exception:
                sample = {"available": False, "values": [], "requests_observed": 0, "load_running": False}
            available, recovered = evaluate(alert, sample)
            consecutive = consecutive + 1 if recovered else 0
            elapsed = self.clock() - start
            point = {**sample, "elapsed_s": round(elapsed, 3), "qualified_recovery": recovered}
            samples.append(point)
            if progress:
                progress(point)
            # STOP may arrive during a telemetry request or progress callback,
            # including the final sample. Never publish recovery past that latch.
            check_stop()
            if elapsed >= self.window_s:
                outcome = "recovered" if consecutive >= 2 else "unresolved" if available else "blocked"
                return {"checked_at": now(), "signal": alert["signal"], "before": alert.get("observed"),
                        "after": sample["values"][0] if sample.get("values") and finite(sample["values"][0]) else (0 if recovered else 1),
                        "recovered": outcome == "recovered", "rolled_back": False, "outcome": outcome,
                        "requests_observed": sample.get("requests_observed", 0), "samples": samples}
            # One-second cancellation points; telemetry reads every 30 seconds.
            deadline = min(start + self.window_s, start + 30 * len(samples))
            while self.clock() < deadline:
                check_stop()
                self.sleep(min(1, deadline - self.clock()))
