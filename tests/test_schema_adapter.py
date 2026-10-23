"""External-schema mapping does not discard the primary incident report."""

import copy
import json

import pytest
from jsonschema import Draft202012Validator

from schema.adapter import AdapterWarning, to_external
from schema.export import main


def test_identity_until_external_schema_arrives():
    report = {"incident_id": "sample", "root_cause": {"component": "cart"}}
    assert to_external(report, {}) == report
    result = to_external(report)
    result["root_cause"]["component"] = "payment"
    assert report["root_cause"]["component"] == "cart"


def test_fake_external_schema_maps_and_drops_unmapped_fields():
    report = {"incident_id": "sample", "root_cause": {"component": "cart", "confidence": 0.8}, "private_extra": "omit"}
    schema = {"type": "object", "properties": {
        "incidentId": {"type": "string"}, "component": {"type": "string"},
        "confidence": {"type": "number"}, "owner": {"type": ["string", "null"]},
        "ticket": {"type": "string"}, "adapter_notes": {"type": "array", "items": {"type": "string"}},
    }, "required": ["incidentId", "component", "owner", "ticket"], "additionalProperties": False}
    original = copy.deepcopy(report)
    with pytest.warns(AdapterWarning, match="required external field"):
        result = to_external(report, schema)
    Draft202012Validator(schema).validate(result)
    assert result["incidentId"] == "sample"
    assert result["component"] == "cart"
    assert result["owner"] is None
    assert result["ticket"] == "not_available"
    assert len(result["adapter_notes"]) == 2
    assert "private_extra" not in result
    assert report == original


def test_nested_array_projection_and_local_refs():
    report = {"evidence": [{"id": "trace:abcd", "summary": "Observed", "raw_ref": "internal"}]}
    schema = {"type": "object", "properties": {"evidence": {"type": "array", "items": {"$ref": "#/$defs/evidence"}}},
              "$defs": {"evidence": {"type": "object", "properties": {"id": {"type": "string"}}, "additionalProperties": False}}}
    result = to_external(report, schema)
    assert result == {"evidence": [{"id": "trace:abcd"}]}
    Draft202012Validator(schema).validate(result)


def test_export_validates_and_retains_primary(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"incident_id": "sample"}), encoding="utf-8")
    external = tmp_path / "external-schema.json"
    external.write_text(json.dumps({"type": "object", "properties": {"incidentId": {"type": "string"}}, "required": ["incidentId"], "additionalProperties": False}), encoding="utf-8")
    assert main([str(report), "--schema", str(external)]) == 0
    assert json.loads(report.with_name("report.external.json").read_text()) == {"incidentId": "sample"}
    assert json.loads(report.read_text()) == {"incident_id": "sample"}


def test_missing_numeric_value_fails_export_instead_of_inventing_data(tmp_path):
    report = tmp_path / "report.json"
    report.write_text("{}", encoding="utf-8")
    external = tmp_path / "external-schema.json"
    external.write_text(json.dumps({"type": "object", "properties": {"affected_users": {"type": "number"}}, "required": ["affected_users"]}), encoding="utf-8")
    assert main([str(report), "--schema", str(external)]) == 1
    assert not report.with_name("report.external.json").exists()
    assert "affected_users" in report.with_name("report.external.notes.json").read_text()
