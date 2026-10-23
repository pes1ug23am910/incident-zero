"""Operator full-loop rehearsal with retained measurements and final cleanup."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

import requests

from scripts.checkpoint2 import command, check_demo_unchanged, timed
from detect.core import Detector, write_alert
from detect.watch import wait_for_alert
from detect.recovery import clean_sample, wait_for_clean
from tools import health_table
from tools.evidence import run_path
from agent.respond import resume, save_bundle
from action_api.service import ActionService
from action_api.verify import LiveSampler, evaluate
from schema.validate import validate_report

ROOT = Path(__file__).resolve().parents[1]
CONTROL_ROOM = "http://127.0.0.1:8787"


def require_clean(directory, timeout):
    """Verify reset health and measured traffic in the same >=180s window."""
    alert = {"signal": "error_rate", "service": "frontend", "threshold": .001}
    sampler = LiveSampler()
    latest = {}

    def sample(**kwargs):
        table = health_table(**kwargs)
        measured = sampler(alert, directory)
        available, qualified = evaluate(alert, measured)
        latest.update(requests_observed=measured.get("requests_observed", 0),
                      load_running=measured.get("load_running") is True,
                      qualified_traffic=available and qualified)
        result = {**table, "evidence_ids": table.get("evidence_ids", []) + measured.get("evidence_ids", [])}
        if not qualified:
            result["error"] = "Recovery needs >=20 measured requests, running load generator and fresh low-error telemetry"
        return result

    def progress(point):
        point.update(latest)
        print(f"  +{point['elapsed_s']:.1f}s clean={point['clean']} requests={point['requests_observed']:.1f} load_running={point['load_running']}: {point['reason']}", flush=True)

    result = wait_for_clean(run_dir=directory, timeout_s=timeout, sample=sample, progress=progress)
    if not result["verified"]:
        raise RuntimeError("Reset returned, but traffic-qualified recovery was not verified")
    return result


def next_report_id(incident, root=ROOT):
    for number in range(1, 100000):
        name = f"{incident}-loop-r{number}"
        if not (Path(root) / "reports" / name).exists():
            return name
    raise ValueError("No unused rehearsal report ID")


def set_operator_load(executor, values):
    """Apply explicit rehearsal setup/cleanup, outside agent authorization."""
    response = requests.post(executor.load_url + "/swarm", data={
        "user_count": values["users"], "spawn_rate": values["spawn_rate"]}, timeout=10)
    response.raise_for_status()
    if response.json().get("success") is not True:
        raise RuntimeError("Locust did not confirm the operator load setting")


def ensure_control_room(root=ROOT):
    """Reuse a real local API, or start one hidden and leave it available."""
    def probe():
        try:
            response = requests.get(CONTROL_ROOM + "/api/stop", timeout=2)
        except requests.ConnectionError:
            return False
        response.raise_for_status()
        if response.json().get("mode") != "real":
            raise RuntimeError("Port 8787 is occupied by a non-real Control Room")
        return True

    if probe():
        return
    logs = Path(root) / ".build"
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / "control-room.log").open("ab") as output:
        process = subprocess.Popen([sys.executable, "-m", "ui.serve", "--mode", "real"],
            cwd=root, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Real Control Room failed to start; inspect .build/control-room.log")
        if probe():
            return
        time.sleep(.5)
    raise RuntimeError("Real Control Room did not become ready within 30 seconds")


def wait_for_browser(report_path, run_id, service, timeout_s=1200):
    print(f"Approve or reject this run in {CONTROL_ROOM}; waiting for its saved final report.", flush=True)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            report = json.loads(Path(report_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(.5)
            continue
        if report.get("run_id") != run_id:
            raise RuntimeError("Browser response changed the report run ID")
        if report.get("action_history") or report.get("status") == "aborted":
            return report
        time.sleep(.5)
    raise RuntimeError("Browser approval/verification did not finish within 1200 seconds")


class RunControl:
    """Explicit operator interventions; neither modifies the real verifier."""
    def __init__(self, service, run_id, *, stop_delay=None, force_nonrecovery=False):
        self.service, self.run_id = service, run_id
        self.stop_delay, self.force_nonrecovery = stop_delay, force_nonrecovery
        self.cancelled = threading.Event()
        self.thread = None
        self.interventions = []
        self.error = None
        self.previous_load = None
        self.load_stopped = False

    def start(self):
        if self.force_nonrecovery:
            self.previous_load = self.service.executor.load_state()
            if self.previous_load.get("users", 0) < 1:
                raise RuntimeError("Forced non-recovery requires an initially active Locust swarm")
        if self.stop_delay is not None or self.force_nonrecovery:
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def _run(self):
        try:
            while not self.cancelled.wait(.2):
                attempts = [item for item in self.service.attempts() if item["report_id"] == self.run_id]
                if self.force_nonrecovery and any(item["phase"] == "verifying" for item in attempts):
                    # Stop only the swarm after the executor captured its world.
                    self.load_stopped = True
                    response = requests.get(self.service.executor.load_url + "/stop", timeout=10)
                    response.raise_for_status()
                    if response.json().get("success") is not True:
                        raise RuntimeError("Locust did not confirm the operator swarm stop")
                    self.interventions.append({"at": datetime.now(timezone.utc).isoformat(),
                        "operation": "stop_locust_swarm", "purpose": "Test refusal to claim recovery without measured traffic",
                        "verifier_overridden": False})
                    return
                if self.stop_delay is not None and any(item["phase"] in ("executing", "verifying") for item in attempts):
                    if not self.cancelled.wait(self.stop_delay):
                        self.service.stop("Operator-requested demonstration timer")
                        self.interventions.append({"at": datetime.now(timezone.utc).isoformat(),
                            "operation": "STOP", "delay_after_execution_s": self.stop_delay})
                    return
        except Exception as exc:
            self.error = str(exc)

    def finish(self):
        self.cancelled.set()
        if self.thread:
            self.thread.join(12)
        if self.load_stopped:
            # This is operator cleanup, like reset, even when STOP is latched.
            response = requests.post(self.service.executor.load_url + "/swarm", data={
                "user_count": self.previous_load["users"], "spawn_rate": self.previous_load["spawn_rate"]}, timeout=10)
            response.raise_for_status()
            if response.json().get("success") is not True:
                raise RuntimeError("Locust did not confirm restoration of the captured swarm")
            self.interventions.append({"at": datetime.now(timezone.utc).isoformat(),
                "operation": "restore_locust_swarm", "users": self.previous_load["users"],
                "spawn_rate": self.previous_load["spawn_rate"]})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("incident")
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--svc")
    parser.add_argument("--report-id")
    parser.add_argument("--operator", default="Yash Verma")
    parser.add_argument("--reject", action="store_true")
    parser.add_argument("--auto-approve-for-tests", action="store_true")
    parser.add_argument("--force-nonrecovery", action="store_true", help="Test only: stop the Locust swarm after execution, then restore it")
    parser.add_argument("--stop-after-seconds", type=float)
    parser.add_argument("--approval-mode", choices=("terminal", "browser"), default="terminal")
    parser.add_argument("--ensure-control-room", action="store_true")
    parser.add_argument("--load-users", type=int, help="Operator setup: capture the swarm, use this many users/spawn 5, restore it during cleanup")
    parser.add_argument("--prepared-stack", action="store_true", help="Outer demo driver already verified a complete clean window")
    parser.add_argument("--defer-cleanup", action="store_true", help="Outer demo driver owns reset and clean verification in finally")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", args.incident):
        parser.error("incident must be a safe metadata slug")
    args.report_id = args.report_id or next_report_id(args.incident, ROOT)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", args.report_id):
        parser.error("report-id must be a safe metadata slug")
    bundle = ROOT / "reports" / args.report_id
    if bundle.exists():
        parser.error("Report bundle exists; use a fresh id")
    if (ROOT / "STOP").exists():
        parser.error("STOP is latched; only an operator may clear it")
    if args.stop_after_seconds is not None and not 0 < args.stop_after_seconds <= 180:
        parser.error("STOP delay must be >0 and <=180 seconds")
    if args.load_users is not None and not 1 <= args.load_users <= 100:
        parser.error("Operator load must be 1..100 users")
    if args.auto_approve_for_tests != (os.environ.get("INCIDENT_ZERO_TEST") == "1"):
        parser.error("Test approval requires BOTH INCIDENT_ZERO_TEST=1 and --auto-approve-for-tests; unset both for the demo")
    if args.force_nonrecovery and (not args.auto_approve_for_tests or args.stop_after_seconds is not None):
        parser.error("Forced non-recovery requires explicit test approval and cannot be combined with STOP")
    if args.approval_mode == "browser" and (args.auto_approve_for_tests or args.reject):
        parser.error("Browser mode collects the real browser decision; do not combine it with terminal test/rejection switches")
    os.environ.setdefault("DOCKER_HOST", "tcp://localhost:2375")
    os.environ.setdefault("DOCKER_CONFIG", str(ROOT / ".build/docker"))
    os.environ.setdefault("DEMO_VERSION", "2.0.2")
    directory = run_path(create=True)
    bundle.mkdir(parents=True)
    timings, verification = {}, {}
    outcome = {"incident_id": args.report_id, "approval_path": "test_auto" if args.auto_approve_for_tests else args.approval_mode,
               "test_auto_approval": args.auto_approve_for_tests, "forced_traffic_loss": args.force_nonrecovery,
               "operator_run_id": directory.name}
    failed, interrupted = False, False
    control = None
    load_executor = None
    previous_load = None
    try:
        if args.ensure_control_room or args.approval_mode == "browser":
            ensure_control_room(ROOT)
        print(f"Control Room: {CONTROL_ROOM}\nBundle: {bundle}", flush=True)
        if args.load_users is not None:
            load_executor = ActionService(ROOT).executor
            previous_load = load_executor.load_state()
            requested_load = {"users": args.load_users, "spawn_rate": 5}
            outcome["operator_load"] = {"before": previous_load, "requested": requested_load,
                "restored": False, "purpose": "Ensure the rehearsal has active charge traffic before its measured baseline"}
            set_operator_load(load_executor, requested_load)
        if args.prepared_stack:
            clean, reason = clean_sample(health_table(lookback_s=120, run_dir=directory))
            if not clean:
                raise RuntimeError("Prepared stack no longer clean: " + reason)
            verification["before"] = {"verified_by_outer_driver": True, "current_sample_clean": True, "reason": reason}
        else:
            with timed("reset_before", timings):
                command(["faultctl", "reset", "--timeout", "90"], structured=True)
                check_demo_unchanged()
            with timed("clear_before", timings):
                verification["before"] = require_clean(directory, 360)
        detector = Detector()
        detector.prime_baseline(run_dir=directory)
        if detector.poll(run_dir=directory, debounce=False) is not None:
            raise RuntimeError("Preexisting baseline anomaly; injection refused")
        started = time.monotonic()
        injection = ["faultctl", "inject", args.incident]
        if args.svc:
            injection += ["--svc", args.svc]
        with timed("injection", timings):
            command(injection, structured=True)
        alert = wait_for_alert(detector, run_dir=directory, timeout_s=90)
        if alert is None:
            raise RuntimeError("No alert within 90 seconds; no diagnosis or recovery claimed")
        path = write_alert(alert, directory)
        timings["inject_to_alert_s"] = round(time.monotonic() - started, 3)
        with timed("agent", timings):
            command(["agent.run", "--alert", str(path), "--incident-id", args.report_id, "--out", str(bundle / "report.json")])
        report = json.loads((bundle / "report.json").read_text(encoding="utf-8"))
        print((bundle / "report.md").read_text(encoding="utf-8"), flush=True)
        timings["inject_to_report_s"] = round(time.monotonic() - started, 3)
        final = report
        if report.get("proposed_actions"):
            service = ActionService(ROOT)
            control = RunControl(service, report["run_id"], stop_delay=args.stop_after_seconds, force_nonrecovery=args.force_nonrecovery)
            control.start()
            with timed("approval_execute_verify", timings):
                if args.approval_mode == "browser":
                    final = wait_for_browser(bundle / "report.json", report["run_id"], service)
                else:
                    final = resume(report, {"decision": "reject"} if args.reject else None,
                        root=ROOT, service=service, operator=args.operator,
                        auto_approve_for_tests=args.auto_approve_for_tests, report_path=bundle / "report.json")
                    save_bundle(final, bundle / "report.json", service)
            if control.error:
                raise RuntimeError("Operator control failed: " + control.error)
        else:
            print("No safe proposal; escalation is the result. No response was forced.", flush=True)
        errors = validate_report(final, bundle_dir=bundle)
        if errors:
            raise RuntimeError("Report validation failed: " + "; ".join(errors[:5]))
        outcome["status"] = final["status"]
        verification["action"] = final.get("verification", {})
        timings["inject_to_finished_s"] = round(time.monotonic() - started, 3)
        if final["status"] == "fixed":
            timings["inject_to_recovery_s"] = timings["inject_to_finished_s"]
        print("Final report:", flush=True)
        print((bundle / "report.md").read_text(encoding="utf-8"), flush=True)
        log = bundle / "action-log.jsonl"
        if not log.exists():
            log.write_text("", encoding="utf-8")
        print("Action-log excerpt:\n" + (log.read_text(encoding="utf-8") or "No action attempt was recorded."), flush=True)
    except Exception as exc:
        failed = True
        outcome["error"] = str(exc)
        print(str(exc), flush=True)
    except KeyboardInterrupt:
        failed, interrupted = True, True
        outcome["error"] = "KeyboardInterrupt; operator cleanup follows"
    finally:
        if control:
            try:
                control.finish()
            except Exception as exc:
                failed = True
                outcome["control_cleanup_error"] = str(exc)
            outcome["operator_interventions"] = control.interventions
        if previous_load is not None:
            try:
                set_operator_load(load_executor, previous_load)
                outcome["operator_load"]["restored"] = True
            except Exception as exc:
                failed = True
                outcome["load_cleanup_error"] = str(exc)
        if not args.defer_cleanup:
            try:
                with timed("reset_after", timings):
                    command(["faultctl", "reset", "--timeout", "90"], structured=True)
                    check_demo_unchanged()
                with timed("clear_after", timings):
                    verification["after"] = require_clean(directory, 360)
            except Exception as exc:
                failed = True
                outcome["cleanup_error"] = str(exc)
                print("Cleanup not verified: " + str(exc), flush=True)
            except KeyboardInterrupt:
                failed, interrupted = True, True
                outcome["cleanup_error"] = "KeyboardInterrupt; cleanup is not verified"
        else:
            verification["after"] = {"deferred_to_outer_driver": True}
        if (ROOT / "STOP").exists():
            print("STOP remains latched. After reviewing cleanup, clear it with: python -m action_api clear-stop", flush=True)
        outcome.update(recorded_at=datetime.now(timezone.utc).isoformat(), live=True,
                       timings=timings, recovery_verification=verification, failed=failed)
        encoded = json.dumps(outcome, indent=2) + "\n"
        (directory / "hands-rehearsal.json").write_text(encoded, encoding="utf-8")
        (bundle / "hands-rehearsal.json").write_text(encoded, encoding="utf-8")
        (bundle / "verification-before-after.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
        evidence = directory / "evidence"
        if evidence.is_dir():
            shutil.copytree(evidence, bundle / "operator-evidence", dirs_exist_ok=True)
        print(json.dumps({key: value for key, value in outcome.items() if key != "recovery_verification"}, indent=2), flush=True)
    if interrupted:
        raise KeyboardInterrupt
    return int(failed)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    os.environ["PYTHONIOENCODING"] = "utf-8"
    raise SystemExit(main())
