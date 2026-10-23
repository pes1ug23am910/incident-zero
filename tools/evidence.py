"""Persist sanitized observations under a confined run's evidence directory."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
from uuid import uuid4

from .redact import sanitize, is_sensitive

ROOT = Path(__file__).resolve().parents[1]
CURRENT_RUN = contextvars.ContextVar("evidence_run", default=None)
_PATTERNS = {
    "trace": (r"trace:[a-fA-F0-9]{16,32}", "jaeger"),
    "span": (r"span:[a-fA-F0-9]{16,32}/[a-fA-F0-9]{16}", "jaeger"),
    "log": (r"log:[a-zA-Z0-9_-]+/[^\s/]+", "opensearch"),
    "dlog": (r"dlog:[a-zA-Z0-9_.-]+:[a-f0-9]{64}", "docker"),
    "metric": (r"metric:[a-zA-Z_:][a-zA-Z0-9_:]*\{.*\}@[-+\d.eE]+=[-+\d.eE]+", "prometheus"),
    "container": (r"container:[a-zA-Z0-9_.-]+:(?:Status|RestartCount|OOMKilled|StartedAt|Created|NanoCpus|Memory|health)=.+", "docker"),
    "action_log": (r"action_log:[1-9][0-9]*", "action_log"),
}


def expected_source(identifier):
    """Reject unsupported or revealing identifiers before any disk lookup."""
    from .redact import is_sensitive_evidence

    if not isinstance(identifier, str) or len(identifier) > 16384:
        raise ValueError("Evidence identifier must be a string of at most 16384 characters")
    if is_sensitive_evidence(identifier):
        raise ValueError("Evidence identifier is excluded from diagnostic reads")
    pattern, source = _PATTERNS.get(identifier.split(":", 1)[0], ("", None))
    if source is None or not re.fullmatch(pattern, identifier):
        raise ValueError("Malformed or unsupported evidence identifier")
    return source


def run_path(run_dir=None, *, create=False):
    """Accept a bare run name or a path strictly inside the repository's runs."""
    root = ROOT.resolve()
    runs = root / "runs"
    if runs.resolve() != runs:
        raise ValueError("The runs directory must not be a symbolic link")
    if run_dir is None:
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex[:8]
        candidate = runs / name
    else:
        given = Path(run_dir)
        if ".." in given.parts:
            raise ValueError("Run directory traversal is not allowed")
        if given.is_absolute():
            candidate = given
        elif len(given.parts) == 1:
            candidate = runs / given
        elif given.parts and given.parts[0] == "runs":
            candidate = root / given
        else:
            raise ValueError("Run directory must be a run name or a path under runs")
    resolved = candidate.resolve()
    if resolved == runs or not resolved.is_relative_to(runs):
        raise ValueError("Run directory must stay inside repository runs")
    if len(resolved.relative_to(runs).parts) != 1:
        raise ValueError("Run directory must identify one immediate child of runs")
    if candidate.absolute() != resolved:
        raise ValueError("Run directory must not resolve through a symbolic link")
    evidence_dir = resolved / "evidence"
    if evidence_dir.resolve() != evidence_dir:
        raise ValueError("Evidence directory must not be a symbolic link")
    if create:
        evidence_dir.mkdir(parents=True, exist_ok=True)
    return resolved


def snapshot_path(run_dir, identifier):
    expected_source(identifier)
    path = run_path(run_dir) / "evidence" / (hashlib.sha256(identifier.encode("utf-8")).hexdigest() + ".json")
    if path.resolve() != path:
        raise ValueError("Evidence file must not be a symbolic link")
    return path


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _clean_payload(identifier, source, data):
    if source != expected_source(identifier):
        raise ValueError("Evidence source does not match its identifier")
    if identifier.startswith(("log:", "dlog:", "action_log:")) and is_sensitive(data):
        raise ValueError("Log evidence is excluded from diagnostic reads")
    if identifier.startswith("dlog:") and isinstance(data, dict) and "original_line" in data:
        line = data["original_line"]
        if not isinstance(line, str) or hashlib.sha256(line.encode("utf-8")).hexdigest() != identifier.rsplit(":", 1)[1]:
            raise ValueError("Docker log evidence digest does not match its recorded line")
    cleaned = sanitize(data)
    if cleaned is None:
        raise ValueError("No safe evidence payload remains")
    return cleaned


@dataclass
class EvidenceRun:
    path: Path
    captured: dict = field(default_factory=dict)
    # Shared by nested tools in one call only; a later call revalidates disk.
    persisted_paths: dict = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)


def begin_run(run_dir=None):
    current = CURRENT_RUN.get()
    if run_dir is None and current is not None:
        return current, None
    path = run_path(run_dir, create=True)
    if current is not None and current.path == path:
        return current, None
    current = EvidenceRun(path)
    return current, CURRENT_RUN.set(current)


def end_run(token):
    if token is not None:
        CURRENT_RUN.reset(token)


def capture_evidence(identifier, source, data):
    """Retain the original observed payload while a bounded tool is running."""
    current = CURRENT_RUN.get()
    if current is None:
        return
    payload = {"id": identifier, "source": source, "data": _clean_payload(identifier, source, data)}
    with current.lock:
        current.captured.setdefault(identifier, payload)


def _from_envelope(identifier, result):
    """Recover observed tool payloads when a producer did not capture raw data."""
    source = expected_source(identifier)
    rows = result.get("data", [])
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("evidence_id") == identifier:
                data = row.get("record", row)
                if identifier.startswith("container:"):
                    _, name, expression = identifier.split(":", 2)
                    key = expression.split("=", 1)[0]
                    data = {"name": name, "field": key, "value": row.get("timestamp")}
                return {"id": identifier, "source": source, "data": data}
            if identifier.startswith("container:"):
                _, name, expression = identifier.split(":", 2)
                key = expression.split("=", 1)[0]
                if row.get("name") == name and key in row:
                    return {"id": identifier, "source": source, "data": {"name": name, "field": key, "value": row[key]}}
            if identifier in (row.get("peak_evidence_id"), row.get("latest_evidence_id")):
                from .resolve import parse_metric
                _, _, stamp, expected, query = parse_metric(identifier)
                if any(float(point[0]) == stamp and point[1] == expected for point in row.get("values", [])):
                    return {"id": identifier, "source": source, "data": {"metric": row["metric"], "timestamp": stamp, "value": expected, "query": query}}
    # The envelope is itself the observation, never a payload synthesized from an ID.
    return {"id": identifier, "source": source, "data": {key: result[key] for key in ("tool", "query", "window", "data")}}


def persist_envelope(result, current):
    paths = {}
    root = ROOT.resolve()
    with current.lock:
        for identifier in result.get("evidence_ids", []):
            if identifier in current.persisted_paths:
                paths[identifier] = current.persisted_paths[identifier]
                continue
            payload = current.captured.get(identifier) or _from_envelope(identifier, result)
            payload = {**payload, "data": _clean_payload(identifier, payload["source"], payload["data"])}
            snapshot = {"version": 1, **payload, "captured_at": datetime.now(timezone.utc).isoformat()}
            snapshot["checksum"] = hashlib.sha256(_canonical(snapshot)).hexdigest()
            path = snapshot_path(current.path, identifier)
            try:
                with path.open("x", encoding="utf-8") as output:
                    json.dump(snapshot, output, ensure_ascii=False, allow_nan=False, indent=2)
                    output.write("\n")
            except FileExistsError:
                # Snapshots are immutable; validate existing bytes, never overwrite them.
                load_snapshot(path, identifier)
            relative = path.relative_to(root).as_posix()
            current.persisted_paths[identifier] = relative
            paths[identifier] = relative
    result["run_dir"] = current.path.relative_to(root).as_posix()
    result["evidence_paths"] = paths
    return result


def load_snapshot(path, identifier):
    source = expected_source(identifier)
    path = Path(path)
    if snapshot_path(path.parent.parent, identifier) != path or not path.is_file():
        raise ValueError("Snapshot path does not match the requested evidence")
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Snapshot exceeds the evidence size bound")
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or set(record) != {"version", "id", "source", "data", "captured_at", "checksum"}:
        raise ValueError("Malformed evidence snapshot")
    checksum = record.pop("checksum")
    if checksum != hashlib.sha256(_canonical(record)).hexdigest():
        raise ValueError("Evidence snapshot checksum mismatch")
    if record["version"] != 1 or record["id"] != identifier or record["source"] != source:
        raise ValueError("Evidence snapshot identity or source mismatch")
    return {"id": identifier, "source": source,
            "data": _clean_payload(identifier, source, record["data"]),
            "captured_at": record["captured_at"], "resolved_from": "snapshot",
            "snapshot_path": path.relative_to(ROOT.resolve()).as_posix()}


def find_snapshot(identifier, run_dir=None):
    expected_source(identifier)
    if run_dir is not None:
        candidates = [snapshot_path(run_path(run_dir), identifier)]
    else:
        runs = ROOT.resolve() / "runs"
        if runs.resolve() != runs:
            raise ValueError("The runs directory must not be a symbolic link")
        # Only exact evidence filenames are visited; no operator state is opened.
        filename = hashlib.sha256(identifier.encode("utf-8")).hexdigest() + ".json"
        candidates = sorted(runs.glob("*/evidence/" + filename), reverse=True)
    failures = []
    for path in candidates:
        try:
            return load_snapshot(path, identifier)
        except (OSError, ValueError) as exc:
            failures.append(str(exc))
    raise ValueError("No valid recorded evidence snapshot" + (": " + failures[0] if failures else ""))
