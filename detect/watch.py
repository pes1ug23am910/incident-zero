"""Poll observability thresholds and start a read-only investigation per alert."""

import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
import time

from .core import Detector, ROOT, load_thresholds, write_alert
from tools.evidence import run_path


def wait_for_alert(detector, *, run_dir, timeout_s=90, interval_s=10, clock=time.monotonic,
                   sleep=time.sleep, stop_path=None):
    if not 0 <= timeout_s <= 90 or interval_s <= 0:
        raise ValueError("Alert wait must be 0..90 seconds and interval must be positive")
    started = clock()
    while True:
        if (stop_path or ROOT / "STOP").exists():
            raise RuntimeError("STOP exists; investigation was not started")
        alert = detector.poll(run_dir=run_dir, debounce=False)
        if alert:
            return alert
        remaining = timeout_s - (clock() - started)
        if remaining <= 0:
            return None
        sleep(min(interval_s, remaining))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=10)
    parser.add_argument("--thresholds")
    parser.add_argument("--no-agent", action="store_true")
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval must be positive")
    detector = Detector(load_thresholds(args.thresholds))
    directory = run_path(create=True)
    detector.prime_baseline(run_dir=directory)
    processes = []
    try:
        while True:
            started = time.monotonic()
            if (ROOT / "STOP").exists():
                print(json.dumps({"status": "stopped", "reason": "STOP exists"}), flush=True)
                return 0
            alert = detector.poll(run_dir=directory)
            if alert:
                path = write_alert(alert, directory)
                incident_id = "unknown-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                print(json.dumps({"alert_path": str(path), "incident_id": incident_id,
                                  "anomalies": len(alert["anomalies"])}), flush=True)
                if not args.no_agent and not (ROOT / "STOP").exists():
                    processes.append(subprocess.Popen([sys.executable, "-m", "agent.run", "--alert", str(path),
                                                       "--incident-id", incident_id], cwd=ROOT))
                directory = run_path(create=True)
            processes = [process for process in processes if process.poll() is None]
            time.sleep(max(0, args.interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
