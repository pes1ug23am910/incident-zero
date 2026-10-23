"""Validate structure, safety invariants, and reproducible evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
import glob
import json
import math
from pathlib import Path
import re
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path(__file__).with_name("incident_report.schema.json")
# The guard must recognise prohibited report content without placing those
# endpoint/configuration markers in a diagnostic package's source text.
PROHIBITED_TEXT = ("flag" + "d", "demo." + "flag" + "d.json", "default" + "Variant")
Resolver = Callable[[str], Any]
TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time")
def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    if not re.fullmatch(TIMESTAMP_PATTERN, value):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00")).utcoffset() is not None
    except ValueError:
        return False


def _path(parts: Any) -> str:
    result = "$"
    for part in parts:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result


def _strings(value: Any, parts: tuple = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield parts + (key,), key
            yield from _strings(child, parts + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _strings(child, parts + (index,))
    elif isinstance(value, str):
        yield parts, value


def _nonfinite_paths(value: Any, parts: tuple = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _nonfinite_paths(child, parts + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _nonfinite_paths(child, parts + (index,))
    elif isinstance(value, float) and not math.isfinite(value):
        yield parts


def _live_resolve(evidence_id: str, *, run_dir: str | None = None, bundle_dir: str | Path | None = None) -> Any:
    from tools.resolve import resolve

    if bundle_dir is not None:
        return resolve(evidence_id, run_dir=run_dir, bundle_dir=bundle_dir)
    return resolve(evidence_id, run_dir=run_dir)


def fixture_resolver(path: str | Path) -> Resolver:
    """Explicit offline mode for examples; never selected automatically."""
    fixture = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(fixture, dict) or not isinstance(fixture.get("evidence"), dict):
        raise ValueError("fixture must contain an evidence object keyed by exact ids")
    entries = fixture["evidence"]

    def resolve_from_fixture(evidence_id: str) -> Any:
        if evidence_id not in entries:
            raise LookupError("evidence id is absent from the explicit offline fixture")
        return entries[evidence_id]

    return resolve_from_fixture


def _resolved(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, dict):
        if value.get("resolved") is False or value.get("found") is False or value.get("ok") is False:
            return False
        if value.get("error"):
            return False
        return bool(value)
    return bool(value)


def _mentions_component(evidence_id: str, resolved: Any, component: str) -> bool:
    """Use source identifiers/structured service names, never generated summaries."""
    if evidence_id.startswith((f"container:{component}:", f"dlog:{component}:")):
        return True
    if evidence_id.startswith("metric:") and re.search(
        r'(?:service_name|container_name|service)="' + re.escape(component) + '"', evidence_id
    ):
        return True

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"service", "service_name", "serviceName", "container_name", "name"} and item == component:
                    return True
                if key == "services" and isinstance(item, list) and component in item:
                    return True
                if visit(item):
                    return True
        elif isinstance(value, list):
            return any(visit(item) for item in value)
        return False

    return visit(resolved)


def validate_report(report: Any, *, resolver: Resolver | None = None, bundle_dir: str | Path | None = None) -> list[str]:
    """Check live evidence, its run snapshots, and an optional retained bundle."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    errors = [f"{_path(error.absolute_path)}: {error.message}" for error in sorted(
        validator.iter_errors(report), key=lambda error: str(list(error.absolute_path))
    )]
    for path, value in _strings(report):
        if any(marker.casefold() in value.casefold() for marker in PROHIBITED_TEXT):
            errors.append(f"{_path(path)}: contains prohibited configuration-disclosure text")
    errors.extend(f"{_path(path)}: numbers must be finite" for path in _nonfinite_paths(report))
    # Semantic checks assume the strict schema's types and required fields.
    if errors:
        return errors

    def fail(path: str, message: str) -> None:
        errors.append(f"$.{path}: {message}")

    status = report["status"]
    root = report["root_cause"]
    if root["confidence"] < 0.6 and status not in {"needs_human", "no_incident", "aborted"}:
        fail("status", "confidence below 0.6 requires needs_human")
    if status == "needs_human" and not (report["escalation_note"] or "").strip():
        fail("escalation_note", "needs_human requires findings, uncertainty, and next checks")

    evidence = report["evidence"]
    evidence_ids = [item["id"] for item in evidence]
    if len(set(evidence_ids)) != len(evidence_ids):
        fail("evidence", "evidence ids must be unique")
    known = set(evidence_ids)
    for collection in ("symptoms", "investigation"):
        for index, item in enumerate(report[collection]):
            for id_index, evidence_id in enumerate(item["evidence_ids"]):
                if evidence_id not in known:
                    fail(f"{collection}[{index}].evidence_ids[{id_index}]", "id does not appear in evidence")
    if status in {"diagnosed", "fixed", "rolled_back", "no_incident"} and not evidence:
        fail("evidence", "a diagnosis, clean finding, or completed action requires evidence")

    causes = report.get("root_causes")
    if causes is not None:
        if root != causes[0]:
            fail("root_cause", "must equal the first root_causes entry")
        if [cause["confidence"] for cause in causes] != sorted((cause["confidence"] for cause in causes), reverse=True):
            fail("root_causes", "must be ordered by descending confidence")
        services = {item["service"] for item in report["symptoms"]}
        for index, cause in enumerate(causes):
            expected = min(cause["confidence_model"], cause["confidence_evidence"])
            if not math.isclose(cause["confidence"], expected, abs_tol=1e-9):
                fail(f"root_causes[{index}].confidence", "must equal min(confidence_model, confidence_evidence)")
            for id_index, evidence_id in enumerate(cause["evidence_ids"]):
                if evidence_id not in known:
                    fail(f"root_causes[{index}].evidence_ids[{id_index}]", "id does not appear in evidence")
            for symptom in cause["explains_symptoms"]:
                if symptom not in services:
                    fail(f"root_causes[{index}].explains_symptoms", "must name a service in symptoms")
            if cause["confidence"] < 0.6 and status not in {"needs_human", "no_incident", "aborted"}:
                fail("status", "a cause below 0.6 requires needs_human")
        proposals = report["proposed_actions"]
        if report["proposed_action"] != (proposals[0] if proposals else None):
            fail("proposed_action", "must equal the first proposed_actions entry, or null when empty")
        if len(proposals) > len(causes):
            fail("proposed_actions", "cannot contain more than one action per cause")
        impact = report["impact"]
        if impact["tier"] == 3:
            if proposals or report["proposed_action"] is not None:
                fail("proposed_actions", "tier 3 never carries a proposed action")
            if status not in {"needs_human", "no_incident", "aborted"}:
                fail("status", "tier 3 requires needs_human")
        if status == "no_incident" and proposals:
            fail("proposed_actions", "no_incident cannot propose remediation")
        if status == "no_incident" and any(cause["category"] != "unknown" for cause in causes):
            fail("root_causes", "no_incident cannot assign incident cause categories")

    all_proposals = report.get("proposed_actions", [report["proposed_action"]])
    for index, proposal in enumerate(all_proposals):
        if proposal and proposal["type"] in {"restart_service", "toggle_flag"}:
            if proposal["parameters"]["service"] != proposal["target"]:
                fail(f"proposed_actions[{index}].parameters.service", "must equal the proposal target")

    component = root["component"].casefold()
    text = [item["summary"] for item in evidence]
    text.extend(item[key] for item in report["symptoms"] for key in ("service", "signal", "observed"))
    if not any(component in value.casefold() for value in text):
        fail("root_cause.component", "component must appear in an evidence summary or symptom")
    steps = [item["step"] for item in report["investigation"]]
    if steps != list(range(1, len(steps) + 1)):
        fail("investigation", "steps must be consecutive and start at 1")

    approval, action, verification = report["approval"], report["action"], report["verification"]
    if status == "no_incident":
        if root["category"] != "unknown":
            fail("root_cause.category", "no_incident cannot assign an incident cause category")
        proposal = report["proposed_action"]
        if proposal is not None and proposal["type"] != "none":
            fail("proposed_action", "no_incident cannot propose remediation")
        if action["executed"]:
            fail("action.executed", "no_incident cannot claim executed remediation")
        if verification["recovered"] is True:
            fail("verification.recovered", "no_incident cannot claim incident recovery")
        if verification["rolled_back"]:
            fail("verification.rolled_back", "no_incident cannot claim rollback")
        if report["resolved_at"] is not None:
            fail("resolved_at", "no_incident has no incident resolution timestamp")
    if approval["approved"] is True:
        for key in ("requested_at", "approved_at", "approved_by", "token"):
            if not approval[key]:
                fail(f"approval.{key}", "explicit approval requires this value")
    elif any(approval[key] is not None for key in ("approved_at", "token")):
        fail("approval", "an unapproved request cannot carry an approval time or token")
    if action["executed"]:
        if approval["approved"] is not True:
            fail("approval.approved", "executed actions require explicit approval")
        if report["proposed_action"] is None or report["proposed_action"]["type"] == "none":
            fail("proposed_action", "executed actions require an actionable proposal")
        for key in ("started_at", "finished_at", "action_log_ref"):
            if not action[key]:
                fail(f"action.{key}", "executed actions require an audit record")
    elif any(action[key] is not None for key in ("started_at", "finished_at", "action_log_ref")):
        fail("action", "unexecuted actions must not claim execution metadata")
    if status == "fixed":
        if approval["approved"] is not True:
            fail("approval.approved", "fixed requires explicit approval")
        if not action["executed"]:
            fail("action.executed", "fixed requires a recorded execution")
        if verification["recovered"] is not True:
            fail("verification.recovered", "fixed requires a successful recovery check")
        if verification["rolled_back"]:
            fail("verification.rolled_back", "fixed cannot claim rollback")
        for key in ("checked_at", "before", "after"):
            if verification[key] is None:
                fail(f"verification.{key}", "fixed requires measured recovery")
        if report["resolved_at"] is None:
            fail("resolved_at", "fixed requires a resolution timestamp")
    if status == "rolled_back" and not verification["rolled_back"]:
        fail("verification.rolled_back", "rolled_back requires a recorded rollback")

    timeline = [
        ("detected_at", report["detected_at"]), ("diagnosed_at", report["diagnosed_at"]),
        ("approval.requested_at", approval["requested_at"]),
        ("approval.approved_at", approval["approved_at"]),
        ("action.started_at", action["started_at"]), ("action.finished_at", action["finished_at"]),
        ("verification.checked_at", verification["checked_at"]), ("resolved_at", report["resolved_at"]),
    ]
    previous = None
    for path, timestamp in timeline:
        if timestamp is None:
            continue
        current = datetime.fromisoformat(timestamp.replace("Z", "+00:00").replace("z", "+00:00"))
        if previous is not None and current < previous:
            fail(path, "timestamp precedes the prior recorded event")
        previous = current

    resolver = resolver or (lambda evidence_id: _live_resolve(evidence_id, run_dir=report["run_id"], bundle_dir=bundle_dir))
    expected_source = {"trace": "jaeger", "span": "jaeger", "log": "opensearch", "dlog": "docker", "metric": "prometheus", "container": "docker", "action_log": "action_log"}
    resolved_evidence = {}
    for index, item in enumerate(evidence):
        if expected_source.get(item["id"].split(":", 1)[0]) != item["source"]:
            fail(f"evidence[{index}].source", "source does not match the evidence id type")
        try:
            resolved = resolver(item["id"])
            if not _resolved(resolved):
                raise LookupError("resolver did not return existing evidence")
            resolved_evidence[item["id"]] = resolved
            if isinstance(resolved, dict) and resolved.get("source") not in (None, item["source"]):
                fail(f"evidence[{index}].source", "source does not match the resolved evidence")
        except Exception as exc:
            fail(f"evidence[{index}].id", f"cannot resolve evidence: {exc}")
    if causes is not None:
        for index, cause in enumerate(causes):
            if cause["category"] == "unknown" and cause["confidence"] < 0.6:
                continue
            if not any(_mentions_component(identity, resolved_evidence.get(identity), cause["component"])
                       for identity in cause["evidence_ids"]):
                fail(f"root_causes[{index}].component", "cited evidence must identify the component in source data")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", help="report files or glob patterns")
    parser.add_argument("--offline-fixture", type=Path, help="explicit evidence fixture for examples/tests; no live verification")
    args = parser.parse_args(argv)
    resolver = None
    if args.offline_fixture:
        try:
            resolver = fixture_resolver(args.offline_fixture)
        except (OSError, ValueError) as exc:
            print(f"{args.offline_fixture}: $: {exc}")
            return 1
        print("OFFLINE FIXTURE MODE: evidence is not verified against the running stack")
    failed = False
    paths = []
    for pattern in args.reports:
        matches = sorted(glob.glob(pattern))
        if not matches:
            print(f"{pattern}: $: no report files matched")
            failed = True
        paths.extend(matches)
    for name in dict.fromkeys(paths):
        try:
            report = json.loads(Path(name).read_text(encoding="utf-8"))
            parent = Path(name).parent
            errors = validate_report(report, resolver=resolver, bundle_dir=parent if (parent / "evidence").is_dir() else None)
        except (OSError, ValueError) as exc:
            errors = [f"$: {exc}"]
        if errors:
            failed = True
            for error in errors:
                print(f"{name}: {error}")
        else:
            print(f"{name}: valid ({'offline fixture' if resolver else 'evidence resolved live, from run snapshots, or from the retained bundle'})")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
