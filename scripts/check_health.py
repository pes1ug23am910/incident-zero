"""Read-only smoke assertions: missing measurements never establish recovery."""
import argparse
import json
import math
import time

from tools.summarize import health_table


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def satisfies(result, expectation):
    if result.get("error") or not result.get("telemetry_available"):
        return False
    rows = {row["service"]: row for row in result["data"]}
    if expectation == "payment-error":
        return any(finite(rows.get(name, {}).get("error_rate")) and rows[name]["error_rate"] > 0
                   for name in ("payment", "checkout"))
    frontend = rows.get("frontend", {})
    if not finite(frontend.get("rps")) or frontend["rps"] <= 0:
        return False
    for name in ("frontend", "payment", "checkout"):
        row = rows.get(name, {})
        if not finite(row.get("error_rate")) or row["error_rate"] > .01:
            return False
    for row in rows.values():
        if row["status"] not in ("running", "unknown"):
            return False
        if finite(row.get("error_rate")) and row["error_rate"] > .01:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", choices=("payment-error", "clean"), required=True)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    if args.timeout < 0:
        parser.error("--timeout must be nonnegative")
    start = time.monotonic()
    consecutive = 0
    while True:
        result = health_table(lookback_s=120)
        consecutive = consecutive + 1 if satisfies(result, args.expect) else 0
        if consecutive >= (2 if args.expect == "clean" else 1):
            print(json.dumps({"verified": True, "expect": args.expect,
                              "elapsed_s": round(time.monotonic()-start, 3), "health_table": result}, indent=2))
            return 0
        if time.monotonic() - start >= args.timeout:
            print(json.dumps({"verified": False, "expect": args.expect,
                              "reason": "Required telemetry or health condition was not observed",
                              "elapsed_s": round(time.monotonic()-start, 3), "health_table": result}, indent=2))
            return 1
        time.sleep(min(5, max(0, args.timeout - (time.monotonic()-start))))


if __name__ == "__main__":
    raise SystemExit(main())
