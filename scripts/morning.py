"""Preflight, optional payment smoke, report sweep and Linux portability."""
import argparse
from pathlib import Path

from .platform_support import ROOT, environment, run_module, stamp, table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-smoke", action="store_true", help="skip the ONLY stack-changing step")
    parser.add_argument("--stack-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    environment()
    rows = []
    preflight = run_module("scripts.preflight", "--stack-root", args.stack_root)
    rows.append(("preflight", "PASS" if preflight == 0 else "FAIL", "read-only"))
    if args.no_smoke or preflight:
        rows.append(("payment smoke", "SKIP", "--no-smoke" if args.no_smoke else "preflight failed; mutation refused"))
    else:
        code = run_module("scripts.operator", "checkpoint2", "payment-failure")
        rows.append(("payment smoke", "PASS" if code == 0 else "FAIL", "diagnosis, injection/reset owned by operator"))
    for label, module, arguments in (
        ("schema sweep", "schema.validate", ["reports/*/report.json"]),
        ("Linux portability", "scripts.crossplatform_check", [])):
        code = run_module(module, *arguments)
        rows.append((label, "PASS" if code == 0 else "FAIL", f"exit {code}"))
    content = table(rows)
    output = ROOT / ".build/morning"
    output.mkdir(parents=True, exist_ok=True)
    (output / (stamp() + ".md")).write_text(content, encoding="utf-8")
    print(content)
    return int(any(row[1] == "FAIL" for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
