"""Code-owned impact assessment for a report; no action is executed here.

Business impact includes the affected journeys. Blast radius describes the
independent causes and candidate change scope: inherited caller errors alone do
not turn one failed dependency into multiple independent failing components.
Data risk describes additional risk from remediation, not lost sales. Restoring
an already stopped cache cannot discard its live process state; restarting a
live payment or cart process requires escalation. Application switches do not
authorize data edits or charge retries.
"""
from __future__ import annotations

from typing import Any

from .policy import SERVICE_CRITICALITY, SERVICES, causes_for, effective_confidence, select_action


JOURNEYS = {
    "frontend": ("browse", "cart", "checkout"),
    "frontend-proxy": ("browse", "cart", "checkout"),
    "checkout": ("checkout",),
    "payment": ("checkout", "payment"),
    "cart": ("cart", "checkout"),
    "valkey-cart": ("cart", "checkout"),
    "product-catalog": ("browse", "product details", "checkout"),
    "currency": ("pricing", "checkout"),
    "shipping": ("checkout", "shipping"),
    "recommendation": ("recommendations",),
    "ad": ("advertising",),
    "email": ("order confirmation",),
    "quote": ("shipping quote",),
    "image-provider": ("product images",),
    "load-generator": ("generated shopping traffic",),
}


def _stopped_component(report: dict[str, Any], service: str) -> bool:
    prefix = f"container:{service}:"
    stopped_fields = {"Status=exited", "Status=dead", "Status=created", "State.Status=exited", "State.Status=dead"}
    fields = {item["id"][len(prefix):] for item in report.get("evidence", [])
              if item.get("id", "").startswith(prefix)}
    # Conflicting lifecycle observations do not establish a safe stopped state.
    return bool(fields & stopped_fields) and not fields & {"Status=running", "State.Status=running", "Status=restarting"}


def assess(report: dict[str, Any]) -> dict[str, Any]:
    """Return the exact schema impact block using deterministic safety rules."""
    causes = causes_for(report)
    components = {cause.get("component", "unknown") for cause in causes}
    confidence = min((effective_confidence(cause) for cause in causes), default=0.0)
    no_incident = report.get("status") == "no_incident"
    priority = {"auxiliary": 0, "core": 1, "critical": 2}
    business = max((SERVICE_CRITICALITY.get(service, "critical") for service in components),
                   key=priority.get, default="auxiliary")
    journeys = sorted({journey for service in components for journey in JOURNEYS.get(service, ("service availability",))})
    candidates = [select_action(cause) for cause in causes]
    blast_radius = "multi_service" if len(components) > 1 else "single_service"
    if len(components) >= 5 or components & {"frontend-proxy", "otel-collector"} and len(components) > 1:
        blast_radius = "platform"
    reversibility = "instant" if all(action and action["type"] in {"toggle_flag", "throttle_load"} for action in candidates) else "self_healing"
    if not candidates or any(action is None for action in candidates):
        reversibility = "manual"

    # Additional explicit state/payment risk can only make the policy stricter.
    data_risk = report.get("impact", {}).get("data_risk", "none")
    if data_risk not in {"none", "state", "payment"}:
        data_risk = "state"
    for action in candidates:
        if action and action["type"] == "restart_service":
            target = action["target"]
            if target == "payment":
                data_risk = "payment"
            elif target in {"cart", "valkey-cart"} and not _stopped_component(report, target):
                data_risk = "state"
    reasons = []
    if blast_radius != "single_service":
        reasons.append("Independent failures span multiple services.")
    if data_risk != "none":
        reasons.append(f"The candidate change carries {data_risk} data risk.")
    if confidence < 0.6:
        reasons.append("Evidence-limited confidence is below 0.60.")
    if not candidates or any(action is None for action in candidates):
        reasons.append("The diagnosed cause has no supported safe action.")
    if any(component not in SERVICES for component in components):
        reasons.append("An unresolved component is outside the known service allowlist.")

    if no_incident:
        tier, score, business = 1, 0, "auxiliary"
        journeys, data_risk, reversibility = [], "none", "instant"
        rationale = "No actionable incident identified in the observed scope; no action or approval is requested."
    elif reasons:
        tier = 3
        score = min(100, 70 + 10 * (len(reasons) - 1))
        rationale = " ".join(reasons) + " Escalate with evidence; no action may be proposed."
    elif business == "critical" or any(action["type"] == "restart_service" for action in candidates):
        tier, score = 2, 60 if business == "critical" else 45
        rationale = "A critical service or process restart requires the full evidence table, a reviewer or the independent-source check, and explicit typed yes."
    elif confidence >= 0.75 and reversibility == "instant":
        tier, score = 1, 25 if business == "core" else 15
        rationale = "One auxiliary or core service, reversible change and confidence at least 0.75; show action, target and predicted effect and require a human yes."
    else:
        tier, score = 2, 45
        rationale = "Confidence is sufficient for diagnosis but below quick-approval eligibility; show full evidence and require explicit typed yes."
    return {
        "business": business,
        "journeys_affected": journeys,
        "users_affected_estimate": "Not measured: telemetry counts spans and requests, not distinct users.",
        "blast_radius": blast_radius,
        "reversibility": reversibility,
        "data_risk": data_risk,
        "confidence": round(confidence, 6),
        "tier": tier,
        "score": score,
        "rationale": rationale,
    }
