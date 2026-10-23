"""Offline ablation honesty, source isolation and retained-evidence validation."""
import hashlib
import json
from pathlib import Path
import shutil
import socket

import pytest

from eval.knowledge_ablation import ROOT, compare, compare_report, main
from tools.evidence import expected_source


@pytest.fixture
def recorded(tmp_path, monkeypatch):
    import tools.evidence

    monkeypatch.setattr(tools.evidence, "ROOT", tmp_path)
    def no_network(*args, **kwargs):
        raise AssertionError("Offline comparison attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    report = json.loads((ROOT / "schema/examples/valid.json").read_text(encoding="utf-8"))
    fixture = json.loads((ROOT / "schema/examples/evidence_fixture.json").read_text(encoding="utf-8"))["evidence"]
    bundle = tmp_path / "reports" / "example"
    (bundle / "evidence").mkdir(parents=True)
    (bundle / "report.json").write_text(json.dumps(report), encoding="utf-8")
    for identifier, data in fixture.items():
        snapshot = {"version": 1, "id": identifier, "source": expected_source(identifier),
                    "data": data, "captured_at": report["detected_at"]}
        snapshot["checksum"] = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        name = hashlib.sha256(identifier.encode()).hexdigest() + ".json"
        (bundle / "evidence" / name).write_text(json.dumps(snapshot), encoding="utf-8")
    return bundle, report


def test_offline_comparison_freezes_metrics_and_does_not_write_report(recorded):
    bundle, report = recorded
    before = (bundle / "report.json").read_bytes()
    result = compare(reports_dir=bundle.parent, bundles=[bundle.name])
    assert result["evaluation"] == "offline_retrieval_only"
    assert result["decisions_frozen"] and not result["improvement_measured"]
    row = result["rows"][0]
    assert row["off"]["recorded_metrics"] == row["on"]["recorded_metrics"]
    assert row["on"]["recorded_metrics"]["tool_calls"] == report["agent"]["tool_calls"]
    assert row["on"]["recorded_metrics"]["seconds"] == report["agent"]["elapsed_s"]
    assert not row["off"]["stages"] and row["off"]["retrieval_ms"] == 0
    assert len(row["on"]["stages"]) == 2
    assert row["on"]["stages"][0]["runbook_refs"]
    assert row["on"]["retrieval_ms"] >= 0
    assert (bundle / "report.json").read_bytes() == before
    assert result["index"]["memories"] == 0


def test_evaluation_reports_and_existing_memory_are_never_index_inputs(recorded, tmp_path):
    bundle, _ = recorded
    root = tmp_path / "source"
    shutil.copytree(ROOT / "knowledge/runbooks", root / "knowledge/runbooks")
    shutil.copyfile(ROOT / "knowledge/services.yaml", root / "knowledge/services.yaml")
    (root / "memory/store").mkdir(parents=True)
    (root / "memory/store/answer.json").write_text(json.dumps({"incident_id": "example", "text": "payment answer contamination"}))
    result = compare(reports_dir=bundle.parent, bundles=[bundle.name], source_root=root)
    assert result["index"]["memories"] == 0
    assert all(not stage["memory_refs"] for stage in result["rows"][0]["on"]["stages"])
    assert not (root / "knowledge/index.sqlite").exists()


def test_corrupt_retained_evidence_fails_closed_without_live_fallback(recorded):
    bundle, _ = recorded
    snapshot = next((bundle / "evidence").glob("*.json"))
    snapshot.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="failed validation"):
        compare(reports_dir=bundle.parent, bundles=[bundle.name])


def test_observation_query_excludes_diagnosis_and_incident_metadata(recorded):
    _, report = recorded
    report["incident_id"] = "operator-label-sentinel"
    report["root_cause"]["component"] = "diagnosis-sentinel"
    calls = []
    class Index:
        def search(self, query, **kwargs):
            calls.append((query, kwargs))
            return {"mode": "bm25", "runbook_refs": [], "memory_refs": [], "service_refs": [], "warnings": []}
    compare_report(report, Index())
    assert "operator-label-sentinel" not in str(calls)
    assert "diagnosis-sentinel" not in calls[0][0]
    assert "diagnosis-sentinel" in calls[1][0]
    assert calls[0][1]["section"] == "investigation"
    assert calls[1][1]["section"] == "remediation"


def test_bundle_path_cannot_escape_selected_reports_directory(recorded):
    bundle, _ = recorded
    with pytest.raises(ValueError, match="direct children"):
        compare(reports_dir=bundle.parent, bundles=["../elsewhere"])


def test_cli_writes_explicitly_labeled_comparison(recorded, tmp_path):
    bundle, _ = recorded
    output = tmp_path / "comparison.json"
    assert main(["--reports-dir", str(bundle.parent), "--bundles", bundle.name, "--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert not result["improvement_measured"] and len(result["rows"]) == 1
