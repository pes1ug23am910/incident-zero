"""Evaluate all service thresholds once, without starting the investigator."""

import argparse
import json

from .core import Detector, load_thresholds, write_alert
from tools.evidence import run_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thresholds")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    directory = run_path(args.run_id, create=True)
    detector = Detector(load_thresholds(args.thresholds))
    detector.prime_baseline(run_dir=directory)
    alert = detector.poll(run_dir=directory, debounce=False)
    if alert:
        path = write_alert(alert, directory)
        print(json.dumps({**alert, "run_id": directory.name, "alert_path": str(path)}, indent=2))
    else:
        print(json.dumps({"status": "no_alert", "telemetry_available": bool(
            (detector.last_health or {}).get("telemetry_available")),
            "warnings": (detector.last_health or {}).get("warnings", []), "run_id": directory.name}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
