"""Sweep schema.validate against each bundle's checksummed retained evidence.

This explicitly verifies recorded evidence, not present stack health. It avoids
live-first retry delays for hundreds of expired historical IDs.
"""
import argparse
import json
from pathlib import Path

from schema.validate import validate_report
from tools.evidence import find_bundle_snapshot
from .platform_support import ROOT


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args(argv)
    paths = sorted(args.reports_dir.glob("*/report.json"))
    if not paths:
        print("FAIL: no report bundles matched")
        return 1
    failed = 0
    print("RECORDED EVIDENCE MODE: schema.validate + per-bundle identity/checksum validation; no live health claim.")
    for path in paths:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            errors = validate_report(report, resolver=lambda identifier: find_bundle_snapshot(identifier, path.parent))
        except (OSError, ValueError) as exc:
            errors = [type(exc).__name__ + ": report could not be validated"]
        if errors:
            failed += 1
            # Paths/reasons come from the validator; no credential-bearing raw record is printed.
            for error in errors:
                print(f"FAIL {path.parent.name}: {error}", flush=True)
        else:
            print(f"PASS {path.parent.name}: schema and retained evidence", flush=True)
    print(f"{'FAIL' if failed else 'PASS'} schema sweep: {len(paths)-failed}/{len(paths)} bundles")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
