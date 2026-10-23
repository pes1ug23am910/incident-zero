"""Offline graph lifecycle checks; these do not claim live diagnostic accuracy."""

from copy import deepcopy
import importlib

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent.graph import build_graph
from agent.policy import propose
from agent.risk import assess
from agent.run import config_for

graph_module = importlib.import_module("agent.graph")
respond_module = importlib.import_module("agent.respond")
RUN_ID = "runs/offline-persistence"


@pytest.fixture
def report():
    cause = {"component": "recommendation", "cause": "The recorded process is stopped.",
             "category": "container_down", "confidence_model": 0.95,
             "confidence_evidence": 0.9, "confidence": 0.9,
             "evidence_ids": ["container:recommendation:Status=exited", 'trace:' + 'a' * 32],
             "explains_symptoms": ["recommendation"]}
    return {
        "run_id": RUN_ID, "incident_id": "synthetic-offline-persistence",
        "alert": {"signal": "container_health", "service": "recommendation", "observed": 1,
                  "threshold": 0, "window_s": 120},
        "limitations": ["Synthetic offline checkpoint; no live measurements."],
        "root_cause": deepcopy(cause), "root_causes": [cause], "status": "diagnosed",
        "evidence": [{"id": identifier, "source": source,
                      "summary": "Synthetic stopped process and caller failure", "raw_ref": "synthetic fixture"}
                     for identifier, source in zip(cause['evidence_ids'], ['docker', 'jaeger'])],
        "proposed_action": None, "proposed_actions": [], "escalation_note": None,
        "approval": {"required": True, "requested_at": None, "approved": None,
                     "approved_by": None, "approved_at": None, "token": None},
        "action": {"executed": False, "started_at": None, "finished_at": None, "action_log_ref": None},
        "verification": {"checked_at": None, "signal": "container_health", "before": None,
                         "after": None, "recovered": None, "rolled_back": False},
    }


class OfflineInvestigation:
    """Supply deterministic observations; retain real graph and policy nodes."""
    def __init__(self, report, calls=None):
        self.report = deepcopy(report)
        self.calls = calls if calls is not None else []

    def observe(self, state):
        self.calls.append("observe")
        return {"tool_calls_used": 1, "findings": [], "evidence": {}, "audit": [{"node": "observe"}]}

    def investigate(self, state):
        self.calls.append("investigate")
        return {"done": True, "stopped_because": "confident"}

    def diagnose(self, state):
        self.calls.append("diagnose")
        return {"report": self.report, "status": self.report["status"]}

    def assess_risk(self, state):
        self.calls.append("assess_risk")
        result = deepcopy(state["report"])
        result["impact"] = assess(result)
        return {"report": result, "impact": result["impact"]}

    def propose(self, state):
        self.calls.append("propose")
        result = propose(state["report"])
        return {"report": result, "proposal": result["proposed_actions"], "status": result["status"]}


def pause_at_approval(database, report, calls=None):
    database.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(database)) as saver:
        graph = build_graph(OfflineInvestigation(report, calls), saver)
        graph.invoke({"run_id": report["run_id"], "incident_id": report["incident_id"], "alert": {}}, config_for(report["run_id"]))
        snapshot = graph.get_state(config_for(report["run_id"]))
        assert snapshot.next == ("approval",)
        return snapshot.values


def test_sqlite_reopens_same_thread_and_resumes_without_repeating_preview(tmp_path, report, monkeypatch):
    database = tmp_path / "runs" / "checkpoints.sqlite"
    calls, previews, approvals = [], [], []
    original_preview, original_approval = graph_module.dry_run, graph_module.approval
    def preview(state):
        previews.append(state["run_id"])
        return original_preview(state)
    def approval(state):
        approvals.append(state["run_id"])
        return original_approval(state)
    monkeypatch.setattr(graph_module, "dry_run", preview)
    monkeypatch.setattr(graph_module, "approval", approval)
    paused = pause_at_approval(database, report, calls)
    assert paused["dry_run"]["available"] is False
    assert "decision" not in paused
    assert previews == [RUN_ID]
    assert approvals == [RUN_ID]
    assert calls == ["observe", "investigate", "diagnose", "assess_risk", "propose"]

    # The first connection is closed. A fresh graph/connection recovers the pause.
    resumed_calls = []
    decision = {"decision": "approve", "token": "synthetic-test-value"}
    with SqliteSaver.from_conn_string(str(database)) as saver:
        graph = build_graph(OfflineInvestigation(report, resumed_calls), saver)
        persisted = graph.get_state(config_for(RUN_ID))
        assert persisted.next == ("approval",)
        assert persisted.values["report"] == paused["report"]
        graph.invoke(Command(resume=decision), config_for(RUN_ID))
        final = graph.get_state(config_for(RUN_ID))
        assert final.next == ()
        assert final.values["decision"] == decision
        assert final.values["report"]["action"]["executed"] is False
        assert final.values["report"]["approval"]["approved"] is None
        assert final.values["report"]["approval"]["token"] is None
        assert final.values["report"]["verification"]["recovered"] is None
        assert final.values["report"]["status"] == "needs_human"
        assert "No action occurred" in final.values["report"]["escalation_note"]
    assert resumed_calls == []
    assert previews == [RUN_ID]
    assert approvals == [RUN_ID, RUN_ID]  # The interrupt node restarts on resume.
    assert not (tmp_path / "action_api" / "log.jsonl").exists()


def test_responder_rejects_unknown_checkpoint_without_starting_new_investigation(tmp_path, report, offline_action_service):
    pause_at_approval(tmp_path / "runs" / "checkpoints.sqlite", report)
    wrong = {**report, "run_id": "runs/different-thread"}
    with pytest.raises(ValueError, match="mismatched resume"):
        respond_module.resume(wrong, {"decision": "reject"}, root=tmp_path, service=offline_action_service)
    with SqliteSaver.from_conn_string(str(tmp_path / "runs" / "checkpoints.sqlite")) as saver:
        graph = build_graph(OfflineInvestigation(report), saver)
        assert graph.get_state(config_for(wrong["run_id"])).values == {}
        assert graph.get_state(config_for(RUN_ID)).next == ("approval",)


def test_responder_rejects_completed_checkpoint(tmp_path, report, offline_action_service):
    paused = pause_at_approval(tmp_path / "runs" / "checkpoints.sqlite", report)
    result = respond_module.resume(paused['report'], {"decision": "reject", "reason": "Operator declined"},
                                  root=tmp_path, service=offline_action_service)
    assert result["action"]["executed"] is False
    assert result['status'] == 'needs_human'
    assert result['approval']['approved'] is False
    with pytest.raises(ValueError, match="mismatched resume"):
        respond_module.resume(result, {"decision": "reject"}, root=tmp_path, service=offline_action_service)
    assert offline_action_service.executor.mutations == []


def test_responder_refuses_unissued_approval_token_without_execution(tmp_path, report, offline_action_service):
    database = tmp_path / "runs" / "checkpoints.sqlite"
    paused = pause_at_approval(database, report)
    result = respond_module.resume(paused['report'], {"decision": "approve", "token": "unissued-test-value"},
                                  root=tmp_path, service=offline_action_service)
    assert result['status'] == 'needs_human'
    assert result['action_history'][0]['error']['reason_codes'] == ['APPROVAL_REQUIRED']
    with SqliteSaver.from_conn_string(str(database)) as saver:
        graph = build_graph(OfflineInvestigation(report), saver)
        snapshot = graph.get_state(config_for(RUN_ID))
        assert snapshot.next == ()
        assert snapshot.values["report"]["action"]["executed"] is False
    assert offline_action_service.executor.mutations == []


def test_responder_refuses_issued_approval_while_stop_is_latched(tmp_path, report, offline_action_service):
    database = tmp_path / "runs" / "checkpoints.sqlite"
    paused = pause_at_approval(database, report)
    current = paused['report']
    service = offline_action_service
    plan = current['proposed_action']
    decision = service.approve(plan, current, service.dry_run(plan, current), 'Test operator',
                               input_fn=lambda _: 'yes', output=lambda _: None)
    (tmp_path / "STOP").touch()
    result = respond_module.resume(current, decision, root=tmp_path, service=service)
    assert result['status'] == 'aborted'
    assert result['action']['executed'] is False
    assert 'STOP_LATCHED' in result['escalation_note']
    assert service.executor.mutations == []
