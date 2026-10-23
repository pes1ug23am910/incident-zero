"""Read-only reset verification over a complete connector recovery window."""

from __future__ import annotations

import argparse
import json
import time

from tools import health_table
from .core import finite


def clean_sample(table, *, error_tolerance=0.001):
    if table.get("error") or not table.get("telemetry_available"):
        return False, "application telemetry is unavailable"
    rows = table.get("data", [])
    frontend = next((row for row in rows if row.get("service") == "frontend"), {})
    if not finite(frontend.get("rps")) or frontend["rps"] <= 0:
        return False, "no observed frontend traffic"
    if not finite(frontend.get("error_rate")):
        return False, "frontend error measurement is missing"
    failures = []
    for row in rows:
        name = row.get("service", "unknown")
        if row.get("status") != "running":
            failures.append(f"{name} container is not confirmed running")
        if row.get("oom_killed") or row.get("container_health") == "unhealthy":
            failures.append(f"{name} reports unhealthy state")
        if finite(row.get("error_rate")) and row["error_rate"] > error_tolerance:
            failures.append(f"{name} error rate {row['error_rate']:.4f}")
        if finite(row.get("rps")) and row["rps"] > 0 and not finite(row.get("error_rate")):
            failures.append(f"{name} has traffic but no error measurement")
    return not failures, "; ".join(failures) if failures else "live traffic, containers running, observed error rates cleared"


def wait_for_clean(*, run_dir=None, window_s=180, timeout_s=360, interval_s=30,
                   sample=health_table, clock=time.monotonic, sleep=time.sleep, progress=None):
    """Never return clean before 180 seconds and two consecutive clean samples."""
    if window_s < 180 or interval_s != 30 or timeout_s < window_s:
        raise ValueError("Recovery requires a >=180s window, 30s samples, and timeout >= window")
    started = clock()
    samples = []
    consecutive = 0
    next_sample = started
    while True:
        delay = next_sample - clock()
        if delay > 0:
            sleep(delay)
        table = sample(lookback_s=120, run_dir=run_dir)
        clean, reason = clean_sample(table)
        consecutive = consecutive + 1 if clean else 0
        elapsed = clock() - started
        point = {"elapsed_s": round(elapsed, 3), "clean": clean, "reason": reason,
                 "evidence_ids": table.get("evidence_ids", [])}
        samples.append(point)
        if progress:
            progress(point)
        if elapsed >= window_s and consecutive >= 2:
            return {"verified": True, "elapsed_s": round(elapsed, 3), "samples": samples}
        if elapsed >= timeout_s:
            return {"verified": False, "elapsed_s": round(elapsed, 3), "samples": samples,
                    "reason": "Error rates or container/telemetry readiness did not clear"}
        next_sample = min(next_sample + interval_s, started + timeout_s)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--timeout", type=float, default=360)
    args = parser.parse_args(argv)
    result = wait_for_clean(run_dir=args.run_id, timeout_s=args.timeout,
                            progress=lambda point: print(json.dumps(point), flush=True))
    print(json.dumps(result, indent=2))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
