"""Pure action selection from validated categories, never telemetry prose.

These functions only build proposals. They do not read settings, mint approval
tokens, call an executor, or change the running application.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


POLICY_PATH = Path(__file__).resolve().parents[1] / "action_api" / "policy.yaml"
POLICY = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
SERVICE_CRITICALITY: dict[str, str] = POLICY["service_criticality"]
SERVICES: tuple[str, ...] = tuple(SERVICE_CRITICALITY)
CAUSE_CATEGORIES = (
    "application_flag", "container_down", "restart_loop", "dependency_unavailable",
    "network", "resource_starvation", "load", "unknown",
)


def effective_confidence(cause: dict[str, Any]) -> float:
    """Fail closed on invalid or contradictory confidence fields."""
    values = [cause.get("confidence", 0)]
    values.extend(cause[key] for key in ("confidence_model", "confidence_evidence", "confidence_review") if key in cause)
    try:
        numbers = [float(value) for value in values]
        if any(not 0 <= value <= 1 for value in numbers):
            return 0.0
        return min(numbers)
    except (TypeError, ValueError):
        return 0.0


def causes_for(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Prefer the current multi-cause contract, with a legacy alias fallback."""
    if "root_causes" in report:
        return list(report["root_causes"] or [])
    return [report["root_cause"]] if report.get("root_cause") else []


def select_action(cause: dict[str, Any]) -> dict[str, Any] | None:
    """Choose a proposal from two closed labels: component and category.

    The model's suggested action, reasons, log text and span attributes have no
    role in this decision. Even a known target is never passed to a shell here.
    """
    target = cause.get("component")
    category = cause.get("category")
    if not isinstance(target, str) or not isinstance(category, str) or target not in SERVICES:
        return None
    if category == "application_flag":
        action_type = "toggle_flag"
        parameters = {"service": target}
        reason = f"disable the failure switch for {target}"
        prediction = f"Restore normal application behavior in {target}; confirm with fresh telemetry."
        risk = "Configuration change requires human approval and a recorded rollback value."
    elif category in {"container_down", "restart_loop", "dependency_unavailable"}:
        action_type = "restart_service"
        parameters = {"service": target}
        reason = f"Restore the diagnosed unavailable component {target}."
        prediction = f"Start a fresh {target} process and restore its availability to callers."
        risk = "Restart may interrupt in-flight work; review state and evidence before approval."
    elif category in {"load", "traffic_flood"}:
        action_type = "throttle_load"
        target = "load-generator"
        parameters = dict(POLICY["load_reduction"])
        reason = "Reduce generated request volume to relieve the observed overload."
        prediction = f"Reduce the load generator to {parameters['users']} concurrent user(s)."
        risk = "Reduces test traffic; record the current traffic level before an approved change."
    else:
        return None
    return {
        "type": action_type,
        "target": target,
        "parameters": parameters,
        "reason": reason,
        "risk": risk,
        "dry_run": {"performed": False, "predicted_effect": prediction},
    }


def runbook_suggestion(causes: list[dict[str, Any]]) -> str:
    categories = {cause.get("category") for cause in causes}
    if "resource_starvation" in categories:
        return "Runbook: inspect CPU quotas, throttling, memory pressure and process usage; have an operator restore the resource baseline."
    if categories & {"network", "network_degradation"}:
        return "Runbook: inspect the affected network path, packet loss, latency and timeouts before an operator changes networking."
    if len({cause.get("component") for cause in causes}) > 1:
        return "Runbook: review each independent cause and dependency separately; plan and approve one recovery step at a time."
    return "Runbook: collect fresh component and dependency traces, logs and container state; review persistence and rollback before selecting a change."


def _propose(report: dict[str, Any]) -> dict[str, Any]:
    """Return a new report with policy-generated proposals and impact.

    Aggregate tier 3 suppresses every candidate, including in combined incidents.
    The human can review those findings, but this brain-only build cannot act.
    """
    from .risk import assess

    result = deepcopy(report)
    causes = causes_for(result)
    impact = assess(result)
    result["impact"] = impact
    result["proposed_actions"] = []
    result["proposed_action"] = None
    if result.get("status") == "no_incident":
        return result
    if impact["tier"] == 3 or result.get("status") in {"needs_human", "aborted"}:
        if result.get("status") != "aborted":
            result["status"] = "needs_human"
        previous = result.get("escalation_note")
        note = f"No action proposed. {impact['rationale']} {runbook_suggestion(causes)}"
        result["escalation_note"] = f"{previous} {note}" if previous else note
        return result
    priorities = {"critical": 0, "core": 1, "auxiliary": 2}
    ordered = sorted(causes, key=lambda cause: (
        priorities.get(SERVICE_CRITICALITY.get(cause.get("component")), 0),
        -effective_confidence(cause),
    ))
    result["proposed_actions"] = [action for cause in ordered if (action := select_action(cause))]
    result["proposed_action"] = result["proposed_actions"][0] if result["proposed_actions"] else None
    if not result["proposed_actions"]:
        result["status"] = "needs_human"
        result["escalation_note"] = runbook_suggestion(causes)
    return result


def propose(report: dict[str, Any], *, knowledge_selections=None) -> dict[str, Any]:
    """Validate retrieved remediation against the existing closed policy.

    A citation can explain a permitted proposal. It cannot authorize a new
    operation, target, parameter, or risk-tier exception.
    """
    result = _propose(report)
    if knowledge_selections is None:
        return result
    refs = {ref['id']: ref for ref in result.get('runbook_refs', [])}
    approved = {(action['type'], action['target']): action for action in result['proposed_actions']}
    causes = causes_for(result)
    matched = set()
    for selection in knowledge_selections:
        citation = selection['citation_id']
        ref = refs.get(citation, {})
        choice = (selection['action_type'], selection['target'])
        related = [cause for cause in causes if (candidate := select_action(cause))
                   and (candidate['type'], candidate['target']) == choice]
        lifecycle = {'container_down', 'restart_loop', 'dependency_unavailable'}
        applies = any(cause['component'] in ref.get('applies_to', []) and (
            ref.get('category') in ('service', cause['category']) or
            ref.get('category') in lifecycle and cause['category'] in lifecycle) for cause in related)
        valid = (ref.get('section') == 'remediation' and choice in approved
                 and choice[0] in ref.get('action_types', []) and applies)
        if valid:
            action = approved[choice]
            action['reason'] += f" Runbook: {citation}; validated against the action allowlist."
            matched.add(choice)
        else:
            result['limitations'].append(
                f"Runbook/policy disagreement: {citation} suggested {choice[0]} on {choice[1]}; "
                'policy wins. No unapproved operation, target or parameters were admitted.')
    if approved.keys() - matched:
        result['limitations'].append(
            'No matching cited runbook selection for every proposal; the evidence-based policy supplied the remaining proposal.')
    return result


def quick_approval_line(action: dict[str, Any]) -> str:
    """A T1 approval must show what changes, its target and predicted effect."""
    return f"{action['type']} on {action['target']}: {action['dry_run']['predicted_effect']} Approve [y/N]?"
