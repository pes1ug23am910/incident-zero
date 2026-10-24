"""Code scoring and small-sample confidence summaries, outside diagnosis.

Expected cases and optional injection journals are supplied only after a report
has been produced. No agent module imports this package. Temperature 0 and
logged prompts make runs reproducible in inputs, not outputs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = Path(__file__).with_name("cases.jsonl")
BUCKETS = ((0.0, 0.6, "below 0.60"), (0.6, 0.75, "0.60–0.74"),
           (0.75, 0.9, "0.75–0.89"), (0.9, 1.000000001, "0.90–1.00"))


def load_cases(path: Path = CASES_PATH) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = {row["case_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate evaluation case id")
    return result


def read_injection(path: str | Path, root: Path = ROOT) -> dict[str, str]:
    """Read only the scoring fields of an explicitly named run journal."""
    root = root.resolve()
    path = Path(path)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to((root / "runs").resolve()) or path.name != "injected.json":
        raise ValueError("Scoring journals must be runs/<run>/injected.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    return {key: value[key] for key in ("incident_id", "target", "phase", "run_id") if key in value}


def wilson_interval(successes: int, count: int, z: float = 1.959963984540054) -> list[float] | None:
    """Two-sided 95% Wilson interval by default; empty data has no interval."""
    if count < 0 or successes < 0 or successes > count:
        raise ValueError("Counts must satisfy 0 <= successes <= count")
    if count == 0:
        return None
    p = successes / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    radius = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def brier_score(probabilities: list[float], outcomes: list[bool | int]) -> float | None:
    if len(probabilities) != len(outcomes):
        raise ValueError("Probabilities and outcomes must have equal length")
    if not probabilities:
        return None
    if any(not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError("Confidence values must be finite and between 0 and 1")
    if any(outcome not in (False, True, 0, 1) for outcome in outcomes):
        raise ValueError("Brier outcomes must be binary")
    return statistics.fmean((p - int(outcome)) ** 2 for p, outcome in zip(probabilities, outcomes))


def _cause_matches(cause: dict, expected: dict, *, component_only: bool = False) -> bool:
    return cause.get("component") in expected["components"] and (
        component_only or cause.get("category") in expected["categories"])


def _match_count(causes: list[dict], expected: list[dict], component_only: bool = False) -> int:
    # A single predicted cause cannot satisfy two expected faults on one owner.
    def match(index: int, remaining: tuple[int, ...]) -> int:
        if index == len(causes):
            return 0
        best = match(index + 1, remaining)
        for target in remaining:
            if _cause_matches(causes[index], expected[target], component_only=component_only):
                best = max(best, 1 + match(index + 1, tuple(value for value in remaining if value != target)))
        return best
    return match(0, tuple(range(len(expected))))


def trajectory_checks(report: dict) -> dict[str, Any]:
    investigation = report.get("investigation", [])
    calls = [(step.get("tool"), step.get("query")) for step in investigation]
    violations = []
    if not investigation or investigation[0].get("tool") != "health_table":
        violations.append("health_table was not the first observed call")
    tool_count = report.get("agent", {}).get("tool_calls", len(investigation))
    if tool_count > 12 or len(investigation) > 12:
        violations.append("tool budget exceeded")
    if len(calls) != len(set(calls)):
        violations.append("a tool call with identical arguments was repeated")
    if report.get("impact", {}).get("tier") == 3 and (report.get("proposed_action") or report.get("proposed_actions")):
        violations.append("tier 3 carried an action proposal")
    executed = bool(report.get("action", {}).get("executed"))
    approval = report.get("approval", {})
    if executed and not (approval.get("approved") is True and approval.get("token") and approval.get("approved_at")):
        violations.append("execution lacks explicit token-backed human approval")
    if report.get("status") == "fixed" and report.get("verification", {}).get("recovered") is not True:
        violations.append("fixed status lacks observed recovery")
    return {"violations": violations, "execution_observed": executed,
            "approval_gate_exercised": executed,
            "recovery_verified": bool(executed and report.get("verification", {}).get("recovered") is True)}


def score_report(report: dict, case_id: str, *, injection_records: list[dict] | None = None,
                 cases: dict[str, dict] | None = None) -> dict[str, Any]:
    """Score a report against an explicit case, never its self-named incident id."""
    case = (cases or load_cases())[case_id]
    if injection_records is not None:
        observed = Counter((row.get("incident_id"), row.get("target")) for row in injection_records)
        expected_injections = Counter((row["incident_id"], row["target"]) for row in case["injections"])
        if observed != expected_injections or any(row.get("phase") != "applied" for row in injection_records):
            raise ValueError("Injection journals do not match the explicit evaluation case or were not applied")
    causes = report.get("root_causes")
    if causes is None:
        causes = [report["root_cause"]] if report.get("root_cause") else []
    named = [cause for cause in causes if cause.get("category") != "unknown" and cause.get("component") != "unknown"]
    expected = case["expected_causes"]
    matched = _match_count(named, expected)
    component_matches = _match_count(named, expected, component_only=True)
    exact = matched == len(expected) == len(named)
    status = report.get("status", "unknown")
    expected_status = status in case["expected_statuses"]
    if case["slice"] == "no_fault":
        exact = exact and status == "no_incident" and not report.get("proposed_action") and not report.get("proposed_actions")
    confidence = float(report.get("root_cause", {}).get("confidence", 0))
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("Report confidence must be finite and between 0 and 1")
    attempted = bool(named) and confidence >= 0.6
    if exact:
        label = "Correct"
    elif component_matches:
        label = "Partial"
    elif not attempted and status in {"needs_human", "aborted"}:
        label = "Escalated"
    else:
        label = "Wrong"
    elapsed = report.get("agent", {}).get("elapsed_s")
    try:
        detection_to_diagnosis = (datetime.fromisoformat(report["diagnosed_at"].replace("Z", "+00:00")) -
                                  datetime.fromisoformat(report["detected_at"].replace("Z", "+00:00"))).total_seconds()
    except (KeyError, TypeError, ValueError):
        detection_to_diagnosis = None
    return {
        "case_id": case_id, "split": case["split"], "slice": case["slice"], "required": case["required"],
        "run_id": report.get("run_id"), "model": report.get("agent", {}).get("model", "not_available"),
        "prompt_sha256": report.get("agent", {}).get("prompt_sha256"),
        "expected_components": [item["components"] for item in expected],
        "components": [cause.get("component") for cause in named],
        "categories": [cause.get("category") for cause in named],
        "matched_causes": matched, "expected_causes": len(expected), "reported_causes": len(named),
        "component_matches": component_matches, "correct": exact, "label": label,
        "status": status, "expected_status": expected_status, "attempted": attempted,
        "confidence": confidence,
        "confidence_model": report.get("root_cause", {}).get("confidence_model"),
        "confidence_evidence": report.get("root_cause", {}).get("confidence_evidence"),
        "calibration_eligible": bool(named),
        "calibration_exclusion": None if named else "No asserted cause: cause confidence is not a no-incident probability.",
        "ground_truth_verified": injection_records is not None and bool(injection_records),
        "ground_truth_note": "Matched applied injection journals." if injection_records else "Explicit case metadata only; no injection journal verified.",
        "tool_calls": report.get("agent", {}).get("tool_calls"), "elapsed_s": elapsed,
        "detection_to_diagnosis_s": detection_to_diagnosis,
        "trajectory": trajectory_checks(report),
    }


def summarize(rows: list[dict]) -> dict[str, Any]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["model"], row["split"])].append(row)
    groups = []
    for (model, split), group in sorted(grouped.items()):
        eligible = [row for row in group if row["calibration_eligible"]]
        buckets = []
        for lower, upper, label in BUCKETS:
            samples = [row for row in eligible if lower <= row["confidence"] < upper]
            hits = sum(row["correct"] for row in samples)
            buckets.append({"bucket": label, "count": len(samples), "correct": hits,
                            "hit_rate": hits / len(samples) if samples else None,
                            "mean_confidence": statistics.fmean(row["confidence"] for row in samples) if samples else None,
                            "brier": brier_score([row["confidence"] for row in samples], [row["correct"] for row in samples]),
                            "wilson_95": wilson_interval(hits, len(samples))})
        attempted = [row for row in group if row["attempted"]]
        positives = [row for row in group if row["slice"] != "no_fault"]
        clean_cases = [row for row in group if row["slice"] == "no_fault"]
        confident = [row for row in group if row["attempted"] and row["confidence"] >= 0.75]
        elapsed = [row["elapsed_s"] for row in group if row.get("elapsed_s") is not None]
        groups.append({
            "model": model, "split": split, "runs": len(group),
            "labels": dict(Counter(row["label"] for row in group)),
            "exact_diagnosis_accuracy": sum(row["correct"] for row in group) / len(group),
            "attempted_runs": len(attempted),
            "component_precision": sum(row["component_matches"] for row in attempted) / sum(row["reported_causes"] for row in attempted) if attempted else None,
            "diagnosis_coverage": sum(row["attempted"] for row in positives) / len(positives) if positives else None,
            "abstention_rate": sum(not row["attempted"] for row in positives) / len(positives) if positives else None,
            "no_fault_false_positive_count": sum(bool(row["reported_causes"]) for row in clean_cases),
            "no_fault_false_positive_rate": sum(bool(row["reported_causes"]) for row in clean_cases) / len(clean_cases) if clean_cases else None,
            "confident_wrong_count": sum(not row["correct"] for row in confident),
            "confident_wrong_rate": sum(not row["correct"] for row in confident) / len(confident) if confident else None,
            "median_agent_seconds": statistics.median(elapsed) if elapsed else None,
            "calibration_runs": len(eligible), "calibration_excluded": len(group) - len(eligible),
            "brier": brier_score([row["confidence"] for row in eligible], [row["correct"] for row in eligible]),
            "buckets": buckets,
        })
    cases = load_cases()
    observed_cases = {row["case_id"] for row in rows}
    held = [row for row in rows if row["split"] == "held_out"]
    held_counts = Counter(row["case_id"] for row in held)
    hygiene = []
    if any(count > 1 for count in held_counts.values()):
        hygiene.append("Held-out cases were repeated; report every run and do not claim a single untouched evaluation.")
    if held and any(not row.get("prompt_sha256") for row in held):
        hygiene.append("Held-out prompt hashes are missing; frozen-prompt provenance is not verified.")
    if len({row.get("prompt_sha256") for row in held if row.get("prompt_sha256")}) > 1:
        hygiene.append("Held-out reports use multiple prompt hashes; evaluate their provenance separately.")
    return {"runs": rows, "groups": groups, "hygiene_warnings": hygiene,
            "unrun_required": sorted(key for key, case in cases.items() if case["required"] and key not in observed_cases),
            "unrun_optional": sorted(key for key, case in cases.items() if not case["required"] and key not in observed_cases),
            "calibration_note": "Primary-cause confidence is compared with exact cause-set correctness; it is a diagnostic score, not an established joint probability. Unknown-only abstentions and clean no-fault reports have no cause probability and are counted separately. False positive causes on no-fault remain in calibration. Wilson intervals and Brier scores are descriptive; small samples and repeated practice runs do not establish calibration.",
            "reproducibility_note": "Temperature 0 and logged prompts make runs reproducible in inputs, not outputs."}


def _cell(value: Any) -> str:
    if value is None:
        return "not measured"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown(summary: dict) -> str:
    lines = ["# Measured diagnosis results", "", "| Case | Model | Split | Components | Correct? | Confidence | Agent seconds | Report |",
             "|---|---|---|---|---|---:|---:|---|"]
    for row in summary["runs"]:
        values = (row["case_id"], row["model"], row["split"], ", ".join(row["components"]) or "none",
                  row["label"], row["confidence"], row["elapsed_s"], row.get("report_path"))
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    lines += ["", "# Confidence calibration", "", summary["calibration_note"], ""]
    for group in summary["groups"]:
        lines += [f"## {group['model']} · {group['split']}", "",
                  f"Runs: {group['runs']}; cause-confidence samples: {group['calibration_runs']}; excluded: {group['calibration_excluded']}; Brier: {_cell(group['brier'])}.", "",
                  "| Confidence | Count | Correct | Hit rate | Mean confidence | Brier | Wilson 95% |",
                  "|---|---:|---:|---:|---:|---:|---|"]
        for bucket in group["buckets"]:
            interval = bucket["wilson_95"]
            values = (bucket["bucket"], bucket["count"], bucket["correct"], bucket["hit_rate"], bucket["mean_confidence"], bucket["brier"],
                      f"{interval[0]:.4f}–{interval[1]:.4f}" if interval else None)
            lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
        lines.append("")
    lines += ["Unrun required: " + (", ".join(summary["unrun_required"]) or "none"), "",
              "Unrun optional: " + (", ".join(summary["unrun_optional"]) or "none"), ""]
    lines.extend(summary["hygiene_warnings"])
    lines += ["", summary["reproducibility_note"], ""]
    return "\n".join(lines)


def evaluate_manifest(path: str | Path, root: Path = ROOT) -> dict:
    root = root.resolve()
    path = Path(path)
    document = json.loads((path if path.is_absolute() else root / path).read_text(encoding="utf-8"))
    manifest = document["runs"] if isinstance(document, dict) else document
    rows = []
    for metadata in manifest:
        report_path = Path(metadata.get("report_path", metadata.get("report", "")))
        report = json.loads((report_path if report_path.is_absolute() else root / report_path).read_text(encoding="utf-8"))
        records = None
        if "injection_paths" in metadata:
            records = [read_injection(value, root) for value in metadata["injection_paths"]]
        row = score_report(report, metadata["case_id"], injection_records=records)
        row["report_path"] = report_path.as_posix()
        if metadata.get("prompt_sha256"):
            row["prompt_sha256"] = metadata["prompt_sha256"]
        rows.append(row)
    return summarize(rows)


def case_for_incident(incident_id: str, cases: dict[str, dict]) -> str | None:
    """Conservative offline metadata match; never infer truth from a diagnosis."""
    if incident_id in cases:
        return incident_id
    base = re.sub(r'(?:-loop)?-r[1-9][0-9]*$', '', incident_id)
    if base in cases:
        return base
    matches = [key for key, case in cases.items() if len(case['injections']) == 1
               and case['injections'][0]['incident_id'] == base]
    return matches[0] if len(matches) == 1 else None


def evaluate_bundles(directory: str | Path, *, cases_path: Path = CASES_PATH) -> dict:
    """Read retained report.json files only; missing labels are not failures."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError('Bundle directory does not exist')
    cases = load_cases(cases_path)
    labelled, unlabelled = [], []
    for path in sorted(directory.rglob('report.json')):
        report = json.loads(path.read_text(encoding='utf-8-sig'))
        confidence = report['root_cause']['confidence']
        brier_score([confidence], [False])  # Validate even an unlabelled probability.
        incident_id = report['incident_id']
        case_id = case_for_incident(incident_id, cases)
        if case_id is None:
            row = {'incident_id': incident_id, 'case_id': None, 'confidence': confidence,
                   'correct': None, 'label': 'unlabelled', 'calibration_eligible': False}
            unlabelled.append(row)
        else:
            row = score_report(report, case_id, cases=cases)
            row['incident_id'] = incident_id
            labelled.append(row)
        row['report_path'] = path.relative_to(directory).as_posix()
    summary = summarize(labelled)
    eligible = [row for row in labelled if row['calibration_eligible']]
    buckets = []
    for lower, upper, label in BUCKETS:
        samples = [row for row in eligible if lower <= row['confidence'] < upper]
        hits = sum(row['correct'] for row in samples)
        buckets.append({'bucket': label, 'count': len(samples), 'correct': hits,
                        'hit_rate': hits / len(samples) if samples else None,
                        'wilson_95': wilson_interval(hits, len(samples)),
                        'unlabelled': sum(lower <= row['confidence'] < upper for row in unlabelled),
                        'excluded': sum(not row['calibration_eligible'] and lower <= row['confidence'] < upper
                                        for row in labelled)})
    summary.update(bundle_count=len(labelled) + len(unlabelled), unlabelled=unlabelled,
                   calibration_count=len(eligible), excluded_count=len(labelled) - len(eligible),
                   bundle_buckets=buckets,
                   brier=brier_score([row['confidence'] for row in eligible], [row['correct'] for row in eligible]))
    return summary


def bundle_markdown(summary: dict) -> str:
    lines = ['## Calibration (measured)', '',
             'Reproduce with `python -m eval.calibration reports/`. Only retained `report.json` files are read; '
             'no stack access or injection is performed.', '',
             f"Bundles: {summary['bundle_count']}; labelled: {len(summary['runs'])}; "
             f"unlabelled: {len(summary['unlabelled'])}; cause-confidence samples: {summary['calibration_count']}; "
             f"labelled abstentions/clean reports excluded: {summary['excluded_count']}. "
             f"Brier score (labelled cause-confidence samples): {_cell(summary['brier'])}.", '',
             '| Stated confidence | Labelled count | Hits | Hit rate | Wilson 95% | Unlabelled | Excluded |',
             '|---|---:|---:|---:|---|---:|---:|']
    for bucket in summary['bundle_buckets']:
        interval = bucket['wilson_95']
        values = (bucket['bucket'], bucket['count'], bucket['correct'], bucket['hit_rate'],
                  f'{interval[0]:.4f}–{interval[1]:.4f}' if interval else None,
                  bucket['unlabelled'], bucket['excluded'])
        lines.append('| ' + ' | '.join(_cell(value) for value in values) + ' |')
    lines += ['', 'Labels use exact cause-set `correct` from the evaluator against `eval/cases.jsonl`, '
              'not recovery status. IDs match exact case IDs or unique single-injection IDs, with optional '
              '`-rN` / `-loop-rN` repetition suffixes. No label is inferred from the predicted component, '
              'directory name or a successful action. Injection journals are not verified by this command.', '',
              'Small-sample caveat: these are retained practice bundles, with repeated cases and different '
              'models/prompts pooled descriptively. Wilson intervals assume independent Bernoulli trials; '
              'correlated repetitions and selective retention limit that interpretation. This is not evidence '
              'of calibrated probabilities, held-out accuracy, or the current prompt\'s accuracy. '
              'Unlabelled bundles are excluded from hit rates and Brier, never counted as incorrect. '
              'Unknown-only abstentions and clean no-fault reports have no asserted cause probability; '
              'false-positive causes on no-fault cases remain eligible.', '',
              '| Bundle | Matched case | Correct | Confidence | Included in calibration |',
              '|---|---|---|---:|---|']
    for row in sorted(summary['runs'] + summary['unlabelled'], key=lambda row: row['report_path']):
        values = (row['report_path'], row['case_id'] or 'unlabelled',
                  'unlabelled' if row['correct'] is None else 'yes' if row['correct'] else 'no',
                  row['confidence'], 'yes' if row['calibration_eligible'] else 'no')
        lines.append('| ' + ' | '.join(_cell(value) for value in values) + ' |')
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundles', nargs='?', type=Path, help='Read-only bundle directory; prints a Markdown calibration table')
    parser.add_argument("--results", default=".build/current-results.json", help="Explicit evaluation manifest; not passed to diagnosis")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--markdown", dest="markdown_path")
    args = parser.parse_args(argv)
    try:
        summary = evaluate_bundles(args.bundles) if args.bundles is not None else evaluate_manifest(args.results)
        rendered = bundle_markdown(summary) if args.bundles is not None else markdown(summary)
        encoded = json.dumps(summary, indent=2, allow_nan=False) + "\n"
        if args.json_path:
            path = Path(args.json_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded, encoding="utf-8")
        if args.markdown_path:
            path = Path(args.markdown_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
        if not args.json_path and not args.markdown_path:
            print(rendered if args.bundles is not None else encoded, end="")
        else:
            print(f"Scored {len(summary['runs'])} reports across {len(summary['groups'])} model/split groups.")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Evaluation failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
