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
    value["alert"]["detected_at"] = "2026-10-23T12:12:23+00:00"
    value["run_id"] = "runs/operator-only-run-marker"
    router = Router()
    investigation = Investigation(tmp_path, router)
    monkeypatch.setattr(investigation, "read", lambda *a: ({"tool": "get_logs"}, {}, {"data": []}))
    investigation.investigate(value)
    transcript = json.dumps(router.messages)
    assert "operator-only-answer-marker" not in transcript
    assert "operator-only-run-marker" not in transcript
    assert "<telemetry>" in transcript
    assert "2026-10-23T12:12:23+00:00" in transcript


def test_finish_does_not_hide_unexplained_independent_service(tmp_path, monkeypatch):
    import agent.graph as graph
    monkeypatch.setattr(graph, "ROOT", tmp_path)
    value = state()
    value["health"]["data"].append({"service": "recommendation", "status": "exited"})
    value["unexplained"] = ["payment", "recommendation"]
    value["evidence"] = {
        "trace:payment": {"source": "jaeger", "services": ["payment"], "strength": .95},
        "log:otel/payment": {"source": "opensearch", "services": ["payment"], "strength": .9},
    }
    router = Router({"name": "finish", "arguments": {"reason": "Payment failure explained",
        "hypotheses": [{"component": "payment", "cause": "Payment application error",
            "category": "application_flag", "confidence_model": .95,
            "evidence_ids": list(value["evidence"]), "explains_symptoms": ["payment"]}],
        "no_incident": False, "limitations": []}})
    update = Investigation(tmp_path, router).investigate(value)
    assert update["unexplained"] == ["recommendation"]
    assert not update.get("done", False)
    assert route_investigate({**value, **update}) == "investigate"


def test_finish_cannot_claim_clean_without_successful_trace(tmp_path, monkeypatch):
    import agent.graph as graph
    monkeypatch.setattr(graph, "ROOT", tmp_path)
    value = state()
    value.update(clean=True, health={"data": [{"service": "frontend", "error_rate": 0, "rps": 4}]},
                 alert={"signal": "no_alert", "service": "frontend"}, unexplained=[])
    router = Router({"name": "finish", "arguments": {"reason": "Overview appears clean",
                    "hypotheses": [], "no_incident": True, "limitations": []}})
    update = Investigation(tmp_path, router).investigate(value)
    assert not update.get("clean", False)
    assert not update.get("done", False)


@pytest.mark.parametrize("proposals,expected", [([], "report"), ([{"type": "restart_service"}], "dry_run")])
def test_only_actionable_reports_enter_preview_and_approval(proposals, expected):
    assert route_proposal({"report": {"proposed_actions": proposals}}) == expected


def supported_finish_state(confidence=.7):
    value = state()
    value['evidence'] = {
        'trace:payment': {'source': 'jaeger', 'services': ['payment'], 'strength': .95},
        'log:otel/payment': {'source': 'opensearch', 'services': ['payment'], 'strength': .9},
        'metric:payment': {'source': 'prometheus', 'services': ['payment'], 'strength': .9},
    }
    decision = {'name': 'finish', 'arguments': {'reason': 'Reassess all current observations.',
        'hypotheses': [{'component': 'payment', 'cause': 'Local application failure.',
            'category': 'application_flag', 'confidence_model': confidence,
            'evidence_ids': list(value['evidence']), 'explains_symptoms': ['payment']}],
        'no_incident': False, 'limitations': []}}
    return value, decision


@pytest.mark.parametrize('other_symptom', [None, 'recommendation'])
def test_finish_self_coverage_does_not_require_redundant_model_label(tmp_path, monkeypatch, other_symptom):
    monkeypatch.setattr('agent.graph.ROOT', tmp_path)
    value, decision = supported_finish_state(.9)
    value['symptom_services'] = ['payment', 'frontend'] + ([other_symptom] if other_symptom else [])
    decision['arguments']['hypotheses'][0]['explains_symptoms'] = ['frontend']
    investigation = Investigation(tmp_path, Router(decision))
    monkeypatch.setattr(investigation, 'read', lambda *args: pytest.fail('Finish must not perform another read'))
    update = investigation.investigate(value)
    assert update['hypotheses'][0]['explains_symptoms'] == ['frontend', 'payment']
    assert update['unexplained'] == ([other_symptom] if other_symptom else [])
    assert update.get('done', False) is (other_symptom is None)
    if other_symptom:
        assert update['finish_blocked']


def test_finish_feedback_identifies_model_bottleneck_without_changing_confidence(tmp_path, monkeypatch):
    monkeypatch.setattr('agent.graph.ROOT', tmp_path)
    value, decision = supported_finish_state()
    investigation = Investigation(tmp_path, Router(decision))
    first = investigation.investigate(value)
    assert 'model confidence 0.70' in first['validation_error']
    assert 'evidence confidence is 0.95' in first['validation_error']
    assert 'seek independent positive support' not in first['validation_error']
    assert 'Symptoms without a proposed explanation' not in first['validation_error']
    assert first['hypotheses'][0]['confidence'] == .7
    assert not first['finish_blocked']  # One reassessment can use existing evidence.
    second = investigation.investigate({**value, **first})
    assert second['finish_blocked'] and not second['done']
    assert second['hypotheses'][0]['confidence'] == .7


def test_finish_feedback_identifies_evidence_bottleneck_and_requires_read(tmp_path, monkeypatch):
    monkeypatch.setattr('agent.graph.ROOT', tmp_path)
    value, decision = supported_finish_state(.9)
    value['evidence'] = {'trace:payment': value['evidence']['trace:payment']}
    decision['arguments']['hypotheses'][0]['evidence_ids'] = ['trace:payment']
    update = Investigation(tmp_path, Router(decision)).investigate(value)
    assert 'evidence confidence 0.55' in update['validation_error']
    assert 'seek independent positive support' in update['validation_error']
    assert update['finish_blocked']


def test_finish_feedback_does_not_consume_malformed_decision_repair(tmp_path, monkeypatch):
    monkeypatch.setattr('agent.graph.ROOT', tmp_path)
    value, decision = supported_finish_state()
    router = Router(decision)
    investigation = Investigation(tmp_path, router)
    feedback = investigation.investigate(value)
    router.decision['arguments']['hypotheses'].append({
        'component': 'checkout', 'cause': 'Unobserved possibility.', 'category': 'application_flag',
        'confidence_model': .3, 'evidence_ids': [], 'explains_symptoms': ['checkout']})
    first_error = investigation.investigate({**value, **feedback})
    assert first_error['decision_repair_used']
    assert first_error.get('stopped_because') != 'error'
    second_error = investigation.investigate({**value, **feedback, **first_error})
    assert second_error['stopped_because'] == 'error'


def test_third_finish_cannot_bypass_required_read_by_raising_model_confidence(tmp_path, monkeypatch):
    monkeypatch.setattr('agent.graph.ROOT', tmp_path)
    value, decision = supported_finish_state()
    router = Router(decision)
    investigation = Investigation(tmp_path, router)
    first = investigation.investigate(value)
    second = investigation.investigate({**value, **first})
    assert second['finish_blocked']
    router.decision['arguments']['hypotheses'][0]['confidence_model'] = .9
    blocked = {**value, **first, **second}
    third = investigation.investigate(blocked)
    assert 'not offered' in third['validation_error']
    assert not third.get('done') and 'hypotheses' not in third
    assert blocked['hypotheses'][0]['confidence'] == .7
    fourth = investigation.investigate({**blocked, **third})
    assert fourth['stopped_because'] == 'error'


@pytest.mark.parametrize('malformation', ['missing_no_incident', 'string_no_incident'])
def test_finish_arguments_use_schema_and_repeated_malformed_finish_abstains(tmp_path, monkeypatch, malformation):
    monkeypatch.setattr('agent.graph.ROOT', tmp_path)
    value, decision = supported_finish_state(.9)
    if malformation == 'missing_no_incident':
        del decision['arguments']['no_incident']
    else:
        value.update(clean=True, symptom_services=[], unexplained=[],
            alert={'signal': 'no_alert', 'service': 'frontend'},
            health={'data': [{'service': 'frontend', 'rps': 5, 'error_rate': 0}]},
            findings=[{'tool': 'get_traces', 'result': {'data': [{'first_error_span': None}]}}])
        decision['arguments'].update(no_incident='false', hypotheses=[])
    investigation = Investigation(tmp_path, Router(decision))
    first = investigation.investigate(value)
    assert 'no_incident' in first['validation_error']
    assert not first.get('done') and 'clean' not in first
    assert first['decision_repair_used']
    second = investigation.investigate({**value, **first})
    assert second['stopped_because'] == 'error'


@pytest.mark.parametrize('tool', ['get_traces', 'get_logs'])
def test_late_failure_adds_only_admitted_positive_services_to_symptoms(tmp_path, monkeypatch, tool):
    monkeypatch.setattr('agent.graph.ROOT', tmp_path)
    value = state()
    value.update(alert={'signal': 'container_status', 'service': 'valkey-cart',
                        'detected_at': '2026-10-23T12:12:23Z', 'window_s': 120},
                 symptom_services=['valkey-cart'], unexplained=['valkey-cart'], clean=True)
    decision = {'name': tool, 'arguments': {'reason': 'Check delayed dependency failures.',
        'hypotheses': [], 'service': 'cart', 'lookback_s': 600}}
    evidence = {
        'failure': {'services': ['cart', 'valkey-cart', 'frontend'],
                    'positive_services': ['cart', 'valkey-cart', 'unknown-service'], 'strength': .9},
        'healthy': {'services': ['payment'], 'positive_services': ['payment'], 'strength': .3},
        'planted': {'services': ['ad'], 'positive_services': ['ad'], 'strength': 0},
        'old': {'services': ['currency'], 'positive_services': ['currency'], 'strength': .9,
                'data': {'@timestamp': '2026-10-23T12:00:00Z'}},
    }
    investigation = Investigation(tmp_path, Router(decision))
    monkeypatch.setattr(investigation, 'read', lambda *args: ({'tool': tool}, evidence, {'data': []}))
    update = investigation.investigate(value)
    assert update['symptom_services'] == ['cart', 'valkey-cart']
    assert update['unexplained'] == ['cart', 'valkey-cart']
    assert update['hypotheses'] == []  # Observations do not invent causes or coverage.
    assert not update['clean']


def test_ordinary_resource_metric_does_not_create_a_new_symptom(tmp_path, monkeypatch):
    monkeypatch.setattr('agent.graph.ROOT', tmp_path)
    decision = {'name': 'get_metrics', 'arguments': {'reason': 'Inspect utilization.',
        'hypotheses': [], 'promql': 'cpu_percent'}}
    investigation = Investigation(tmp_path, Router(decision))
    evidence = {'metric': {'services': ['ad'], 'positive_services': ['ad'], 'strength': .5}}
    monkeypatch.setattr(investigation, 'read', lambda *args: ({'tool': 'get_metrics'}, evidence, {'data': []}))
    update = investigation.investigate(state())
    assert update['tool_calls_used'] == 2
    assert 'symptom_services' not in update
