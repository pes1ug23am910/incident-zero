"""Operator prompts; no token is minted by interpreting telemetry prose."""
import json
import os
import sys
from .safety import Blocked


def prompt(report, dry_run, operator, *, auto_approve_for_tests=False, input_fn=input, output=print):
    if auto_approve_for_tests:
        if os.environ.get("INCIDENT_ZERO_TEST") != "1":
            raise Blocked("TEST_APPROVAL_DISABLED")
        output("TEST ONLY: INCIDENT_ZERO_TEST=1 --auto-approve-for-tests; no human approval was collected")
        return True
    impact, plan = dry_run["impact"], dry_run["plan"]
    root = report["root_cause"]
    output(f"Affected service: {root['component']}; journeys: {', '.join(impact['journeys_affected'])}; {impact['users_affected_estimate']}")
    output(f"Diagnosis: {root['cause']}; alternatives: {root.get('alternatives_considered', [])}; uncertainty: {impact['uncertainty']:.2f}")
    output("Evidence IDs: " + ", ".join(e["id"] for e in report.get("evidence", [])))
    if impact["tier"] == 2:
        for row in report.get("evidence", []):
            output(f"{row['id']} | {row.get('source')} | {row.get('summary')}")
        output("Independent-source check: " + dry_run["second_source_check"])
    output(f"Exact operation: {plan['action']} on {plan['target']} {json.dumps(plan['parameters'], sort_keys=True)}")
    output(f"Risk: tier {impact['tier']}, score {impact['score']}; {', '.join(dry_run['reason_codes'])}; {impact['rationale']}")
    output("Expected effect: " + dry_run["predicted_effect"] + "; side effects: " + dry_run["side_effects"])
    output("Rollback limits: " + dry_run["rollback_limits"])
    output("Verification: every alert signal below its threshold on two consecutive 30s samples over >=180s, >=20 frontend requests in 2m, load still running.")
    if impact["tier"] == 1:
        output(f"{plan['action']} on {plan['target']}: {dry_run['predicted_effect']} [{operator}: y/N]")
        if input_fn is input and os.name == "nt" and sys.stdin.isatty():
            import msvcrt
            return msvcrt.getwch().lower() == "y"
        return input_fn("Approve [y/N]: ").strip().lower() == "y"
    return input_fn(f"{operator}, type yes to approve: ").strip() == "yes"
