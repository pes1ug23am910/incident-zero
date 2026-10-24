"""Offline retrieval, provenance and answer-leakage boundaries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest
import yaml

from knowledge import KnowledgeIndex
from knowledge.catalogue import generate
from tools.redact import FLAG_NAMES, is_sensitive

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def index(tmp_path):
    target = KnowledgeIndex(tmp_path / "index.sqlite")
    target.build()
    return target


def test_complete_versioned_runbooks_build_under_ten_seconds(tmp_path):
    result = KnowledgeIndex(tmp_path / "index.sqlite").build()
    assert result["runbooks"] >= 12
    assert result["services"] >= 20
    assert result["seconds"] < 10
    assert result["mode"] == "bm25"
    assert not result["warnings"]
    required = {"symptoms", "investigation", "confirmation", "remediation", "rollback", "verification", "prevention", "pitfalls"}
    with sqlite3.connect(tmp_path / "index.sqlite") as db:
        books = db.execute("SELECT DISTINCT document_id FROM chunks WHERE kind='runbook'").fetchall()
        for (name,) in books:
            sections = {row[0] for row in db.execute("SELECT section FROM chunks WHERE document_id=?", (name,))}
            assert required <= sections
        assert db.execute("SELECT count(*) FROM terms").fetchone()[0] > 100
        assert db.execute("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL").fetchone()[0] == 0


def test_cache_is_first_for_cart_connection_errors(index):
    hits = index.search("cart errors connection refused")
    assert hits["runbook_refs"][0]["id"].startswith("kb:cache#")
    assert len(hits["runbook_refs"]) == 3
    assert len({hit["file"] for hit in hits["runbook_refs"]}) == 3
    assert len(hits["service_refs"]) == 1
    assert hits["service_refs"][0]["id"].startswith("kb:service-")


def test_payment_remediation_cites_category_and_contains_structured_action(index):
    hits = index.search("application_flag payment", section="remediation")["runbook_refs"]
    assert hits[0]["id"] == "kb:application-fault#remediation"
    assert hits[0]["action_types"] == ["toggle_flag"]
    assert hits[0]["category"] == "application_flag"
    assert "payment" in hits[0]["applies_to"]
    assert all(hit["section"] == "remediation" for hit in hits)


def test_provenance_and_scores_are_stable(index):
    first = index.search("recommendation memory growth")
    assert first == index.search("recommendation memory growth")
    for hit in first["runbook_refs"]:
        raw = (ROOT / hit["file"]).read_text(encoding="utf-8-sig")
        assert hit["sha256"] == hashlib.sha256(raw.encode()).hexdigest()
        assert hit["score"] > 0
        assert hit["version"] == "1"
        assert hit["text"].startswith("# ")
    index.build()
    assert first == index.search("recommendation memory growth")


def test_memory_upsert_updates_one_record_and_ranks_outcome(index):
    record = {"incident_id": "offline-example", "symptom_fingerprint": "cart connection refused cache",
              "component": "valkey-cart", "category": "container_down", "outcome": "escalated"}
    index.upsert_memory(record)
    hits = index.search("cart connection refused", runbook_k=0, service_k=0)["memory_refs"]
    assert hits[0]["id"] == "mem:offline-example"
    assert hits[0]["component"] == "valkey-cart"
    assert hits[0]["category"] == "container_down"
    assert hits[0]["outcome"] == "escalated"
    changed = {**record, "outcome": "rolled_back"}
    index.upsert_memory(changed)
    updated = index.search("cart connection refused")["memory_refs"]
    assert len(updated) == 1
    assert updated[0]["sha256"] != hits[0]["sha256"]
    assert updated[0]["outcome"] == "rolled_back"


def test_memory_redaction_and_safe_identity(index):
    record = {"incident_id": "redaction-example", "component": "payment", "cause": FLAG_NAMES[0] + "=true",
              "symptom_fingerprint": "payment errors", "outcome": "unknown"}
    index.upsert_memory(record)
    hit = index.search("payment errors")["memory_refs"][0]
    assert not is_sensitive(hit)
    assert "cause" not in json.loads(hit["text"])
    with pytest.raises(ValueError, match="safe incident_id"):
        index.upsert_memory({"incident_id": "../outside"})


def test_sensitive_query_is_not_tokenized(index):
    result = index.search(FLAG_NAMES[0] + "=true")
    assert result["runbook_refs"] == result["memory_refs"] == result["service_refs"] == []
    assert index.search(" \n ")["runbook_refs"] == []
    assert index.search("unrelatedxyzzyterm")["runbook_refs"] == []


def test_source_tree_excludes_control_names_and_incident_answers():
    for path in (ROOT / "knowledge").rglob("*"):
        if path.suffix not in {".py", ".md", ".yaml"}:
            continue
        raw = path.read_text(encoding="utf-8")
        assert not is_sensitive(raw), path
        assert "injected.json" not in raw, path
    for path in (ROOT / "knowledge" / "runbooks").glob("*.md"):
        raw = path.read_text(encoding="utf-8")
        assert "reports/" not in raw
        assert "incident_id" not in raw


def test_build_reads_only_authored_inputs_and_stored_memory(tmp_path, monkeypatch):
    root = tmp_path / "data"
    shutil.copytree(ROOT / "knowledge" / "runbooks", root / "knowledge" / "runbooks")
    shutil.copy2(ROOT / "knowledge" / "services.yaml", root / "knowledge" / "services.yaml")
    (root / "memory" / "store").mkdir(parents=True)
    (root / "memory" / "store" / "bad.json").write_text("invalid json")
    (root / "runs" / "hidden").mkdir(parents=True)
    (root / "runs" / "hidden" / "injected.json").write_text('{"secret_answer":"unrelatedxyzzyterm"}')
    seen = []
    original = Path.read_text
    def tracked(path, *args, **kwargs):
        seen.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", tracked)
    target = KnowledgeIndex(root=root)
    stats = target.build()
    assert len(stats["warnings"]) == 1
    assert not any("runs" in path.parts for path in seen)
    assert not target.search("unrelatedxyzzyterm")["runbook_refs"]


def test_catalogue_generation_keeps_only_safe_topology(tmp_path, monkeypatch):
    sensitive_service = "flag" + "d"
    raw = {"services": {"cart": {"depends_on": {"valkey-cart": {}, sensitive_service: {}},
                                    "environment": {"PASSWORD": "never-store-this"}},
                        "valkey-cart": {}, sensitive_service: {}}}
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps(raw), "")
    monkeypatch.setattr(subprocess, "run", run)
    output = tmp_path / "services.yaml"
    generated = generate(tmp_path, output)
    assert calls[0][0] == ["docker", "compose", "config", "--format", "json"]
    assert generated["services"]["cart"]["dependencies"] == ["valkey-cart"]
    assert sensitive_service not in generated["services"]
    assert "never-store-this" not in output.read_text()
    assert "startup dependencies" in generated["source"]["dependency_semantics"]


def test_explain_retains_report_citations_without_current_index(index, tmp_path):
    refs = index.search("payment application exception", section="remediation")
    report = {"incident_id": "offline-example", "runbook_refs": refs["runbook_refs"],
              "memory_refs": [], "knowledge_consulted": {"enabled": True, "mode": "bm25"}}
    original = deepcopy(report)
    result = KnowledgeIndex(tmp_path / "not-built.sqlite").explain(report)
    assert result == report == original
    assert not (tmp_path / "not-built.sqlite").exists()


def test_cli_build_search_explain(tmp_path, capsys):
    from knowledge.__main__ import main
    path = str(tmp_path / "cli.sqlite")
    main(["--index", path, "build"])
    assert json.loads(capsys.readouterr().out)["runbooks"] >= 12
    main(["--index", path, "search", "cart errors connection refused"])
    assert json.loads(capsys.readouterr().out)["runbook_refs"][0]["id"].startswith("kb:cache#")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"incident_id": "offline-example", "runbook_refs": []}))
    main(["explain", str(report)])
    assert json.loads(capsys.readouterr().out)["incident_id"] == "offline-example"


def test_invalid_book_does_not_destroy_preexisting_index(tmp_path):
    root = tmp_path / "data"
    shutil.copytree(ROOT / "knowledge" / "runbooks", root / "knowledge" / "runbooks")
    shutil.copy2(ROOT / "knowledge" / "services.yaml", root / "knowledge" / "services.yaml")
    target = KnowledgeIndex(root=root)
    target.build()
    prior = target.search("cart errors connection refused")
    (root / "knowledge" / "runbooks" / "broken.md").write_text("missing front matter")
    with pytest.raises(ValueError, match="front matter"):
        target.build()
    assert target.search("cart errors connection refused") == prior
