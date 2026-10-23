import ast
import json
from pathlib import Path

import pytest

from eval.calibration import brier_score, evaluate_manifest, load_cases, markdown, read_injection, score_report, summarize, wilson_interval


def make_report(component="payment", category="application_flag", confidence=0.8, status="diagnosed"):
    cause = {"component": component, "category": category, "confidence": confidence}
    return {"incident_id": "ignored-attacker-chosen-id", "run_id": "runs/test", "root_cause": cause,
            "root_causes": [cause], "status": status, "proposed_action": None, "proposed_actions": [],
            "agent": {"model": "primary", "tool_calls": 1, "elapsed_s": 4.5},
            "investigation": [{"tool": "health_table", "query": "{}"}],
            "impact": {"tier": 3 if status == "needs_human" else 2},
            "action": {"executed": False}}


def test_wilson_and_brier_known_values():
    low, high = wilson_interval(7, 8)
    assert low == pytest.approx(0.5291, abs=0.0001)
    assert high == pytest.approx(0.9776, abs=0.0001)
    assert brier_score([0.8, 0.2], [True, False]) == pytest.approx(0.04)
    assert wilson_interval(0, 0) is None
    assert brier_score([], []) is None
    assert wilson_interval(0, 4)[0] == pytest.approx(0)
    assert wilson_interval(4, 4)[1] == pytest.approx(1)
    with pytest.raises(ValueError):
        brier_score([float("nan")], [True])
    with pytest.raises(ValueError):
        wilson_interval(2, 1)


def test_case_splits_and_required_combinations_are_frozen():
    cases = load_cases()
    assert sum(case["split"] == "tuning" for case in cases.values()) == 10
    assert sum(case["slice"] == "combination" for case in cases.values()) == 6
    assert sum(case["slice"] == "combination" and case["required"] for case in cases.values()) == 2
    assert cases["no-fault"]["split"] == "held_out"


def test_diagnostic_packages_never_import_evaluation_answers():
    root = Path(__file__).resolve().parents[1]
    for package in ("agent", "tools", "detect"):
        for path in (root / package).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert all(alias.name.split(".")[0] != "eval" for alias in node.names), str(path)
                elif isinstance(node, ast.ImportFrom):
                    assert (node.module or "").split(".")[0] != "eval", str(path)


def test_explicit_case_scores_report_regardless_of_report_incident_id():
    data = make_report()
    assert score_report(data, "payment-failure")["correct"]
    assert not score_report(data, "cart-intermittent")["correct"]


def test_combination_needs_both_causes_and_rejects_spurious_causes():
    data = make_report(status="needs_human")
    first = score_report(data, "combo-payment-recommendation")
    assert first["matched_causes"] == 1 and first["correct"] is False
    data["root_causes"].append({"component": "recommendation", "category": "container_down", "confidence": 0.9})
    assert score_report(data, "combo-payment-recommendation")["correct"]
    data["root_causes"].append({"component": "cart", "category": "application_flag", "confidence": 0.8})
    assert not score_report(data, "combo-payment-recommendation")["correct"]


def test_cache_and_cart_combination_cannot_be_masked_by_dependency():
    data = make_report("valkey-cart", "container_down", status="needs_human")
    assert not score_report(data, "combo-cache-cart")["correct"]
    data["root_causes"].append({"component": "cart", "category": "application_flag", "confidence": 0.8})
    assert score_report(data, "combo-cache-cart")["correct"]


def test_cpu_diagnosis_with_action_escalation_is_correct_not_abstention():
    row = score_report(make_report("recommendation", "resource_starvation", status="needs_human"), "cpu-starve-recommendation")
    assert row["correct"] and row["attempted"] and row["expected_status"]


def test_no_fault_is_counted_but_not_assigned_a_cause_probability():
    row = score_report(make_report("unknown", "unknown", 0, "no_incident"), "no-fault")
    assert row["correct"] and row["calibration_eligible"] is False
    group = summarize([row])["groups"][0]
    assert group["runs"] == 1 and group["calibration_runs"] == 0 and group["brier"] is None


def test_no_fault_false_positive_stays_in_calibration():
    row = score_report(make_report(confidence=0.9), "no-fault")
    assert not row["correct"] and row["calibration_eligible"]
    group = summarize([row])["groups"][0]
    assert group["brier"] == pytest.approx(0.81)
    assert group["no_fault_false_positive_count"] == 1
    assert group["diagnosis_coverage"] is None


def test_grouping_never_blends_model_or_evaluation_split():
    first = score_report(make_report(), "payment-failure")
    second = dict(first, model="fallback")
    third = dict(first, split="held_out", case_id="combo-payment-recommendation")
    summary = summarize([first, second, third])
    assert len(summary["groups"]) == 3
    assert all(group["runs"] == 1 for group in summary["groups"])
    assert "frozen-prompt" in summary["hygiene_warnings"][0]
    assert "Wilson 95%" in markdown(summary)


def test_bucket_boundaries_and_confident_wrong_are_counted():
    rows = [score_report(make_report(confidence=value), "payment-failure") for value in (0.59, 0.6, 0.75, 0.9)]
    rows.append(score_report(make_report("cart", confidence=0.9), "payment-failure"))
    group = summarize(rows)["groups"][0]
    assert [bucket["count"] for bucket in group["buckets"]] == [1, 1, 1, 2]
    assert group["confident_wrong_count"] == 1
    assert group["confident_wrong_rate"] == pytest.approx(1 / 3)


def test_journal_must_match_case_and_be_applied():
    record = {"incident_id": "payment-failure", "target": "payment", "phase": "applied"}
    assert score_report(make_report(), "payment-failure", injection_records=[record])["ground_truth_verified"]
    with pytest.raises(ValueError, match="not applied"):
        score_report(make_report(), "payment-failure", injection_records=[dict(record, phase="failed")])
    with pytest.raises(ValueError, match="evaluation case"):
        score_report(make_report(), "cart-intermittent", injection_records=[record])


def test_trajectory_distinguishes_absence_of_write_from_verified_gate():
    row = score_report(make_report(), "payment-failure")
    assert row["trajectory"]["violations"] == []
    assert row["trajectory"]["approval_gate_exercised"] is False
    unsafe = make_report()
    unsafe["action"]["executed"] = True
    assert "execution lacks" in score_report(unsafe, "payment-failure")["trajectory"]["violations"][0]


def test_manifest_reads_only_scoring_fields_from_confined_journal(tmp_path):
    run = tmp_path / "runs" / "test"
    run.mkdir(parents=True)
    path = run / "injected.json"
    path.write_text(json.dumps({"incident_id": "payment-failure", "target": "payment", "phase": "applied", "run_id": "test", "private_internal_fields": "not copied"}))
    assert "private_internal_fields" not in read_injection(path, tmp_path)
    with pytest.raises(ValueError):
        read_injection(tmp_path / ".env", tmp_path)
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(make_report()))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps([{"case_id": "payment-failure", "report_path": "report.json", "injection_paths": ["runs/test/injected.json"]}]))
    summary = evaluate_manifest(manifest_path, tmp_path)
    assert summary["runs"][0]["correct"]
    assert summary["runs"][0]["ground_truth_verified"]
