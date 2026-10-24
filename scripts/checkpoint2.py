"""Operator rehearsal: reset, inject, detect, diagnose, validate, show, reset."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from detect.core import Detector, ROOT, load_thresholds, write_alert
from detect.recovery import clean_sample, wait_for_clean
from detect.watch import wait_for_alert
from tools.evidence import run_path


def command(arguments, *, structured=False, timeout=900):
    result = subprocess.run([sys.executable, "-m", *arguments], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        # The operator's mutation output contains settings and is never copied
        # into an alert or report. Print only a bounded failure message here.
        if arguments[0] == "faultctl":
            raise RuntimeError(f"Operator {arguments[1]} failed (exit {result.returncode}); run that command directly for diagnostics")
        raise RuntimeError((result.stderr or result.stdout)[-2000:])
    if structured:
        return json.loads(result.stdout)
    if result.stdout.strip():
        print(result.stdout.strip(), flush=True)
    return result.stdout


@contextmanager
def timed(name, timings):
    started = time.monotonic()
    print(f"[{name}] starting", flush=True)
    try:
        yield
    finally:
        timings[name] = round(time.monotonic() - started, 3)
        print(f"[{name}] {timings[name]:.3f} seconds", flush=True)


def require_clean(run_dir, timeout):
    result = wait_for_clean(run_dir=run_dir, timeout_s=timeout,
        progress=lambda point: print(f"  +{point['elapsed_s']:.1f}s clean={point['clean']}: {point['reason']}", flush=True))
    if not result["verified"]:
        raise RuntimeError("Reset returned, but live error-rate clearance was not verified")
    return result


def check_demo_unchanged():
    directory = os.environ.get("INCIDENT_ZERO_DEMO_DIR", r"D:\opentelemetry-demo")
    result = subprocess.run(["git", "-c", "safe.directory=" + directory.replace("\\", "/"),
                             "-C", directory, "status", "--porcelain"],
                            capture_output=True, text=True, timeout=10)
    if result.returncode or result.stdout.strip():
        raise RuntimeError("Official demo checkout is not confirmed clean after reset")


def observed_no_alert(detector):
    """Describe an observed clean baseline without supplying a diagnosis."""
    table = detector.last_health or {}
    clean, reason = clean_sample(table)
    if not clean:
        raise RuntimeError("No-alert observation requires healthy live telemetry: " + reason)
    frontend = next(row for row in table["data"] if row.get("service") == "frontend")
    return {"detected_at": datetime.now(timezone.utc).isoformat(),
            "signal": "no_alert", "service": "frontend",
            "observed": frontend["error_rate"], "threshold": detector.thresholds.error_rate,
            "window_s": detector.thresholds.rate_window_s, "baseline": None,
            "anomalies": [], "telemetry_available": table["telemetry_available"],
            "evidence_ids": table.get("evidence_ids", []), "warnings": table.get("warnings", [])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("incident", nargs="?", help="Operator incident name, no-fault, or optional combination label; metadata only")
    parser.add_argument("--combo", help="Comma-separated operator incidents applied together before observation")
    parser.add_argument("--svc")
    parser.add_argument("--thresholds")
    # Keep wrappers and the direct module within this branch's watcher contract.
    parser.add_argument("--alert-timeout", type=float, default=90)
    parser.add_argument("--clean-timeout", type=float, default=360)
    parser.add_argument("--report-id", help="Optional unique report bundle name; existing bundles are never replaced")
    args = parser.parse_args(argv)
    if not args.incident and not args.combo:
        parser.error("Provide an incident, no-fault, or --combo")
    if args.combo and args.incident == "no-fault":
        parser.error("no-fault cannot be combined with injection")
    combination = [item.strip() for item in args.combo.split(",")] if args.combo else []
    if args.combo and (len(combination) < 2 or not all(combination) or len(set(combination)) != len(combination)):
        parser.error("--combo requires at least two distinct nonempty incident names")
    if args.incident == "no-fault" and args.svc:
        parser.error("no-fault does not select an injection service")
    if not 0 <= args.alert_timeout <= 90 or args.clean_timeout < 180:
        parser.error("Alert timeout must be 0..90s and clean timeout at least 180s")
    from scripts.platform_support import environment
    environment()
    os.environ.setdefault("DEMO_VERSION", "2.0.2")
    os.environ.setdefault("DOCKER_CONFIG", str(ROOT / ".build" / "docker"))
    if (ROOT / "STOP").exists():
        print("STOP exists; no incident was injected", file=sys.stderr)
        return 1
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    report_id = args.report_id or "-".join(part for part in (args.incident or "combo", args.svc, suffix) if part)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", report_id):
        parser.error("Report id must be a filename-safe identifier of at most 200 characters")
    report_dir = ROOT / "reports" / report_id
    if report_dir.exists():
        parser.error("Report bundle already exists; use a new --report-id")
    timings = {}
    verification = {}
    operator_run = run_path("rehearsal-" + suffix, create=True)
    run_dir = operator_run
    outcome = {"incident_id": report_id}
    failed = False
    # Cleanup runs even if injection partially succeeds or any later stage fails.
    try:
        with timed("reset_before", timings):
            command(["faultctl", "reset", "--timeout", "90"], structured=True, timeout=120)
            check_demo_unchanged()
        with timed("clear_before", timings):
            verification["before"] = require_clean(operator_run, args.clean_timeout)
        detector = Detector(load_thresholds(args.thresholds))
        with timed("baseline", timings):
            detector.prime_baseline(run_dir=operator_run)
            existing_alert = detector.poll(run_dir=operator_run, debounce=False)
            if existing_alert is not None:
                crossings = ", ".join(f"{item.get('service', 'unknown')}:{item.get('signal', 'unknown')}"
                                      for item in existing_alert.get("anomalies", []))
                raise RuntimeError("Unexpected preexisting baseline anomalies; injection refused: " + (crossings or "threshold crossing"))
        if args.incident == "no-fault":
            with timed("observe_no_alert", timings):
                path = write_alert(observed_no_alert(detector), run_dir)
                outcome["injection_run_ids"] = []
        else:
            with timed("inject", timings):
                inject_args = ["faultctl", "inject"]
                inject_args.extend(["--combo", ",".join(combination)] if combination else [args.incident])
                if args.svc:
                    inject_args.extend(["--svc", args.svc])
                result = command(inject_args, structured=True, timeout=180)
                # Consume only caller metadata. Observations and diagnosis never
                # receive injection settings or the expected cause set.
                records = result.get("runs", [])
                expected_count = len(combination) if combination else 1
                if len(records) != expected_count:
                    raise RuntimeError(f"Operator did not return {expected_count} run identifier(s)")
                injection_runs = [run_path(record["run_id"], create=True) for record in records]
                run_dir = injection_runs[-1]
                outcome["injection_run_id"] = run_dir.name
                outcome["injection_run_ids"] = [directory.name for directory in injection_runs]
            with timed("wait_for_alert", timings):
                alert = wait_for_alert(detector, run_dir=run_dir, timeout_s=args.alert_timeout)
                if alert is None:
                    raise RuntimeError(f"No observable threshold crossing within the {args.alert_timeout}-second alert window")
                path = write_alert(alert, run_dir)
        with timed("agent", timings):
            command(["agent.run", "--alert", str(path), "--incident-id", report_id,
                     "--out", str(report_dir / "report.json")])
        with timed("validate", timings):
            command(["schema.validate", str(report_dir / "report.json")], timeout=180)
        with timed("print_report", timings):
            markdown = report_dir / "report.md"
            if not markdown.exists():
                command(["reports.render", str(report_dir / "report.json")])
            print(markdown.read_text(encoding="utf-8"), flush=True)
            outcome["report_path"] = str(markdown)
    except Exception as exc:
        failed = True
        outcome["error"] = str(exc)
        print(str(exc), file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        failed = True
        outcome["error"] = "KeyboardInterrupt: rehearsal interrupted"
        raise
    finally:
        cleanup_interrupted = False
        try:
            with timed("reset_after", timings):
                command(["faultctl", "reset", "--timeout", "90"], structured=True, timeout=120)
                check_demo_unchanged()
            with timed("clear_after", timings):
                verification["after"] = require_clean(operator_run, args.clean_timeout)
        except Exception as exc:
            failed = True
            outcome["cleanup_error"] = str(exc)
            print("Cleanup not verified: " + str(exc), file=sys.stderr, flush=True)
        except KeyboardInterrupt:
            failed = True
            cleanup_interrupted = True
            outcome["cleanup_error"] = "KeyboardInterrupt: cleanup interrupted; recovery is not verified"
        outcome.update(ok=not failed, stage_seconds=timings, recovery_verification=verification)
        (operator_run / "checkpoint2.json").write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
        if report_dir.is_dir():
            public = json.loads(json.dumps(outcome))
            for check in public.get("recovery_verification", {}).values():
                for sample in check.get("samples", []):
                    sample["evidence_count"] = len(sample.pop("evidence_ids", []))
            (report_dir / "checkpoint2.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in outcome.items() if key != "recovery_verification"}, indent=2))
        if cleanup_interrupted:
            raise KeyboardInterrupt
    return int(failed)


if __name__ == "__main__":
    # Redirected Windows output otherwise uses the legacy code page, which can
    # reject valid Unicode in a model's Markdown after diagnosis has succeeded.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    os.environ["PYTHONIOENCODING"] = "utf-8"
    raise SystemExit(main())
