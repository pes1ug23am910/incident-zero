"""Persist redacted summaries of schema-validated reports, without live reads."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import tempfile

from agent.llm_router import scrub
from schema.validate import validate_report
from tools.redact import sanitize

ROOT = Path(__file__).resolve().parents[1]
_ERROR_KEYS = {"body", "msg", "message", "error", "status_message", "exception.message"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _normalize(value):
    text = str(value).casefold()
    text = re.sub(r"\b[0-9a-f]{16,}\b", "<id>", text)
    text = re.sub(r"\b\d{4}-\d\d-\d\d[t ][\d:.+z-]+", "<time>", text)
    text = re.sub(r"(?<![a-z])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", "<number>", text)
    return " ".join(text.split())[:500]


def _error_text(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _ERROR_KEYS and isinstance(child, str) and child.strip():
                yield child
            elif isinstance(child, (dict, list)):
                yield from _error_text(child)
    elif isinstance(value, list):
        for child in value:
            yield from _error_text(child)


def _observed_errors(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            # Bundles truncate long JSON summaries. Only extract complete,
            # explicitly named message values; never use the surrounding prose.
            for match in re.finditer(r'"([^"\\]+)"\s*:\s*("(?:[^"\\]|\\.)*")', value):
                if match[1] in _ERROR_KEYS:
                    try:
                        yield json.loads(match[2])
                    except ValueError:
                        continue
            return
    yield from _error_text(value)


def fingerprint(observation, *, secrets=()):
    """Stable symptom query, excluding diagnoses, proposals and retrieval hints.

    Accept a report, observation state, detector alert, or health-table envelope.
    Error messages are selected from observed tool results, never model rationale.
    """
    data = sanitize(scrub(deepcopy(observation), secrets)) or {}
    symptoms = list(data.get("symptoms", [])) + list(data.get("anomalies", []))
    alert = data.get("alert", {})
    if data.get("service") and data.get("signal"):
        symptoms.append(data)
    if alert.get("service") and alert.get("signal"):
        symptoms.append(alert)
    symptoms.extend(alert.get("anomalies", []))
    health = data.get("health", data if data.get("tool") == "health_table" else None)
    if health is not None:
        from detect.core import anomalies

        symptoms.extend(anomalies(health))
    parts = set()
    for symptom in symptoms:
        if not isinstance(symptom, dict):
            continue
        parts.add(" ".join(_normalize(symptom.get(key, "")) for key in ("service", "signal", "observed")).strip())
    for service in data.get("symptom_services", []):
        parts.add(_normalize(service))
    for finding in data.get("findings", []) + data.get("investigation", []):
        observed = finding.get("result", finding.get("finding", {}))
        parts.update(_normalize(text) for text in _observed_errors(observed))
    evidence = data.get("evidence", [])
    entries = evidence.values() if isinstance(evidence, dict) else evidence
    for entry in entries:
        parts.update(_normalize(text) for text in _observed_errors(entry.get("data", entry.get("summary", {}))))
    return " | ".join(sorted(part for part in parts if part))[:4096]


def _recorded_resolver(report, report_path):
    from tools.evidence import find_bundle_snapshot, find_snapshot

    if report_path is not None:
        bundle = Path(report_path).parent
        return lambda identifier: find_bundle_snapshot(identifier, bundle)
    return lambda identifier: find_snapshot(identifier, run_dir=report["run_id"])


def _actual_actions(report):
    proposals = report.get("proposed_actions", [report.get("proposed_action")])
    result = []
    for item in report.get("action_history", []):
        execution = item.get("execution", {})
        if execution.get("executed") is not True:
            continue
        index = item.get("index")
        proposal = proposals[index] if isinstance(index, int) and 0 <= index < len(proposals) else None
        result.append({
            "type": (proposal or {}).get("type"), "target": (proposal or {}).get("target"),
            "parameters": (proposal or {}).get("parameters", {}),
            "started_at": execution.get("started_at"), "finished_at": execution.get("finished_at"),
            "action_log_ref": execution.get("action_log_ref"),
            "verification": item.get("verification", {}),
        })
    if not result and report["action"]["executed"]:
        proposal = report.get("proposed_action") or {}
        result.append({
            "type": proposal.get("type"), "target": proposal.get("target"),
            "parameters": proposal.get("parameters", {}),
            **{key: report["action"].get(key) for key in ("started_at", "finished_at", "action_log_ref")},
            "verification": report["verification"],
        })
    return result


def _outcome(report):
    status, verification = report["status"], report["verification"]
    if verification["rolled_back"] or status == "rolled_back":
        return "rolled_back"
    if status == "fixed" and verification["recovered"] is True:
        return "recovered"
    if status in {"no_incident", "aborted"}:
        return status
    if status == "needs_human":
        return "escalated"
    # Only fixed reports pass the validator's measured-recovery invariants.
    claimed = verification.get("outcome", "unknown")
    return "unknown" if claimed == "recovered" else claimed


def _recovery_seconds(report):
    if report["status"] != "fixed" or report["verification"]["recovered"] is not True or not report["resolved_at"]:
        return None
    start = datetime.fromisoformat(report["detected_at"].replace("Z", "+00:00").replace("z", "+00:00"))
    end = datetime.fromisoformat(report["resolved_at"].replace("Z", "+00:00").replace("z", "+00:00"))
    return round((end - start).total_seconds(), 3)


class MemoryStore:
    """One JSON per incident; repeated writes update its observed outcome.

    Validation resolves only selected retained evidence unless the caller supplies
    an explicit resolver. A report_path only locates retained evidence.
    """

    def __init__(self, root=None, index=None, *, resolver=None, secrets=()):
        self.root = Path(root) if root is not None else ROOT / "memory" / "store"
        self.index = index
        self.resolver = resolver
        self.secrets = tuple(secrets)

    def _index(self):
        if self.index is None:
            from knowledge import KnowledgeIndex

            self.index = KnowledgeIndex()
        return self.index

    def remember(self, report, *, report_path=None, resolver=None):
        """Validate before writing, redact before storage, and index immediately."""
        source = deepcopy(report)
        errors = validate_report(source, resolver=resolver or self.resolver or _recorded_resolver(source, report_path))
        if errors:
            # Validation messages may contain rejected input, so never echo it.
            raise ValueError(f"Memory requires a validated report ({len(errors)} validation errors)")
        safe = sanitize(scrub(source, self.secrets))
        # Stable across response updates, without retaining operator labels or paths.
        identifier = hashlib.sha256(_canonical([safe["run_id"], safe["incident_id"]]).encode("utf-8")).hexdigest()
        symptom_query = fingerprint(safe, secrets=self.secrets)
        cause, verification = safe["root_cause"], safe["verification"]
        record = {
            "schema_version": "1.0", "memory_id": identifier, "citation_id": "mem:" + identifier,
            "symptom_fingerprint": symptom_query,
            "fingerprint_sha256": hashlib.sha256(symptom_query.encode("utf-8")).hexdigest(),
            "services": sorted({item["service"] for item in safe["symptoms"]}),
            "anomalies": [{key: item[key] for key in ("service", "signal", "observed")} for item in safe["symptoms"]],
            "category": cause["category"], "component": cause["component"],
            "confidence": cause["confidence"], "cause": cause["cause"],
            "action_taken": _actual_actions(safe), "verification": verification,
            "verification_outcome": verification.get("outcome", "unknown"), "outcome": _outcome(safe),
            "report_status": safe["status"], "seconds_to_recovery": _recovery_seconds(safe),
            "recovery_time_basis": "detected_at_to_resolved_at",
            "detected_at": safe["detected_at"], "diagnosed_at": safe["diagnosed_at"], "resolved_at": safe["resolved_at"],
            "prompt_sha256": safe["agent"].get("prompt_sha256"),
            "report_sha256": hashlib.sha256(_canonical(safe).encode("utf-8")).hexdigest(),
            "escalation_note": safe.get("escalation_note"),
            "hint_only": True,
        }
        record = sanitize(scrub(record, self.secrets))
        self.root.mkdir(parents=True, exist_ok=True)
        root = self.root.resolve()
        path = root / (identifier + ".json")
        if path.resolve() != path:
            raise ValueError("Memory record path must not resolve through a symbolic link")
        # Write complete JSON before replacing the old record; a failed index can
        # be repaired by rerunning remember or knowledge build from these files.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=root, prefix=".memory-", suffix=".tmp", encoding="utf-8", delete=False) as output:
                temporary = Path(output.name)
                output.write(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
            temporary.replace(path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
        self._index().upsert_memory(record, file=str(path))
        return record

    def similar(self, observation, *, limit=3):
        """Return scored prior-incident hints using the same retrieval index."""
        query = observation if isinstance(observation, str) else fingerprint(observation, secrets=self.secrets)
        query = sanitize(scrub(query, self.secrets)) or ""
        return self._index().search(query, runbook_k=0, memory_k=limit, service_k=0)["memory_refs"]
