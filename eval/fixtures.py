"""Export immutable graph inputs for replay after a completed diagnosis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.evidence import load_snapshot, run_path, snapshot_path


def _write_immutable(path: Path, raw: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as output:
            output.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError("Fixture already contains different data; use a new fixture directory")


def save_tool_fixture(report_path: str | Path, fixture_dir: str | Path, *, origin: str = "recorded") -> dict:
    """Copy only recorded runtime observations; never read scoring state.

    Set origin="live" only when the caller actually ran against the live demo.
    A separate expected report is for test assertions; replay never reads it.
    """
    if origin not in {"live", "synthetic", "recorded"}:
        raise ValueError("Fixture origin must be live, synthetic or recorded")
    report_path, fixture_dir = Path(report_path).resolve(), Path(fixture_dir).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    run_dir = run_path(report["run_id"])
    tools_path = run_dir / "tools.jsonl"
    model_path = run_dir / "llm.jsonl"
    if not tools_path.is_file() or not model_path.is_file():
        raise ValueError("Completed run must have both tool and model audit logs for graph replay")
    calls = [json.loads(line) for line in tools_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = sorted({identifier for call in calls for identifier in call["result"].get("evidence_ids", [])})
    evidence = []
    for identifier in ids:
        path = snapshot_path(run_dir, identifier)
        load_snapshot(path, identifier)
        evidence.append((path.name, path.read_bytes()))
    # Keep the complete detector alert when available: bundle alerts omit the
    # anomaly list, which can affect coverage and must not change during replay.
    alert_path = run_dir / "alert.json"
    if not alert_path.is_file():
        alert_path = report_path.parent / "alert.json"
    if not alert_path.is_file():
        raise ValueError("Replay requires the detector alert retained with the run or report")
    files = {"tools.jsonl": tools_path.read_bytes(), "llm.jsonl": model_path.read_bytes(),
             "alert.json": alert_path.read_bytes(), "expected_report.json": report_path.read_bytes()}
    for name, raw in evidence:
        files["evidence/" + name] = raw
    manifest = {"version": 1, "origin": origin, "source_run_id": report["run_id"],
                "source_incident_id": report["incident_id"], "source_model": report["agent"]["model"],
                "prompt_sha256": report["agent"].get("prompt_sha256"),
                "tool_calls": len(calls), "evidence_count": len(ids),
                "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())}}
    for name, raw in files.items():
        _write_immutable(fixture_dir / name, raw)
    _write_immutable(fixture_dir / "fixture.json", (json.dumps(manifest, indent=2) + "\n").encode())
    return manifest
