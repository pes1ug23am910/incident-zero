from copy import deepcopy

import pytest

from agent.policy import POLICY, quick_approval_line, select_action, propose
from agent.risk import assess


def report(component="ad", category="application_flag", confidence=0.9, evidence=None):
    cause = {
        "component": component, "category": category, "cause": "Observed failure",
        "confidence_model": confidence, "confidence_evidence": confidence,
        "confidence": confidence, "evidence_ids": [], "explains_symptoms": [],
    }
    return {"root_cause": cause, "root_causes": [cause], "status": "diagnosed",
            "evidence": evidence or [], "symptoms": []}


@pytest.mark.parametrize(("component", "category", "confidence", "tier"), [
    ("ad", "application_flag", 0.9, 1),
    ("product-catalog", "application_flag", 0.75, 1),
    ("payment", "application_flag", 0.9, 2),
    ("recommendation", "container_down", 0.9, 2),
    ("recommendation", "resource_starvation", 0.9, 3),
    ("ad", "application_flag", 0.59, 3),
    ("ad", "application_flag", 0.6, 2),
    ("ad", "application_flag", 0.749, 2),
])
def test_tiers(component, category, confidence, tier):
    result = propose(report(component, category, confidence))
    assert result["impact"]["tier"] == tier
    assert result["impact"]["confidence"] == confidence
    if tier == 3:
        assert result["status"] == "needs_human"
        assert result["proposed_action"] is None
        assert result["proposed_actions"] == []
        assert "Runbook:" in result["escalation_note"]


def test_cache_restart_needs_stopped_evidence_to_avoid_new_state_risk():
    cache = report("valkey-cart", "dependency_unavailable")
    assert assess(cache)["tier"] == 3
    cache["evidence"] = [{"id": "container:valkey-cart:Status=exited"}]
    result = propose(cache)
    assert result["impact"]["tier"] == 2
    assert result["impact"]["data_risk"] == "none"
    assert result["proposed_action"]["target"] == "valkey-cart"
    cache["evidence"].append({"id": "container:valkey-cart:Status=running"})
    assert assess(cache)["tier"] == 3


def test_effective_confidence_cannot_be_raised_by_model_or_existing_proposal():
    data = report()
    data["root_causes"][0]["confidence_evidence"] = 0.4
    data["proposed_action"] = {"type": "restart_service", "target": "payment"}
    assert propose(data)["impact"]["tier"] == 3
    assert propose(data)["proposed_action"] is None


def test_multicause_escalates_and_never_proposes():
    data = report("payment")
    data["root_causes"].append(report("recommendation", "container_down")["root_cause"])
    result = propose(data)
    assert result["impact"]["blast_radius"] == "multi_service"
    assert result["impact"]["tier"] == 3
    assert result["proposed_actions"] == []


def test_callers_inheriting_errors_do_not_create_additional_causes():
    data = report("payment")
    data["symptoms"] = [{"service": "checkout"}, {"service": "frontend"}]
    assert assess(data)["tier"] == 2


def test_propose_is_pure_and_uses_only_closed_labels():
    original = report()
    before = deepcopy(original)
    result = propose(original)
    assert original == before
    assert result["proposed_action"]["type"] == "toggle_flag"
    assert result["proposed_action"]["parameters"] == {"service": "ad"}
    assert result["proposed_action"]["reason"] == "disable the failure switch for ad"
    assert "toggle_flag on ad:" in quick_approval_line(result["proposed_action"])
    assert "Restore normal application behavior" in quick_approval_line(result["proposed_action"])
    assert select_action({"component": "ad;restart payment", "category": "application_flag"}) is None
    assert select_action({"component": "payment", "category": "execute"}) is None


def test_no_incident_never_gets_a_proposal():
    data = report()
    data["status"] = "no_incident"
    result = propose(data)
    assert result["status"] == "no_incident"
    assert result["proposed_action"] is None
    assert result["proposed_actions"] == []
    assert result["impact"]["score"] == 0


def test_every_action_needs_human():
    assert POLICY["auto_approve_tiers"] == []


def test_explicit_data_risk_can_only_strengthen_policy():
    data = report("payment")
    data["impact"] = {"data_risk": "payment"}
    assert propose(data)["impact"]["tier"] == 3
