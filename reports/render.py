"""Render an incident report as readable Markdown without changing the demo."""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def _cell(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _table(headers, rows) -> list[str]:
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] + ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]


def render_report(report: dict) -> str:
    root = report["root_cause"]
    approval, action, verification = report["approval"], report["action"], report["verification"]
    lines = [f"# Incident: {_cell(report['incident_id'])}", "", f"**{_cell(report['status'])}** · {_cell(root['component'])} · confidence {root['confidence']:.0%}", "", f"{_cell(root['cause'])}", "", f"Run: `{_cell(report['run_id'])}` · schema {report['schema_version']}", "", "## Timeline", ""]
    lines += _table(["Event", "Timestamp"], [
        ("Detected", report["detected_at"]), ("Diagnosed", report["diagnosed_at"]),
        ("Approval requested", approval["requested_at"]), ("Approved", approval["approved_at"]),
        ("Action started", action["started_at"]), ("Action finished", action["finished_at"]),
        ("Verified", verification["checked_at"]), ("Resolved", report["resolved_at"]),
    ])
    lines += ["", "## Symptoms", ""]
    lines += _table(["Service", "Signal", "Observed", "Evidence"], [(s["service"], s["signal"], s["observed"], ", ".join(s["evidence_ids"])) for s in report["symptoms"]])
    if "root_causes" in report:
        lines += ["", "## Root causes", ""]
        lines += _table(["Component", "Cause", "Model confidence", "Evidence confidence", "Final confidence", "Explained symptoms", "Evidence"], [
            (cause["component"], cause["cause"], f"{cause['confidence_model']:.0%}",
             f"{cause['confidence_evidence']:.0%}", f"{cause['confidence']:.0%}",
             ", ".join(cause["explains_symptoms"]), ", ".join(cause["evidence_ids"]))
            for cause in report["root_causes"]
        ])
    lines += ["", "## Investigation", ""]
    lines += _table(["Step", "Tool", "Why", "Finding"], [(s["step"], s["tool"], s["why"], s["finding"]) for s in report["investigation"]])
    lines += ["", "## Evidence", ""]
    lines += _table(["ID", "Source", "Summary", "Reproduce"], [(e["id"], e["source"], e["summary"], e["raw_ref"]) for e in report["evidence"]])
    lines += ["", f"Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir '{_cell(report['run_id'])}'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots."]
    impact = report.get("impact")
    if impact:
        lines += ["", "## Impact", ""]
        lines += _table(["Field", "Assessment"], [
            ("Approval tier", f"T{impact['tier']}"), ("Score", f"{impact['score']}/100"),
            ("Business criticality", impact["business"]), ("Journeys affected", ", ".join(impact["journeys_affected"])),
            ("Estimated users affected", impact["users_affected_estimate"]), ("Blast radius", impact["blast_radius"]),
            ("Reversibility", impact["reversibility"]), ("Data risk", impact["data_risk"]),
            ("Confidence", f"{impact['confidence']:.0%}"), ("Rationale", impact["rationale"]),
            ("Decision", impact.get('decision')), ("Reason codes", ', '.join(impact.get('reason_codes', []))),
            ("Uncertainty", impact.get('uncertainty')), ("Observability gap", impact.get('observability_gap')),
        ])
    lines += ["", "## Proposed action", ""]
    proposals = report.get("proposed_actions", [report["proposed_action"]] if report["proposed_action"] else [])
    if proposals:
        for index, proposal in enumerate(proposals, 1):
            lines += [f"**{index}. {_cell(proposal['type'])}** → {_cell(proposal['target'])}", "", f"Reason: {_cell(proposal['reason'])}", "", f"Risk: {_cell(proposal['risk'])}", "", f"Parameters: `{json.dumps(proposal['parameters'], sort_keys=True)}`", "", f"Dry run performed: {_cell(proposal['dry_run']['performed'])}. {_cell(proposal['dry_run']['predicted_effect'])}", ""]
            if impact and impact["tier"] == 1:
                lines += [f"Quick approval: {_cell(proposal['type'])} on {_cell(proposal['target'])}; predicted effect: {_cell(proposal['dry_run']['predicted_effect'])}. A human yes is required.", ""]
        if len(proposals) > 1:
            lines += ["Approve and execute each action separately in the listed impact order. Rejecting one does not approve or cancel another."]
    else:
        lines += ["No action proposed."]
    lines += ["", "## Approval record", ""]
    lines += _table(["Field", "Value"], [("Required", approval["required"]), ("Approved", approval["approved"]), ("Approved by", approval["approved_by"]), ("Approved at", approval["approved_at"]), ("Token", "present (redacted)" if approval["token"] else "absent"), ("Executed", action["executed"]), ("Action log", action["action_log_ref"])])
    lines += ["", "## Verification", ""]
    lines += _table(["Signal", "Before", "After", "Recovered", "Rolled back"], [(verification["signal"], verification["before"], verification["after"], verification["recovered"], verification["rolled_back"])])
    lines += ['', f"Outcome: {_cell(verification.get('outcome'))}; requests observed: {_cell(verification.get('requests_observed'))}."]
    if report.get('action_history'):
        lines += ['', '## Action history', '']
        lines += _table(['Index', 'Decision', 'Executed', 'Outcome', 'Blocked'], [
            (r['index'], r['decision'].get('decision'), r['execution'].get('executed', False),
             r['verification'].get('outcome'), ', '.join(r['error'].get('reason_codes', []))) for r in report['action_history']])
    lines += ["", "## Alternatives and escalation", ""]
    lines += [f"- {_cell(item)}" for item in root.get("alternatives_considered", [])] or ["No alternatives recorded."]
    lines += ["", _cell(report["escalation_note"]), "", "## Prevention", "", _cell(report["prevention"]), "", "## Limitations", ""]
    lines += [f"- {_cell(item)}" for item in report["limitations"]] or ["No limitations recorded."]
    agent = report["agent"]
    lines += ["", "## Investigation budget", "", f"Model: {_cell(agent['model'])}; {agent['tool_calls']} tool calls; {agent['elapsed_s']:.2f} s; stopped because {_cell(agent['stopped_because'])}.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", help="JSON files or glob patterns")
    parser.add_argument("--output-dir", type=Path, help="default: a Markdown sibling of each input")
    args = parser.parse_args(argv)
    failed = False
    for pattern in args.reports:
        matches = sorted(glob.glob(pattern))
        if not matches:
            print(f"{pattern}: no report files matched")
            failed = True
        for name in matches:
            source = Path(name)
            output = (args.output_dir / source.with_suffix(".md").name) if args.output_dir else source.with_suffix(".md")
            try:
                report = json.loads(source.read_text(encoding="utf-8"))
                rendered = render_report(report)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
                print(output)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                print(f"{name}: cannot render: {exc}")
                failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
