"""Offline memory provenance, redaction, outcome and similarity checks."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from agent.policy import select_action
from memory import MemoryStore, fingerprint
from schema.validate import fixture_resolver
from tools.redact import FLAG_NAMES

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example():
    return json.loads((ROOT / "schema/examples/valid.json").read_text(encoding="utf-8"))


@pytest.fixture
def resolver():
    return fixture_resolver(ROOT / "schema/examples/evidence_fixture.json")


@pytest.fixture
def store(tmp_path, resolver):
    from knowledge import KnowledgeIndex

    return MemoryStore(tmp_path / "store", KnowledgeIndex(tmp_path / "index.sqlite"), resolver=resolver)


def executed_report(example, *, status="fixed"):
    report = deepcopy(example)
    report["root_cause"].update(category="restart_loop", confidence=.9,
                                cause="Synthetic restart-loop example for outcome bookkeeping.")
    report["proposed_action"] = select_action(report["root_cause"])
    report["approval"].update(approved=True, approved_by="offline-test-operator", token="approval-secret",
        surface="test", mode="test", token_id="sha256:" + "a" * 64,
        requested_at="2026-10-23T13:00:03+05:30", approved_at="2026-10-23T13:00:03+05:30")
    report["action"].update(executed=True, started_at="2026-10-23T13:00:04+05:30",
                           finished_at="2026-10-23T13:00:05+05:30", action_log_ref="action_log:1")
    report["verification"].update(checked_at="2026-10-23T13:00:06+05:30", before=1, after=0,
                                  recovered=True, outcome="recovered", requests_observed=25)
    report["status"] = status
    report["resolved_at"] = "2026-10-23T13:00:07+05:30"
    if status == "rolled_back":
        report["verification"].update(rolled_back=True, recovered=False, outcome="escalated")
        report["resolved_at"] = None
    return report


def test_validated_report_is_written_and_immediately_searchable(store, example):
    record = store.remember(example, report_path="reports/example/report.json")
    stored = json.loads((store.root / (record["memory_id"] + ".json")).read_text(encoding="utf-8"))
    assert record == stored
    assert record["component"] == "payment" and record["hint_only"] is True
    assert record["action_taken"] == []
    assert record["verification"]["recovered"] is None
    assert record["verification_outcome"] == "unknown"
    assert record["outcome"] == "escalated" and record["seconds_to_recovery"] is None
    hits = store.similar("payment container_status")
    assert hits[0]["id"] == record["citation_id"]
    assert example["incident_id"] not in json.dumps(record)
    assert "report_path" not in record and "incident_id" not in record
    assert hits[0]["score"] > 0


def test_invalid_report_cannot_create_memory_or_index(store, example):
    example["status"] = "fixed"
    with pytest.raises(ValueError, match="validated report"):
        store.remember(example)
    assert not store.root.exists()
    assert not store.index.path.exists()


def test_missing_evidence_cannot_create_memory(store, example):
    with pytest.raises(ValueError, match="validated report"):
        store.remember(example, resolver=lambda _: None)
    assert not store.root.exists()


def test_proposed_action_is_not_stored_as_executed(store, example):
    example["root_cause"].update(category="restart_loop", confidence=.9)
    example["status"] = "diagnosed"
    example["proposed_action"] = select_action(example["root_cause"])
    record = store.remember(example)
    assert record["action_taken"] == []
    assert record["outcome"] == "unknown"
    assert record["seconds_to_recovery"] is None


def test_recovery_label_without_validated_fixed_status_is_not_promoted(store, example):
    example["root_cause"]["confidence"] = .9
    example["status"] = "diagnosed"
    example["verification"].update(recovered=True, outcome="recovered")
    record = store.remember(example)
    assert record["verification_outcome"] == "recovered"
    assert record["outcome"] == "unknown"
    assert record["seconds_to_recovery"] is None
    assert not record["action_taken"]


@pytest.mark.parametrize("status,outcome,seconds", [("fixed", "recovered", 7), ("rolled_back", "rolled_back", None)])
def test_actual_actions_and_measured_outcomes_preserved(store, example, status, outcome, seconds):
    report = executed_report(example, status=status)
    record = store.remember(report)
    assert record["action_taken"][0]["type"] == "restart_service"
    assert record["action_taken"][0]["target"] == "payment"
    assert record["action_taken"][0]["action_log_ref"] == "action_log:1"
    assert record["outcome"] == outcome
    assert record["seconds_to_recovery"] == seconds
    assert "approval-secret" not in json.dumps(record)


def test_unknown_recovery_after_execution_stays_unknown(store, example):
    report = executed_report(example, status="needs_human")
    report["verification"].update(recovered=None, checked_at=None, before=None, after=None)
    report["verification"].pop("outcome")
    report["resolved_at"] = None
    record = store.remember(report)
    assert record["action_taken"]
    assert record["verification_outcome"] == "unknown"
    assert record["verification"]["recovered"] is None
    assert record["outcome"] == "escalated" and record["seconds_to_recovery"] is None


def test_action_history_preserves_actual_attempts_and_skips_rejected_proposals(store, example):
    report = executed_report(example, status="rolled_back")
    report["action_history"] = [
        {"index": 0, "decision": {"decision": "approve", "token": "private-approval"},
         "execution": deepcopy(report["action"]), "verification": deepcopy(report["verification"]), "error": {}},
        {"index": 1, "decision": {"decision": "reject"}, "execution": {"rejected": True},
         "verification": {}, "error": {}},
    ]
    record = store.remember(report)
    assert len(record["action_taken"]) == 1
    assert record["action_taken"][0]["verification"]["rolled_back"] is True
    assert record["action_taken"][0]["verification"]["recovered"] is False
    assert "private-approval" not in json.dumps(record)


def test_repeated_incident_updates_one_json_and_one_retrieval_hit(store, example):
    original = store.remember(example)
    report = executed_report(example)
    store.remember(report)
    assert len(list(store.root.glob("*.json"))) == 1
    hits = store.similar("payment")
    assert [hit["id"] for hit in hits] == [original["citation_id"]]
    assert hits[0]["outcome"] == "recovered"


def test_redaction_happens_before_storage_and_index(store, example, monkeypatch):
    store.secrets = ("local-secret-sentinel",)
    example["symptoms"][0]["observed"] += " Bearer private-auth-token local-secret-sentinel"
    captured = []
    original = store.index.upsert_memory

    def inspect(record, **kwargs):
        captured.append(deepcopy(record))
        return original(record, **kwargs)

    monkeypatch.setattr(store.index, "upsert_memory", inspect)
    record = store.remember(example, report_path="reports/local-secret-sentinel/report.json")
    for text in (json.dumps(record), json.dumps(captured), next(store.root.glob("*.json")).read_text()):
        assert "local-secret-sentinel" not in text
        assert "private-auth-token" not in text
    assert "local-secret-sentinel" in example["symptoms"][0]["observed"]


def test_configuration_disclosure_rejected_before_storage(store, example):
    example["symptoms"][0]["observed"] = FLAG_NAMES[0]
    with pytest.raises(ValueError, match="validated report") as error:
        store.remember(example)
    assert FLAG_NAMES[0] not in str(error.value)
    assert not store.root.exists()


def test_fingerprint_uses_observations_not_hint_or_diagnosis(example):
    example["symptoms"][0].update(service="recommendation", signal="container_status", observed="exited")
    example["alert"].update(service="recommendation", signal="container_status", observed=0)
    example["root_cause"]["component"] = "payment"
    example["memory_refs"] = [{"text": "payment always causes these errors"}]
    example["investigation"] = []
    result = fingerprint(example)
    assert "recommendation" in result and "exited" in result
    assert "payment" not in result


def test_fingerprint_is_stable_across_values_order_and_redacts():
    observation = {"symptoms": [
        {"service": "cart", "signal": "error_rate", "observed": "0.4"},
        {"service": "checkout", "signal": "latency", "observed": "112.32"}],
        "findings": [{"result": {"data": [{"body": "Connection refused"}, {"body": FLAG_NAMES[0]}]}}]}
    changed = deepcopy(observation)
    changed["symptoms"].reverse()
    changed["symptoms"][0]["observed"] = "320.3"
    assert fingerprint(observation) == fingerprint(changed)
    assert "connection refused" in fingerprint(observation)
    assert FLAG_NAMES[0].casefold() not in fingerprint(observation)


def test_fingerprint_recovers_complete_errors_from_truncated_bundle_summaries():
    observation = {"investigation": [{"finding": '[{"body": "Connection refused", "details": "truncated'}],
                   "evidence": [{"summary": '{"exception.message": "Payment request failed", "nested":'}]}
    result = fingerprint(observation)
    assert "connection refused" in result
    assert "payment request failed" in result
    assert "truncated" not in result


def test_default_validation_never_falls_back_to_network(tmp_path, example, monkeypatch):
    import requests

    def forbidden(*args, **kwargs):
        raise AssertionError("Memory attempted a network read")

    monkeypatch.setattr(requests.Session, "request", forbidden)
    store = MemoryStore(tmp_path / "store")
    with pytest.raises(ValueError, match="validated report"):
        store.remember(example, report_path=tmp_path / "reports/missing/report.json")
    assert not store.root.exists()


def test_retained_bundle_memory_reads_only_exact_evidence_files(tmp_path, monkeypatch):
    from tools import evidence
    from knowledge import KnowledgeIndex

    monkeypatch.setattr(evidence, "ROOT", ROOT)
    report_path = ROOT / "reports/payment-failure-r6/report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    opened = []
    original = Path.read_text
    index = KnowledgeIndex(tmp_path / "index.sqlite")
    index.build()

    def track(path, *args, **kwargs):
        opened.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", track)
    store = MemoryStore(tmp_path / "store", index)
    record = store.remember(report, report_path=report_path)
    assert record["component"] == report["root_cause"]["component"]
    assert record["verification_outcome"] == "unknown"
    assert report_path not in opened
    for path in opened:
        assert path == ROOT / "schema/incident_report.schema.json" or path.parent == report_path.parent / "evidence"


@pytest.mark.parametrize("identifier", ["../escape", "..\\escape", "CON", "payment."])
def test_incident_filename_is_confined(store, example, identifier):
    example["incident_id"] = identifier
    record = store.remember(example)
    assert len(record["memory_id"]) == 64
    assert list(store.root.glob("*.json")) == [store.root / (record["memory_id"] + ".json")]
