"""Serializable typed control state persisted at each graph boundary."""
from typing import Annotated, TypedDict
import operator


def merge_evidence(left, right):
    return {**(left or {}), **(right or {})}


class IncidentState(TypedDict, total=False):
    run_id: str
    incident_id: str
    alert: dict
    findings: Annotated[list[dict], operator.add]
    evidence: Annotated[dict, merge_evidence]
    audit: Annotated[list[dict], operator.add]
    hypotheses: list[dict]
    tool_calls_used: int
    last_call: str
    seen_calls: list[str]
    stop_signal: bool
    stopped_because: str
    validation_error: str
    health: dict
    unexplained: list[str]
    symptom_services: list[str]
    finish_blocked: bool
    confidence_reassessment: bool
    decision_repair_used: bool
    done: bool
    clean: bool
    report: dict
    impact: dict
    proposal: list[dict]
    dry_run: dict
    decision: dict
    verification: dict
    status: str
    knowledge_context: dict
    report_path: str
