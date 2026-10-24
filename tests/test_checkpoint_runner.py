"""Rehearsal orchestration with local fakes; never invokes Docker or a model."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from detect.core import Thresholds
from scripts import checkpoint2 as runner


@pytest.fixture
def rehearsal(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    commands = []
    state = SimpleNamespace(baseline_alert=None, health={
        "telemetry_available": True, "data": [{"service": "frontend", "status": "running",
            "rps": 10.0, "error_rate": 0.0}], "evidence_ids": ["metric:fixture{}@1=0"],
        "warnings": []})

    class Detector:
        def __init__(self, config):
            self.thresholds = config
            self.last_health = None

        def prime_baseline(self, **kwargs):
            return {"data": []}

        def poll(self, **kwargs):
            self.last_health = state.health
            return state.baseline_alert

    def command(arguments, **kwargs):
        commands.append(arguments)
        if arguments[:2] == ["faultctl", "inject"]:
            count = len(arguments[arguments.index("--combo") + 1].split(",")) if "--combo" in arguments else 1
            return {"runs": [{"run_id": f"injection-{index}", "settings": "private operator configuration"}
                             for index in range(1, count + 1)]}
        if arguments[0] == "agent.run":
            output = Path(arguments[arguments.index("--out") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("{}", encoding="utf-8")
            output.with_suffix(".md").write_text("Observed report", encoding="utf-8")
        return {"ok": True}

    waiter = Mock(return_value={"detected_at": "2026-10-23T00:00:00+00:00", "signal": "error_rate",
        "service": "checkout", "observed": 0.2, "threshold": 0.05, "anomalies": []})
    monkeypatch.setattr(runner, "command", command)
    monkeypatch.setattr(runner, "Detector", Detector)
    monkeypatch.setattr(runner, "load_thresholds", lambda _: Thresholds())
    monkeypatch.setattr(runner, "require_clean", lambda *args: {"verified": True, "samples": []})
    monkeypatch.setattr(runner, "check_demo_unchanged", lambda: None)
    monkeypatch.setattr(runner, "wait_for_alert", waiter)
    state.commands = commands
    state.waiter = waiter
    state.root = tmp_path
    return state


def saved_alert(rehearsal):
    command = next(command for command in rehearsal.commands if command[0] == "agent.run")
    return json.loads(Path(command[command.index("--alert") + 1]).read_text(encoding="utf-8"))


def test_standard_run_preserves_sequence_and_injection_path(rehearsal):
    assert runner.main(["payment-failure", "--report-id", "payment-failure-r2"]) == 0
    assert [command[:2] for command in rehearsal.commands] == [
        ["faultctl", "reset"], ["faultctl", "inject"], ["agent.run", "--alert"],
        ["schema.validate", str(rehearsal.root / "reports/payment-failure-r2/report.json")],
        ["faultctl", "reset"]]
    assert rehearsal.commands[1] == ["faultctl", "inject", "payment-failure"]
    assert rehearsal.waiter.call_args.kwargs["run_dir"].name == "injection-1"
    assert rehearsal.waiter.call_args.kwargs["timeout_s"] == 90
    assert "private operator configuration" not in json.dumps(saved_alert(rehearsal))


def test_no_fault_observes_health_without_injection_or_alert_wait(rehearsal):
    assert runner.main(["no-fault", "--report-id", "no-fault-r1"]) == 0
    assert all(command[:2] != ["faultctl", "inject"] for command in rehearsal.commands)
    rehearsal.waiter.assert_not_called()
    alert = saved_alert(rehearsal)
    assert alert["signal"] == "no_alert"
    assert alert["observed"] == rehearsal.health["data"][0]["error_rate"]
    assert alert["evidence_ids"] == rehearsal.health["evidence_ids"]
    assert "no-fault" not in json.dumps(alert)
    result = json.loads((rehearsal.root / "reports/no-fault-r1/checkpoint2.json").read_text())
    assert result["injection_run_ids"] == []
    assert "observe_no_alert" in result["stage_seconds"]
    assert "inject" not in result["stage_seconds"]


def test_combo_waits_after_all_injections_and_keeps_all_run_ids(rehearsal):
    assert runner.main(["--combo", "payment-failure,container-stopped", "--svc", "recommendation",
                        "--report-id", "payment-stopped-r1"]) == 0
    assert rehearsal.commands[1] == ["faultctl", "inject", "--combo", "payment-failure,container-stopped",
                                     "--svc", "recommendation"]
    assert rehearsal.waiter.call_args.kwargs["run_dir"].name == "injection-2"
    result = json.loads((rehearsal.root / "reports/payment-stopped-r1/checkpoint2.json").read_text())
    assert result["injection_run_ids"] == ["injection-1", "injection-2"]
    assert result["injection_run_id"] == "injection-2"
    serialized = json.dumps(saved_alert(rehearsal))
    assert "payment-failure" not in serialized
    assert "container-stopped" not in serialized
    assert "private operator configuration" not in serialized


@pytest.mark.parametrize("incident", ["payment-failure", "no-fault"])
def test_preexisting_anomaly_aborts_and_still_resets(rehearsal, incident):
    rehearsal.baseline_alert = {"anomalies": [{"service": "ad", "signal": "cpu_percent"}]}
    assert runner.main([incident, "--report-id", "baseline-rejected"]) == 1
    assert [command[:2] for command in rehearsal.commands] == [["faultctl", "reset"], ["faultctl", "reset"]]
    rehearsal.waiter.assert_not_called()
    outcome_path = next((rehearsal.root / "runs").glob("*/checkpoint2.json"))
    outcome = json.loads(outcome_path.read_text())
    assert "preexisting baseline anomalies" in outcome["error"]
    assert "ad:cpu_percent" in outcome["error"]


def test_missing_no_fault_telemetry_cannot_become_a_clean_report(rehearsal):
    rehearsal.health["telemetry_available"] = False
    assert runner.main(["no-fault", "--report-id", "missing-health"]) == 1
    assert [command[:2] for command in rehearsal.commands] == [["faultctl", "reset"], ["faultctl", "reset"]]


@pytest.mark.parametrize("failure", [KeyError, KeyboardInterrupt])
def test_unexpected_failure_records_failed_outcome_and_preserves_cleanup(rehearsal, monkeypatch, failure):
    original = runner.command

    def fail_injection(arguments, **kwargs):
        if arguments[:2] == ["faultctl", "inject"]:
            raise failure("simulated interruption")
        return original(arguments, **kwargs)

    monkeypatch.setattr(runner, "command", fail_injection)
    arguments = ["payment-failure", "--report-id", "interrupted-run"]
    if failure is KeyboardInterrupt:
        with pytest.raises(KeyboardInterrupt):
            runner.main(arguments)
    else:
        assert runner.main(arguments) == 1
    outcome_path = next((rehearsal.root / "runs").glob("*/checkpoint2.json"))
    outcome = json.loads(outcome_path.read_text())
    assert outcome["ok"] is False
    assert outcome["error"]
    assert outcome["recovery_verification"]["after"]["verified"] is True
    assert [command[:2] for command in rehearsal.commands] == [["faultctl", "reset"], ["faultctl", "reset"]]


def test_unexpected_cleanup_failure_is_recorded(rehearsal, monkeypatch):
    calls = []

    def require_clean(*args):
        calls.append(args)
        if len(calls) == 2:
            raise KeyError("missing cleanup measurement")
        return {"verified": True, "samples": []}

    monkeypatch.setattr(runner, "require_clean", require_clean)
    assert runner.main(["payment-failure", "--report-id", "cleanup-failed"]) == 1
    outcome = json.loads((rehearsal.root / "reports/cleanup-failed/checkpoint2.json").read_text())
    assert outcome["ok"] is False
    assert "missing cleanup measurement" in outcome["cleanup_error"]


def test_cleanup_interrupt_records_failure_before_propagating(rehearsal, monkeypatch):
    calls = []

    def require_clean(*args):
        calls.append(args)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return {"verified": True, "samples": []}

    monkeypatch.setattr(runner, "require_clean", require_clean)
    with pytest.raises(KeyboardInterrupt):
        runner.main(["payment-failure", "--report-id", "cleanup-interrupted"])
    outcome = json.loads((rehearsal.root / "reports/cleanup-interrupted/checkpoint2.json").read_text())
    assert outcome["ok"] is False
    assert "cleanup interrupted" in outcome["cleanup_error"]


@pytest.mark.parametrize("arguments", [[], ["no-fault", "--svc", "recommendation"],
    ["payment-failure", "--alert-timeout", "150"],
    ["no-fault", "--combo", "payment-failure,container-stopped"],
    ["--combo", "payment-failure,"], ["--combo", "payment-failure,payment-failure"]])
def test_invalid_modes_refuse_before_operator_commands(rehearsal, arguments):
    with pytest.raises(SystemExit) as result:
        runner.main(arguments)
    assert result.value.code == 2
    assert rehearsal.commands == []
