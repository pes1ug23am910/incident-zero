"""Exercise graph safety boundaries without remote models or Docker reads."""

from copy import deepcopy
import json

import pytest

from agent.graph import Investigation, route_investigate, route_proposal
from agent.evidence import uncovered


class Router:
    def __init__(self, decision=None):
        self.calls = 0
        self.messages = None
        self.decision = decision or {"name": "get_logs", "arguments": {
            "reason": "Corroborate the failed call with the component log.", "hypotheses": [],
            "service": "payment", "lookback_s": 120}}

    def complete(self, *args):
        self.calls += 1
        self.messages = args[0]
        return deepcopy(self.decision)


def state(calls=1):
    return {"tool_calls_used": calls, "alert": {"signal": "error_rate", "service": "payment"},
            "findings": [], "hypotheses": [], "evidence": {}, "unexplained": ["payment"],
            "health": {"data": [{"service": "payment", "error_rate": .5}]},
            "seen_calls": [], "clean": False}


@pytest.mark.parametrize("patch,expected", [({}, "investigate"),
    ({"done": True}, "diagnose"), ({"stop_signal": True}, "diagnose"),
    ({"stopped_because": "budget"}, "diagnose"), ({"stopped_because": "error"}, "diagnose"),
    ({"validation_error": "repair once"}, "investigate")])
def test_routes_are_pure_and_cover_all_exit_conditions(patch, expected):
    value = {**state(), **patch}
    original = deepcopy(value)
    assert route_investigate(value) == expected
    assert value == original


@pytest.mark.parametrize("confidence,expected", [(.749, ["payment"]), (.75, [])])
def test_confidence_coverage_boundary(confidence, expected):
    assert uncovered([{"confidence": confidence, "explains_symptoms": ["payment"]}], ["payment"]) == expected


@pytest.mark.parametrize("calls,router_calls,read_calls", [(11, 1, 1), (12, 0, 0)])
def test_twelve_tool_budget_counts_observe_and_prevents_extra_model_call(tmp_path, monkeypatch, calls, router_calls, read_calls):
    import agent.graph as graph
    monkeypatch.setattr(graph, "ROOT", tmp_path)
    router = Router()
    investigation = Investigation(tmp_path, router)
    reads = []
    def read(*args):
        reads.append(args)
        return {"tool": "get_logs"}, {}, {"data": []}
    monkeypatch.setattr(investigation, "read", read)
    update = investigation.investigate(state(calls))
    assert router.calls == router_calls and len(reads) == read_calls
    if calls == 12:
        assert route_investigate({**state(calls), **update}) == "diagnose"
    else:
        assert update["tool_calls_used"] == 12


def test_stop_prevents_model_and_tool_calls(tmp_path, monkeypatch):
    import agent.graph as graph
    monkeypatch.setattr(graph, "ROOT", tmp_path)
    (tmp_path / "STOP").touch()
    router = Router()
    update = Investigation(tmp_path, router).investigate(state())
    assert update["stop_signal"] is True and router.calls == 0


def test_repeated_read_stops_before_dispatch(tmp_path, monkeypatch):
    import agent.graph as graph
    monkeypatch.setattr(graph, "ROOT", tmp_path)
    value = state()
    value["seen_calls"] = [json.dumps(["get_logs", {"service": "payment", "lookback_s": 120}], sort_keys=True)]
    investigation = Investigation(tmp_path, Router())
    monkeypatch.setattr(investigation, "read", lambda *args: pytest.fail("duplicate tool read"))
    update = investigation.investigate(value)
    assert update["done"] and "Repeated" in update["validation_error"]


def test_malformed_structured_tool_args_get_one_repair_then_abstain(tmp_path, monkeypatch):
    import agent.graph as graph
    monkeypatch.setattr(graph, "ROOT", tmp_path)
    router = Router({"name": "get_logs", "arguments": {
        "reason": "Read a log", "hypotheses": [], "service": "unknown-host"}})
    investigation = Investigation(tmp_path, router)
    monkeypatch.setattr(investigation, "read", lambda *args: pytest.fail("invalid tool arguments were dispatched"))
    first = investigation.investigate(state())
    assert first["validation_error"]
    assert route_investigate({**state(), **first}) == "investigate"
    second = investigation.investigate({**state(), **first})
    assert second["stopped_because"] == "error"
    assert route_investigate({**state(), **second}) == "diagnose"


def test_fabricated_hypothesis_cannot_reach_a_tool(tmp_path, monkeypatch):
    import agent.graph as graph
    monkeypatch.setattr(graph, "ROOT", tmp_path)
    router = Router()
    router.decision["arguments"]["hypotheses"] = [{"component": "payment", "cause": "Failure",
        "category": "application_flag", "confidence_model": .99,
        "evidence_ids": ["trace:invented"], "explains_symptoms": ["payment"]}]
    investigation = Investigation(tmp_path, router)
    monkeypatch.setattr(investigation, "read", lambda *args: pytest.fail("planted evidence reached dispatch"))
    update = investigation.investigate(state())
    assert "not returned" in update["validation_error"]
    assert "hypotheses" not in update


def test_operator_metadata_never_enters_model_prompt(tmp_path, monkeypatch):
    import agent.graph as graph
    monkeypatch.setattr(graph, "ROOT", tmp_path)
    value = state()
    value["incident_id"] = "operator-only-answer-marker"
    value["alert"]["incident_id"] = "operator-only-answer-marker"
    value["run_id"] = "runs/operator-only-run-marker"
    router = Router()
    investigation = Investigation(tmp_path, router)
    monkeypatch.setattr(investigation, "read", lambda *a: ({"tool": "get_logs"}, {}, {"data": []}))
    investigation.investigate(value)
    transcript = json.dumps(router.messages)
    assert "operator-only-answer-marker" not in transcript
    assert "operator-only-run-marker" not in transcript
    assert "<telemetry>" in transcript


def test_finish_does_not_hide_unexplained_independent_service(tmp_path, monkeypatch):
    import agent.graph as graph
    monkeypatch.setattr(graph, "ROOT", tmp_path)
    value = state()
    value["health"]["data"].append({"service": "recommendation", "status": "exited"})
   