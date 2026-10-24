"""Common implementation for the PowerShell and bash operator entry points."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .platform_support import ROOT, environment, run_module, stamp


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    up = commands.add_parser("up", help="install dependencies, start the official demo, check clean detection")
    up.add_argument("--demo-dir", default=os.environ.get("INCIDENT_ZERO_DEMO_DIR", str(ROOT.parent / "opentelemetry-demo")))
    cp2 = commands.add_parser("checkpoint2", help="reset, inject, diagnose, validate, reset; CHANGES STACK")
    cp2.add_argument("incident", nargs="?")
    cp2.add_argument("--combo")
    cp2.add_argument("--svc")
    cp2.add_argument("--report-id")
    cp2.add_argument("--alert-timeout", type=int, default=150)
    cp2.add_argument("--clean-timeout", type=int, default=360)
    cp3 = commands.add_parser("checkpoint3", help="full loop with real approval; CHANGES STACK")
    cp3.add_argument("incident")
    demo = commands.add_parser("demo", help="preview by default; --live CHANGES STACK")
    demo.add_argument("--live", action="store_true")
    demo.add_argument("--incident", default="payment-failure")
    demo.add_argument("--rejected-report")
    for command in (cp3, demo):
        command.add_argument("--svc")
        command.add_argument("--report-id")
        command.add_argument("--operator", default="Yash Verma")
        command.add_argument("--load-users", type=int, choices=range(1, 101), default=20, metavar="1..100")
        command.add_argument("--browser-approval", action="store_true")
    ui = commands.add_parser("ui", help="start the Control Room, mock by default")
    ui.add_argument("--mode", choices=("mock", "real"), default="mock")
    ui.add_argument("--reports-dir")
    ui.add_argument("--runs-dir")
    ui.add_argument("--port", type=int)
    args = parser.parse_args(argv)
    environment()
    if args.command == "up":
        os.environ["INCIDENT_ZERO_DEMO_DIR"] = args.demo_dir
        install = ([shutil.which("uv"), "pip", "install", "--python", sys.executable, "-e", ".[test]"]
                   if shutil.which("uv") else [sys.executable, "-m", "pip", "install", "-e", ".[test]"])
        if subprocess.call(install, cwd=ROOT):
            return 1
        for operation in ("up", "build-netem", "status"):
            if run_module("faultctl", operation):
                return 1
        from detect.core import Detector
        detector = Detector()
        detector.prime_baseline()
        alert = detector.poll(debounce=False)
        clean = alert is None and (detector.last_health or {}).get("telemetry_available") is True
        print("PASS clean-stack detect.once: no_alert" if clean else "FAIL clean-stack detector; do not rehearse")
        return int(not clean)
    if args.command == "ui":
        options = ["--mode", args.mode]
        for key in ("reports_dir", "runs_dir", "port"):
            if getattr(args, key):
                options += ["--" + key.replace("_", "-"), str(getattr(args, key))]
        return run_module("ui.serve", *options)
    if args.command == "demo" and not args.live:
        print("Preview: use --live for a real human-approved demonstration.")
        print("Preparation: reset, >=180s clean traffic, inject, detect, diagnose; wait for PRESENTATION READY.")
        print("0:00-0:45 review alert/evidence and approve once in terminal or browser.")
        print("0:45-4:30 execute and verify >=180s; show the report and action log.")
        print("4:30-5:00 show BLOCK (403), STOP, and a stopped allowed dry run (423).")
        print("Afterwards: operator reset, >=180s clean traffic, explicit STOP clear phrase.")
        print("Injection and diagnosis occur before the five-minute clock; verification is never shortened.")
        return 0
    if os.environ.get("INCIDENT_ZERO_TEST") == "1":
        parser.error("Unset INCIDENT_ZERO_TEST; mentor wrappers require real approval")
    if args.command == "checkpoint2" and not args.incident and not args.combo:
        parser.error("checkpoint2 requires an incident or --combo")
    if args.command in {"checkpoint2", "checkpoint3", "demo"}:
        if run_module("scripts.preflight"):
            print("Preflight failed; rehearsal refused before any injection/reset.")
            return 1
    if args.command == "checkpoint2":
        options = [args.incident] if args.incident else []
        for key in ("combo", "svc", "report_id", "alert_timeout", "clean_timeout"):
            value = getattr(args, key)
            if value is not None:
                options += ["--" + key.replace("_", "-"), str(value)]
        return run_module("scripts.checkpoint2", *options)
    identity = args.report_id or ("demo-" if args.command == "demo" else "checkpoint3-") + stamp().replace(".", "-")
    options = [args.incident, "--live", "--operator", args.operator,
               "--ensure-control-room", "--load-users", str(args.load_users), "--report-id", identity]
    if args.svc:
        options += ["--svc", args.svc]
    if args.browser_approval:
        options += ["--approval-mode", "browser"]
    if args.command == "checkpoint3":
        return run_module("scripts.hands_rehearsal", *options)
    # Same preparation/presentation/cleanup contract on both shells.
    if args.rejected_report:
        report = json.loads(Path(args.rejected_report).read_text(encoding="utf-8"))
        if report.get("impact", {}).get("tier") != 2:
            parser.error("--rejected-report must identify a real tier-2 report")
    failed = 0
    try:
        failed = run_module("scripts.hands_rehearsal", *options, "--defer-cleanup", "--presentation-ready")
        if not failed and args.rejected_report:
            failed = run_module("agent.respond", "--report", args.rejected_report, "--operator", args.operator, "--reject")
        if not failed:
            failed = run_module("scripts.show_block", "--operator", args.operator)
    finally:
        failed |= run_module("faultctl", "reset", "--timeout", "90")
        from scripts.hands_rehearsal import require_clean, check_demo_unchanged
        from tools.evidence import run_path
        check_demo_unchanged()
        cleanup = require_clean(run_path(create=True), 360)
        path = ROOT / "reports" / identity / "demo-cleanup.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cleanup, indent=2) + "\n", encoding="utf-8")
        if (ROOT / "STOP").exists():
            failed |= run_module("action_api", "clear-stop", "--operator", args.operator)
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
