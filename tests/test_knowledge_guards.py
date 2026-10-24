"""Regression guards for disabled checkpoints and runbook applicability."""
from copy import deepcopy
import json
from pathlib import Path

from agent import knowledge_context
from agent.policy import propose
from knowledge import KnowledgeIndex

ROOT = Path(__file__).resolve().parents[1]


def consultation():
    return {"enabled": True, "mode": "bm25", "queries": [], "runbook_refs": [],
            "memory_refs": [{"id": "mem:old", "text": "Old payment hint"}],
            "service_refs": [], "limitations": []}


def test_disabled_stale_checkpoint_does_not_retrieve_plan_store_or_inject(monkeypatch):
    import memory

    monkeypatch.setenv("INCIDENT_ZERO_KNOWLEDGE", "0")

    def forbidden(*args, **kwargs):
        raise AssertionError("Disabled knowledge performed work from stale checkpoint state")

    monkeypatch.setattr(knowledge_context, "index", forbidden)
    monkeypatch.setattr(knowledge_context, "load_env", forbidden)
    monkeypatch.setattr(memory, "MemoryStore", forbidden)

    class Router:
        complete = forbidden

    report = json.loads((ROOT / "reports/payment-failure-r6/report.json").read_text(encoding="utf-8"))
    report["knowledge_consulted"] = consultation()
    original = deepcopy(report)
    state = {"knowledge_context": consultation(), "report": report}
    planned, selections = knowledge_context.prepare_plan(report, Router())
    assert planned == original and selections is None
    assert knowledge_context.remember(state) == {}
    fresh_report = {"limitations": [], "agent": {}}
    assert knowledge_context.attach_context(fresh_report, state) == fresh_report
    context = {"finding": "Observed recommendation container exited"}
    messages = knowledge_context.investigation_messages(context, state, "base system")
    assert messages == [
        {"role": "system", "content": "base system"},
        {"role": "user", "content": "<telemetry>\n" + json.dumps(context, separators=(",", ":")) + "\n</telemetry>"},
    ]
    assert report == original


def test_service_specific_runbook_cannot_support_another_service(tmp_path):
    index = KnowledgeIndex(tmp_path / "index.sqlite")
    index.build()
    refs = index.search("payment recommendation", section="remediation", runbook_k=15,
                        memory_k=0, service_k=0)["runbook_refs"]
    wrong = next(ref for ref in refs if ref["id"] == "kb:payment#remediation")
    correct = next(ref for ref in refs if ref["id"] == "kb:recommendation#remediation")
    assert "restart_service" in wrong["action_types"]
    assert wrong["applies_to"] == ["payment"]
    report = json.loads((ROOT / "reports/container-stopped-r3/report.json").read_text(encoding="utf-8"))
    report["runbook_refs"] = [wrong, correct]
    selection = {"citation_id": wrong["id"], "action_type": "restart_service", "target": "recommendation"}
    rejected = propose(report, knowledge_selections=[selection])
    assert rejected["proposed_action"]["target"] == "recommendation"
    assert wrong["id"] not in rejected["proposed_action"]["reason"]
    assert any("Runbook/policy disagreement" in note for note in rejected["limitations"])
    accepted = propose(report, knowledge_selections=[{**selection, "citation_id": correct["id"]}])
    assert correct["id"] in accepted["proposed_action"]["reason"]


def test_resumed_memory_reloads_known_secrets_without_checkpointing_them(monkeypatch):
    import memory

    monkeypatch.setenv("INCIDENT_ZERO_KNOWLEDGE", "1")
    monkeypatch.setattr(knowledge_context, "load_env", lambda: {
        "UNIT_TEST_API_KEY": "test-secret-sentinel", "PUBLIC_CONFIGURATION": "public-value"})
    monkeypatch.setattr(knowledge_context, "index", lambda: object())
    captured = {}

    class Store:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def remember(self, report, **kwargs):
            captured["report"] = deepcopy(report)

    monkeypatch.setattr(memory, "MemoryStore", Store)
    state = {"report": {"knowledge_consulted": consultation()}}
    original = deepcopy(state)
    result = knowledge_context.remember(state)
    assert captured["secrets"] == ("test-secret-sentinel",)
    assert state == original
    assert "test-secret-sentinel" not in json.dumps(result)
    assert "test-secret-sentinel" not in json.dumps(captured["report"])
