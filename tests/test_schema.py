"""Structural, evidence, approval, and report-rendering contract checks."""

import copy
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest
from jsonschema import Draft202012Validator

from reports.render import render_report
from schema.validate import SCHEMA_PATH, fixture_resolver, main, validate_report

EXAMPLES = Path(__file__).resolve().parents[1] / "schema" / "examples"


@pytest.fixture
def report():
    return json.loads((EXAMPLES / "valid.json").read_text(encoding="utf-8"))


@pytest.fixture
def resolve():
    return fixture_resolver(EXAMPLES / "evidence_fixture.json")


def test_schema_is_valid_draft_2020_12_and_all_objects_are_closed():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(schema)


def test_valid_report_passes_explicit_fixture(report, resolve):
    assert validate_report(report, resolver=resolve) == []


def test_default_validation_calls_real_resolver_interface(report, monkeypatch):
    calls = []
    module = ModuleType("tools.resolve")

    def backend(evidence_id, *, run_dir=None):
        calls.append((evidence_id, run_dir))
        return {"found": True, "data": {"status": "running"}}

    module.resolve = backend
    monkeypatch.setitem(sys.modules, "tools.resolve", module)
    assert validate_report(report) == []
    assert calls == [(report["evidence"][0]["id"], report["run_id"])]


@pytest.mark.parametrize("result", [None, False, {}, {"found": False}, {"resolved": False}, {"error": "missing"}])
def test_nonexistent_evidence_fails(report, result):
    errors = validate_report(report, resolver=lambda _: result)
    assert any("$.evidence[0].id: cannot resolve" in error for error in errors)


def test_backend_failure_fails_closed(report):
    def unavailable(_):
        raise ConnectionError("backend unavailable")

    assert any("backend unavailable" in error for error in validate_report(report, resolver=unavailable))


@pytest.mark.parametrize("filename,path", [
    ("invalid_unresolved.json", "$.evidence[0].id"),
    ("invalid_fixed_no_approval_time.json", "$.approval.approved_at"),
    ("invalid_low_confidence.json", "$.status"),
])
def test_invalid_examples(filename, path, resolve):
    example = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
    assert any(error.startswith(path) for error in validate_report(example, resolver=resolve))


def test_fixed_requires_complete_approval_and_measured_recovery(resolve):
    report = json.loads((EXAMPLES / "invalid_fixed_no_approval_time.json").read_text(encoding="utf-8"))
    report["approval"]["approved_at"] = "2026-10-23T13:00:03+05:30"
    assert validate_report(report, resolver=resolve) == []
    report["verification"]["recovered"] = False
    assert any("$.verification.recovered" in error for error in validate_report(report, resolver=resolve))


def test_executed_action_without_approval_fails_even_if_not_fixed(report, resolve):
    report["action"]["executed"] = True
    errors = validate_report(report, resolver=resolve)
    assert any("$.approval.approved" in error for error in errors)
    assert any("$.action.action_log_ref" in error for error in errors)


def test_uncited_evidence_reference_fails(report, resolve):
    report["symptoms"][0]["evidence_ids"].append("trace:missing")
    assert any("$.symptoms[0].evidence_ids[1]" in error for error in validate_report(report, resolver=resolve))


def test_duplicate_evidence_ids_fail(report, resolve):
    report["evidence"].append(copy.deepcopy(report["evidence"][0]))
    assert any("must be unique" in error for error in validate_report(report, resolver=resolve))


def test_component_needs_support(report, resolve):
    report["root_cause"]["component"] = "unmentioned-service"
    assert any("$.root_cause.component" in error for error in validate_report(report, resolver=resolve))


def test_evidence_source_matches_type(report, resolve):
    report["evidence"][0]["source"] = "jaeger"
    assert any("$.evidence[0].source" in error for error in validate_report(report, resolver=resolve))


def test_health_table_is_an_investigation_tool(report, resolve):
    report["investigation"][0]["tool"] = "health_table"
    assert validate_report(report, resolver=resolve) == []


@pytest.mark.parametrize("evidence_id,source", [
    ("action_log:1", "action_log"),
    ("dlog:checkout:" + "6de102fa" * 8, "docker"),
])
def test_action_and_stdout_evidence_id_source_agreement(report, evidence_id, source):
    item = report["evidence"][0]
    previous_id = item["id"]
    item.update(id=evidence_id, source=source)
    for collection in ("symptoms", "investigation"):
        for entry in report[collection]:
            entry["evidence_ids"] = [evidence_id if value == previous_id else value for value in entry["evidence_ids"]]
    resolver = lambda _: {"found": True, "source": source, "data": {"body": "Example recorded event"}}
    assert validate_report(report, resolver=resolver) == []
    item["source"] = "prometheus"
    assert any("$.evidence[0].source" in error for error in validate_report(report, resolver=resolver))


@pytest.mark.parametrize("evidence_id", ["action_log:0", "action_log:-1", "action_log:abc", "dlog:checkout:", "dlog:checkout:not-a-hash", "dlog:check/out:abc"])
def test_invalid_action_and_stdout_ids_rejected(report, resolve, evidence_id):
    report["evidence"][0]["id"] = evidence_id
    assert any("$.evidence[0].id" in error for error in validate_report(report, resolver=resolve))


def test_resolver_source_must_match_report(report):
    result = {"found": True, "source": "jaeger", "data": {"value": "running"}}
    assert any("$.evidence[0].source" in error for error in validate_report(report, resolver=lambda _: result))


def test_recorded_snapshot_can_resolve_report_evidence(report):
    result = {"found": True, "source": "docker", "resolved_from": "snapshot", "data": {"value": "running"}}
    assert validate_report(report, resolver=lambda _: result) == []


def test_no_incident_allows_low_root_cause_confidence_without_escalation(report, resolve):
    report["status"] = "no_incident"
    report["root_cause"]["confidence"] = 0
    report["root_cause"]["cause"] = "No payment container outage was observed in the recorded check."
    report["escalation_note"] = None
    assert validate_report(report, resolver=resolve) == []


@pytest.mark.parametrize("field,value", [
    ("action.executed", True),
    ("verification.recovered", True),
    ("verification.rolled_back", True),
    ("root_cause.category", "container_down"),
    ("resolved_at", "2026-10-23T13:00:05+05:30"),
])
def test_no_incident_rejects_remediation_and_recovery_claims(report, resolve, field, value):
    report["status"] = "no_incident"
    target = report
    parts = field.split(".")
    for key in parts[:-1]:
        target = target[key]
    target[parts[-1]] = value
    assert any(error.startswith("$." + field) for error in validate_report(report, resolver=resolve))


def test_no_incident_rejects_actionable_proposal(report, resolve):
    report["status"] = "no_incident"
    report["proposed_action"] = {
        "type": "restart_service", "target": "payment", "parameters": {"service": "payment"},
        "reason": "Example", "risk": "Example",
        "dry_run": {"performed": False, "predicted_effect": "Example"},
    }
    assert any(error.startswith("$.proposed_action") for error in validate_report(report, resolver=resolve))


def test_no_incident_requires_evidence(report, resolve):
    report["status"] = "no_incident"
    report["evidence"] = []
    report["symptoms"][0]["evidence_ids"] = []
    report["investigation"][0]["evidence_ids"] = []
    assert any(error.startswith("$.evidence") for error in validate_report(report, resolver=resolve))


@pytest.mark.parametrize("marker", ["flag" + "d", "demo." + "flag" + "d.json", "default" + "Variant"])
def test_prohibited_report_content_is_rejected_at_nested_path(report, resolve, marker):
    report["investigation"][0]["finding"] = "Read from " + marker.upper()
    assert any("$.investigation[0].finding" in error for error in validate_report(report, resolver=resolve))


def test_timezone_is_required(report, resolve):
    report["detected_at"] = "2026-10-23T13:00:00"
    assert any("$.detected_at" in error for error in validate_report(report, resolver=resolve))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_numbers_fail(report, resolve, value):
    report["alert"]["observed"] = value
    assert any("$.alert.observed" in error for error in validate_report(report, resolver=resolve))


def test_reversed_timeline_is_rejected(report, resolve):
    report["diagnosed_at"] = "2026-10-23T12:59:59+05:30"
    assert any("$.diagnosed_at" in error for error in validate_report(report, resolver=resolve))


@pytest.mark.parametrize("location", ["top", "nested", "parameters"])
def test_unknown_fields_and_action_parameters_rejected(report, resolve, location):
    if location == "top":
        report["unlisted"] = True
    elif location == "nested":
        report["root_cause"]["unlisted"] = True
    else:
        report["proposed_action"] = {
            "type": "restart_service", "target": "payment",
            "parameters": {"service": "payment", "shell": "unexpected"},
            "reason": "Example", "risk": "Example",
            "dry_run": {"performed": False, "predicted_effect": "Example"},
        }
    assert validate_report(report, resolver=resolve)


@pytest.mark.parametrize("kind,parameters", [
    ("restart_service", {"service": "payment"}),
    ("toggle_flag", {"flag": "paymentFailure", "variant": "off"}),
    ("throttle_load", {"users": 5, "spawn_rate": 1}),
    ("none", {}),
])
def test_action_parameter_allowlist(report, resolve, kind, parameters):
    report["proposed_action"] = {
        "type": kind, "target": "payment", "parameters": parameters,
        "reason": "Example", "risk": "Example",
        "dry_run": {"performed": False, "predicted_effect": "Example"},
    }
    assert validate_report(report, resolver=resolve) == []


def test_cli_explicit_fixture_and_exit_codes(capsys):
    fixture_args = ["--offline-fixture", str(EXAMPLES / "evidence_fixture.json")]
    assert main([str(EXAMPLES / "valid.json"), *fixture_args]) == 0
    assert "OFFLINE FIXTURE MODE" in capsys.readouterr().out
    assert main([str(EXAMPLES / "invalid_*.json"), *fixture_args]) == 1
    output = capsys.readouterr().out
    assert "$.approval.approved_at" in output
    assert "$.evidence[0].id" in output
    assert "$.status" in output


def test_cli_missing_or_bad_json_fails(tmp_path):
    assert main([str(tmp_path / "absent.json")]) == 1
    bad = tmp_path / "bad.json"
    bad.write_text("{not json}", encoding="utf-8")
    assert main([str(bad)]) == 1


def test_renderer_has_sections_and_redacts_approval_token(report):
    report["approval"]["token"] = "secret-example-token"
    report["evidence"][0]["summary"] = "payment | multiline\nvalue"
    markdown = render_report(report)
    for heading in ("Timeline", "Symptoms", "Investigation", "Evidence", "Proposed action", "Approval record", "Verification", "Limitations"):
        assert f"## {heading}" in markdown
    assert "secret-example-token" not in markdown
    assert "present (redacted)" in markdown
    assert "payment \\| multiline value" in markdown
    assert "ILLUSTRATIVE OFFLINE EXAMPLE" in markdown
