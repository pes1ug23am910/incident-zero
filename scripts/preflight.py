"""Read-only readiness gate. Failures never trigger reset, repair or execution."""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time

from .platform_support import ROOT, environment, stamp, table


def memory_free():
    if sys.platform == "win32":
        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (key, ctypes.c_ulonglong) for key in (
                    "total", "available", "page_total", "page_available", "virtual_total",
                    "virtual_available", "extended")]
        state = Memory()
        state.length = ctypes.sizeof(state)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            raise OSError("Cannot read available RAM")
        return state.available
    values = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    return int(values["MemAvailable"].split()[0]) * 1024


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack-root", type=Path, default=ROOT,
                        help="checkout owning STOP, policy, attempts and the mounted overlay")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".build/preflight")
    parser.add_argument("--no-model", action="store_true", help="mark model gate FAIL without calling the provider")
    args = parser.parse_args(argv)
    environment()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    identity = stamp()
    stack = args.stack_root.resolve()
    rows, observed = [], {"captured_at": datetime.now(timezone.utc).isoformat(), "read_only": True}

    def check(name, operation):
        started = time.monotonic()
        try:
            ok, detail = operation()
            rows.append((name, "PASS" if ok else "FAIL", detail))
        except Exception as exc:
            # Never include provider exception bodies or credentials in logs.
            rows.append((name, "FAIL", type(exc).__name__ + ": check unavailable"))
        observed.setdefault("timings", {})[name] = round(time.monotonic() - started, 3)
        print(f"{rows[-1][1]:4} {name}: {rows[-1][2]}", flush=True)

    def docker(*args):
        if not args or args[0] not in {"ps", "inspect", "port", "stats", "logs", "version"}:
            raise ValueError("preflight permits Docker reads only")
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise RuntimeError("Docker read failed")
        return result.stdout

    import requests
    from tools import common
    # In particular, do not allow tools.common's docker-exec OpenSearch fallback.
    common.docker = docker
    session = requests.Session()
    session.trust_env = False

    def get(url, **kwargs):
        response = session.get(url, timeout=5, **kwargs)
        response.raise_for_status()
        return response.json()

    def prom(query):
        payload = get(common.prometheus() + "/api/v1/query", params={"query": query})
        if payload.get("status") != "success":
            raise ValueError("Prometheus query failed")
        return payload["data"]["result"]

    config = json.loads((ROOT / "faultctl/config.yaml").read_text())
    containers = {}

    def stack_ready():
        nonlocal containers
        records = json.loads(docker("inspect", *config["containers"].values()))
        containers = {row["Name"].lstrip("/"): row for row in records}
        running = sum(row["State"]["Running"] for row in records)
        observed["containers"] = [{"name": k, "status": v["State"]["Status"],
                                   "started_at": v["State"]["StartedAt"]} for k, v in containers.items()]
        return running == 21 and len(records) == 21, f"{running}/21 expected containers running"

    check("stack", stack_ready)

    def collector():
        record = containers["otel-collector"]["State"]
        age = time.time() - datetime.fromisoformat(record["StartedAt"].replace("Z", "+00:00")).timestamp()
        return record["Running"] and age > 120, f"collector uptime {age:.0f}s; needs >120s"

    check("collector", collector)
    calls = 'traces_span_metrics_calls_total{service_name="frontend",span_kind="SPAN_KIND_SERVER"}'
    check("application metrics", lambda: (bool(prom(calls)), "frontend SERVER application series must exist"))

    def fresh():
        values = prom("time() - max(timestamp(" + calls + "))")
        age = float(values[0]["value"][1]) if values else float("inf")
        return 0 <= age < 90, f"actual newest sample age {age:.1f}s; needs <90s"

    check("Prometheus freshness", fresh)
    check("Jaeger", lambda: ((n := len(common.jaeger_json("services").get("data", []))) >= 10,
                              f"{n} services; needs >=10"))
    check("OpenSearch", lambda: ("otel" in common.search_json("/_alias"), "otel index exists via published HTTP port"))

    from detect.core import Detector, load_thresholds
    from tools import health_table, get_metrics, get_traces, get_logs, get_container_health, get_deploy_history
    from tools.evidence import run_path
    directory = run_path("preflight-" + identity, create=True)
    detector = Detector(load_thresholds())
    health = {}

    def clean_detector():
        nonlocal health
        baseline = detector.prime_baseline(run_dir=directory)
        health = health_table(run_dir=directory)
        alert = detector.evaluate(health, debounce=False)
        observed.update(health=health, baseline_metrics=baseline, detector_alert=alert)
        return alert is None and health.get("telemetry_available") is True, (
            "detect.once path: no_alert for every service" if alert is None else
            "alerts: " + ", ".join(f"{x['service']}:{x['signal']}" for x in alert.get("anomalies", [])))

    check("clean detector", clean_detector)

    def traffic_health():
        history = get_metrics("p95_latency_by_service", lookback_s=720, run_dir=directory)
        cutoff = time.time() - 120
        baseline = {}
        for series in history.get("data", []):
            points = [v for t, v in series.get("values", []) if cutoff - 600 <= t <= cutoff and v is not None]
            if len(points) >= 3:
                baseline[series["metric"].get("service_name")] = statistics.median(points)
        observed["latency_baseline_metrics"] = history
        traffic = [r for r in health.get("data", []) if r.get("rps") is not None and r["rps"] > 0
                   and r["service"] != "load-generator"]
        bad = [r["service"] for r in traffic if r.get("error_rate") != 0 or r.get("p95_ms") is None
               or r["service"] not in baseline or r["p95_ms"] >= max(1500, 3 * baseline[r["service"]])]
        return bool(traffic) and not bad, f"{len(traffic)} traffic services; nonzero errors/missing baseline/high p95: {bad}"

    check("traffic health and baseline", traffic_health)
    tool_calls = [("metrics", lambda: get_metrics("rps_by_service", run_dir=directory)),
                  ("traces", lambda: get_traces("checkout", errors_only=False, limit=1, run_dir=directory)),
                  ("logs", lambda: get_logs("payment", limit=1, run_dir=directory)),
                  ("containers", lambda: get_container_health(run_dir=directory)),
                  ("history", lambda: get_deploy_history(run_dir=directory))]
    for name, call in tool_calls:
        def timed_read(call=call):
            start = time.monotonic()
            result = call()
            elapsed = time.monotonic() - start
            return not result.get("error") and elapsed < 5, f"{elapsed:.3f}s; needs <5s and no error"
        check("tool " + name, timed_read)

    def resolve_one():
        from tools.resolve import resolve
        ids = [i for i in health.get("evidence_ids", []) if i.startswith("container:")]
        if not ids:
            return False, "no observed container id to round-trip"
        result = resolve(ids[0], run_dir=directory)
        return result.get("data") is not None and result.get("resolved_from") == "live", "tools.resolve: " + result.get("resolved_from", "unknown")

    check("evidence resolver", resolve_one)

    def flags():
        active = stack / "faultctl/.state/flags/demo.flagd.json"
        pristine = stack / "faultctl/.pristine/demo.flagd.json"
        hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (active, pristine)]
        return hashes[0] == hashes[1], "operator-only byte comparison; settings never enter diagnosis"

    check("pristine overlay", flags)
    check("flagd overlay mount", lambda: (any(
        m["Destination"] == "/etc/flagd" and "faultctl" in m["Source"] and "/.state/flags" in m["Source"].replace("\\", "/")
        for m in containers["flagd"].get("Mounts", [])), "repository-owned overlay mounted at /etc/flagd"))
    check("STOP absent", lambda: (not (stack / "STOP").exists(), "checked stack owner's STOP file"))
    check("test mode absent", lambda: (os.environ.get("INCIDENT_ZERO_TEST") != "1", "INCIDENT_ZERO_TEST must not be 1"))

    def action_health():
        import yaml
        response = get("http://127.0.0.1:8787/health")
        policy = yaml.safe_load((stack / "action_api/policy.yaml").read_text())
        auto = response.get("auto_approve_tiers", policy.get("auto_approve_tiers"))
        return response.get("ok") is True and response.get("stopped") is False and auto == [], "health OK, STOP false, auto_approve_tiers empty (policy file if API omits it)"

    check("Action API", action_health)

    def attempts():
        # Read-only fallback diagnostics; missing H8 CLI is a failed readiness gate.
        db = stack / "runs/action-api/state.sqlite"
        if not db.is_file():
            return False, "attempt database missing; not verified"
        with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
            records = [json.loads(row[0]) for row in conn.execute("select value from attempts")]
        stuck = [r for r in records if r.get("phase") in {"executing", "verifying", "rolling_back"}]
        cooling = [r for r in records if time.time() - r.get("created", 0) < 300]
        if not (stack / "action_api/state.py").is_file():
            return False, f"H8 state check CLI missing; read-only DB: {len(stuck)} stuck, {len(cooling)} cooldown"
        result = subprocess.run([sys.executable, "-m", "action_api.state", "check"], cwd=stack,
                                capture_output=True, text=True, timeout=15)
        return result.returncode == 0 and not stuck and not cooling, f"state check exit {result.returncode}; {len(stuck)} stuck, {len(cooling)} cooldown"

    check("attempts and cooldown", attempts)

    def control_room():
        state = get("http://127.0.0.1:8787/api/stop")
        # A responding old process is not evidence that current code was loaded.
        started = state.get("started_at")
        revision = state.get("revision")
        current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=stack, capture_output=True, text=True).stdout.strip()
        fresh = bool(started) and revision == current
        if not fresh and sys.platform == "win32":
            probe = subprocess.run(["pwsh", "-NoProfile", "-Command",
                "$owner = (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction Stop | Select-Object -First 1).OwningProcess; "
                "(Get-Process -Id $owner -ErrorAction Stop).StartTime.ToUniversalTime().ToString('o')"],
                capture_output=True, text=True, timeout=15)
            if probe.returncode == 0:
                epoch = datetime.fromisoformat(probe.stdout.strip().replace("Z", "+00:00")).timestamp()
                sources = [p for folder in ("ui", "action_api", "agent") for p in (stack / folder).rglob("*.py")]
                fresh = bool(sources) and epoch >= max(p.stat().st_mtime for p in sources)
        return state.get("mode") == "real" and not state.get("stopped") and fresh, (
            "real server loaded after source changes (or matching API revision)" if fresh else
            "fresh real server not verified from process start/source times or API revision; operator restart required")

    check("fresh real Control Room", control_room)
    check("Locust", lambda: ((value := get("http://localhost:8080/loadgen/stats/requests")).get("state") == "running"
                              and value.get("user_count", 0) > 0, "Locust responds within 5s; running with positive users"))
    check("disk", lambda: ((free := shutil.disk_usage(ROOT).free / 2**30) > 5, f"{free:.2f} GiB free; needs >5"))
    check("RAM", lambda: ((free := memory_free() / 2**30) > 2, f"{free:.2f} GiB free; needs >2"))

    def model():
        from agent.llm_router import load_env
        env = load_env()
        if args.no_model:
            return False, "model probe skipped; not verified"
        key, selected = env.get("OPENROUTER_API_KEY"), env.get("OPENROUTER_MODEL")
        if not key or not selected:
            return False, "OpenRouter credential/model configuration missing"
        catalog = get("https://openrouter.ai/api/v1/models")
        ids = {r["id"] for r in catalog.get("data", [])}
        configured = [env.get(k) for k in ("OPENROUTER_MODEL", "OPENROUTER_FALLBACK_MODEL") if env.get(k)]
        if not all(m in ids for m in configured):
            return False, "configured OpenRouter model id not in provider catalogue"
        response = session.post("https://openrouter.ai/api/v1/chat/completions",
                                headers={"Authorization": "Bearer " + key},
                                json={"model": selected, "messages": [{"role": "user", "content": "Reply OK."}],
                                      "max_tokens": 16}, timeout=(5, 30))
        ok = response.ok and bool(response.json().get("choices"))
        return ok, f"model ids resolved; authenticated inference HTTP {response.status_code}; no key logged"

    check("models and OpenRouter", model)
    passed = all(row[1] == "PASS" for row in rows)
    final = f"{'PASS' if passed else 'FAIL'} preflight {identity}: {sum(r[1] == 'PASS' for r in rows)}/{len(rows)} checks"
    content = f"# Read-only preflight {identity}\n\n" + table(rows) + "\n" + final + "\n"
    (args.output_dir / (identity + ".md")).write_text(content, encoding="utf-8")
    observed.update(rows=rows, passed=passed, summary=final)
    (args.output_dir / (identity + ".json")).write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    print("\n" + content)
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
