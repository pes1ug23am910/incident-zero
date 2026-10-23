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
from detect.recovery import wait_for_clean
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("incident", help="Operator incident name; used only for injection and report metadata")
    parser.add_argument("--svc")
    parser.add_argument("--thresholds")
    parser.add_argument("--alert-timeout", type=float, default=90)
    parser.add_argument("--clean-timeout", type=float, default=360)
    parser.add_argument("--report-id", help="Optional unique report bundle name; existing bundles are never replaced")
    args = parser.parse_args(argv)
    if not 0 <= args.alert_timeout <= 90 or args.clean_timeout < 180:
        parser.error("Alert timeout must be 0..90s and clean timeout at least 180s")
    os.environ.setdefault("DOCKER_HOST", "tcp://localhost:2375")
    os.environ.setdefault("DEMO_VERSION", "2.0.2")
    os.environ.setdefault("DOCKER_CONFIG", str(ROOT / ".build" / "docker"))
    if (ROOT / "STOP").exists():
        print("STOP exists; no incident was injected", file=sys.stderr)
        return 1
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    report_id = args.report_id or "-".join(part for part in (args.incident, args.svc, suffix) if part)
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
            detector.poll(run_dir=operator_run, debounce=False)
        with timed("inject", timings):
            inject_args = ["faultctl", "inject", args.incident]
            if args.svc:
                inject_args.extend(["--svc", args.svc])
            result = command(inject_args, structured=True, timeout=180)
            # Consume only the caller metadata from stdout. Observed symptoms
            # and the eventual diagnosis come exclusively from read-only tools.
            records = result.get("runs", [])
            if len(records) != 1:
                raise RuntimeError("Operator did not return one run identifier")
            run_dir = run_path(records[0]["run_id"], create=True)
            outcome["injection_run_id"] = run_dir.name
        with timed("wait_for_alert", timings):
            alert = wait_for_alert(detector, run_dir=run_dir, timeout_s=args.alert_timeout)
            if alert is None:
                raise RuntimeError("No observable threshold crossing within the 90-second alert window")
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
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        failed = True
        outcome["error"] = str(exc)
        print(str(exc), file=sys.stderr, flush=True)
    finally:
        try:
            with timed("reset_after", timings):
                command(["faultctl", "reset", "--timeout", "90"], structured=True, timeout=120)
                check_demo_unchanged()
            with timed("clear_after", timings):
                verification["after"] = require_clean(operator_run, args.clean_timeout)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            failed = True
            outcome["cleanup_error"] = str(exc)
            print("Cleanup not verified: " + str(exc), file=sys.stderr, flush=True)
        outcome.update(ok=not failed, stage_seconds=timings, recovery_verification=verification)
        (operator_run / "checkpoint2.json").write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
        if report_dir.is_dir():
            public = json.loads(json.dumps(outcome))
            for check in public.get("recovery_verification", {}).values():
                for sample in check.get("samples", []):
                    sample["evidence_count"] = len(sample.pop("evidence_ids", []))
            (report_dir / "checkpoint2.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in outcome.items() if key != "recovery_verification"}, indent=2))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
