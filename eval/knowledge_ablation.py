"""Offline retrieval-only comparison on validated retained incident reports.

Decisions and recorded timings are frozen: this is not a new model run and does
not measure diagnosis improvement. No telemetry, action or model API is called.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time

from knowledge import KnowledgeIndex
from memory import fingerprint
from schema.validate import validate_report
from tools.evidence import find_bundle_snapshot

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLES = ("payment-failure-r6", "container-stopped-r3", "cache-unavailable-r2")


@contextmanager
def isolated_index(source_root):
    """Copy only generic reference documents, never evaluation incident memories."""
    source_root = Path(source_root).resolve()
    with tempfile.TemporaryDirectory(prefix="incident-zero-ablation-") as directory:
        root = Path(directory)
        shutil.copytree(source_root / "knowledge/runbooks", root / "knowledge/runbooks")
        shutil.copyfile(source_root / "knowledge/services.yaml", root / "knowledge/services.yaml")
        index = KnowledgeIndex(root=root)
        yield index, index.build()


def load_recorded_report(bundle):
    bundle = Path(bundle).resolve()
    path = bundle / "report.json"
    raw = path.read_bytes()
    report = json.loads(raw)
    errors = validate_report(report, resolver=lambda identifier: find_bundle_snapshot(identifier, bundle))
    if errors:
        raise ValueError(f"{bundle.name}: report or retained evidence failed validation ({len(errors)} errors)")
    return report, hashlib.sha256(raw).hexdigest()


def compare_report(report, index):
    """Measure retrieval on recorded symptoms and then the frozen diagnosed labels."""
    cause = report["root_cause"]
    causes = report.get("root_causes", [cause])
    metrics = {
        "component": cause["component"], "category": cause["category"],
        "confidence": cause["confidence"], "tool_calls": report["agent"]["tool_calls"],
        "seconds": report["agent"]["elapsed_s"], "status": report["status"],
    }
    off = {"enabled": False, "recorded_metrics": dict(metrics), "retrieval_ms": 0.0, "stages": []}
    queries = (
        ("recorded_symptoms", fingerprint({"alert": report["alert"], "symptoms": report["symptoms"]}), "investigation"),
        ("recorded_diagnosis", " ".join(f"{item['component']} {item['category']}" for item in causes), "remediation"),
    )
    stages = []
    started = time.perf_counter()
    for name, query, section in queries:
        tick = time.perf_counter()
        retrieved = index.search(query, section=section)
        stages.append({"stage": name, "query": query, "section": section,
                       "retrieval_ms": round((time.perf_counter() - tick) * 1000, 3), **retrieved})
    on = {"enabled": True, "recorded_metrics": dict(metrics),
          "retrieval_ms": round((time.perf_counter() - started) * 1000, 3), "stages": stages}
    return {"incident_id": report["incident_id"], "decisions_frozen": True,
            "off": off, "on": on, "improvement_measured": False}


def compare(*, reports_dir=None, bundles=DEFAULT_BUNDLES, source_root=ROOT):
    reports_dir = Path(reports_dir or ROOT / "reports").resolve()
    recorded = []
    for name in bundles:
        bundle = (reports_dir / name).resolve()
        if bundle.parent != reports_dir:
            raise ValueError("Bundle names must identify direct children of the reports directory")
        report, digest = load_recorded_report(bundle)
        recorded.append((report, digest, name))
    with isolated_index(source_root) as (index, stats):
        rows = []
        for report, digest, name in recorded:
            row = compare_report(report, index)
            row.update(bundle=name, report_sha256=digest)
            rows.append(row)
    return {
        "version": 1, "evaluation": "offline_retrieval_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decisions_frozen": True, "improvement_measured": False,
        "memory_policy": "isolated empty memory; evaluation reports are never indexed",
        "metrics_basis": "component/confidence/tool_calls/seconds are copied from the recorded report",
        "limitations": [
            "No fresh investigator or planner decision was made; equal on/off metrics are expected by construction.",
            "Recorded symptom queries use the report's observed symptoms, not a reconstructed initial health-table envelope.",
            "Only retrieval time is measured now; recorded elapsed seconds are not replay runtime or recovery time.",
            "A live on/off comparison is required to measure changes in diagnosis, tool calls, or elapsed time.",
        ],
        "index": stats, "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".build/knowledge-ablation.json")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    parser.add_argument("--bundles", nargs="+", default=DEFAULT_BUNDLES)
    args = parser.parse_args(argv)
    try:
        result = compare(reports_dir=args.reports_dir, bundles=args.bundles)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Offline comparison failed: {exc}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "evaluation": result["evaluation"],
                      "incidents": len(result["rows"]), "improvement_measured": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
