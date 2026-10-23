"""Driver authorization and cleanup with command fakes; never starts the demo."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from scripts import hands_rehearsal as driver


def test_live_driver_requires_explicit_switch_before_any_command(monkeypatch):
    monkeypatch.setattr(driver,'command',lambda *a,**k:pytest.fail('must not run'))
    with pytest.raises(SystemExit):
        driver.main(['payment-failure','--report-id','new','--operator','Tester'])


def test_existing_bundle_refused_before_any_command(tmp_path,monkeypatch):
    monkeypatch.setattr(driver,'ROOT',tmp_path)
    (tmp_path/'reports/existing').mkdir(parents=True)
    monkeypatch.setattr(driver,'command',lambda *a,**k:pytest.fail('must not run'))
    with pytest.raises(SystemExit):
        driver.main(['payment-failure','--live','--report-id','existing','--operator','Tester'])


def test_live_driver_never_allows_test_environment(tmp_path,monkeypatch):
    monkeypatch.setattr(driver,'ROOT',tmp_path)
    monkeypatch.setenv('INCIDENT_ZERO_TEST','1')
    monkeypatch.setattr(driver,'command',lambda *a,**k:pytest.fail('must not run'))
    with pytest.raises(SystemExit):
        driver.main(['payment-failure','--live','--report-id','new','--operator','Tester'])


def test_driver_resets_after_diagnosis_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(driver,'ROOT',tmp_path)
    monkeypatch.delenv('INCIDENT_ZERO_TEST',raising=False)
    calls=[]
    def command(args,**kwargs):
        calls.append(args)
        if args[0]=='agent.run':
            raise RuntimeError('model unavailable')
        return {}
    monkeypatch.setattr(driver,'command',command)
    monkeypatch.setattr(driver,'require_clean',lambda *a:None)
    monkeypatch.setattr(driver,'check_demo_unchanged',lambda:None)
    monkeypatch.setattr(driver.Detector,'prime_baseline',lambda *a,**k:None)
    monkeypatch.setattr(driver.Detector,'poll',lambda *a,**k:None)
    monkeypatch.setattr(driver,'wait_for_alert',lambda *a,**k:{'signal':'error_rate'})
    monkeypatch.setattr(driver,'write_alert',lambda a,d:d/'alert.json')
    assert driver.main(['payment-failure','--live','--report-id','new','--operator','Tester'])==1
    assert [c[:2] for c in calls].count(['faultctl','reset'])==2
    assert calls[-1][:2]==['faultctl','reset']


@pytest.fixture
def loop(tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    monkeypatch.delenv("INCIDENT_ZERO_TEST", raising=False)
    directory = tmp_path / "runs/operator"
    (directory / "evidence").mkdir(parents=True)
    monkeypatch.setattr(driver, "run_path", lambda **kwargs: directory)
    state = SimpleNamespace(commands=[], resumes=[], final_status="fixed", baseline=None)
    report = {"run_id": "runs/fixture", "status": "diagnosed", "proposed_actions": [{"type": "toggle_flag"}], "verification": {}}

    def command(args, **kwargs):
        state.commands.append(args)
        if args[0] == "agent.run":
            path = Path(args[args.index("--out") + 1])
            path.write_text(json.dumps(report), encoding="utf-8")
            path.with_suffix(".md").write_text("Observed diagnosis", encoding="utf-8")
        return {}

    def resume(value, decision=None, **kwargs):
        state.resumes.append((decision, kwargs))
        return {**value, "status": state.final_status, "action_history": [{"decision": decision}],
            "verification": {"recovered": state.final_status == "fixed", "requests_observed": 35,
                "samples": [{"elapsed_s": 150, "qualified_recovery": True}, {"elapsed_s": 180, "qualified_recovery": True}]}}

    def save(report, path, service):
        path.write_text(json.dumps(report), encoding="utf-8")
        path.with_suffix(".md").write_text("Final " + report["status"], encoding="utf-8")
        (path.parent / "action-log.jsonl").write_text('{"event":"verify"}\n', encoding="utf-8")

    monkeypatch.setattr(driver, "command", command)
    monkeypatch.setattr(driver, "resume", resume)
    monkeypatch.setattr(driver, "save_bundle", save)
    monkeypatch.setattr(driver, "require_clean", lambda *a: {"verified": True, "elapsed_s": 180, "samples": []})
    monkeypatch.setattr(driver, "check_demo_unchanged", lambda: None)
    monkeypatch.setattr(driver, "Detector", lambda: SimpleNamespace(prime_baseline=lambda **k: None, poll=lambda **k: state.baseline))
    monkeypatch.setattr(driver, "wait_for_alert", lambda *a, **k: {"signal": "error_rate"})
    monkeypatch.setattr(driver, "write_alert", lambda alert, path: path / "alert.json")
    monkeypatch.setattr(driver, "ActionService", lambda *a: SimpleNamespace())
    monkeypatch.setattr(driver, "validate_report", lambda *a, **k: [])
    state.root = tmp_path
    return state


def test_complete_loop_retains_both_windows_action_log_and_real_approval(loop, capsys):
    assert driver.main(["payment-failure", "--live"]) == 0
    bundle = loop.root / "reports/payment-failure-loop-r1"
    outcome = json.loads((bundle / "hands-rehearsal.json").read_text())
    assert outcome["status"] == "fixed"
    assert outcome["approval_path"] == "terminal"
    assert outcome["test_auto_approval"] is False
    assert outcome["recovery_verification"]["before"]["elapsed_s"] >= 180
    assert outcome["recovery_verification"]["after"]["elapsed_s"] >= 180
    assert "inject_to_recovery_s" in outcome["timings"]
    assert loop.resumes[0][1]["report_path"] == bundle / "report.json"
    assert loop.resumes[0][1]["auto_approve_for_tests"] is False
    assert "Action-log excerpt:" in capsys.readouterr().out


def test_rejection_passes_no_approval_and_records_no_recovery_duration(loop):
    loop.final_status = "needs_human"
    assert driver.main(["payment-failure", "--live", "--reject"]) == 0
    outcome = json.loads((loop.root / "reports/payment-failure-loop-r1/hands-rehearsal.json").read_text())
    assert loop.resumes[0][0] == {"decision": "reject"}
    assert "inject_to_recovery_s" not in outcome["timings"]


def test_auto_approval_requires_both_gates_and_records_test_path(loop, monkeypatch):
    with pytest.raises(SystemExit):
        driver.main(["payment-failure", "--live", "--auto-approve-for-tests"])
    assert loop.commands == []
    monkeypatch.setenv("INCIDENT_ZERO_TEST", "1")
    assert driver.main(["payment-failure", "--live", "--auto-approve-for-tests"]) == 0
    outcome = json.loads((loop.root / "reports/payment-failure-loop-r1/hands-rehearsal.json").read_text())
    assert outcome["test_auto_approval"] is True
    assert loop.resumes[0][1]["auto_approve_for_tests"] is True


def test_baseline_anomaly_blocks_injection_and_still_cleans(loop):
    loop.baseline = {"signal": "error_rate"}
    assert driver.main(["payment-failure", "--live"]) == 1
    assert [command[:2] for command in loop.commands] == [["faultctl", "reset"], ["faultctl", "reset"]]


def test_browser_mode_never_invokes_terminal_resume(loop, monkeypatch):
    monkeypatch.setattr(driver, "ensure_control_room", lambda *a: None)
    monkeypatch.setattr(driver, "wait_for_browser", lambda *a: {"run_id": "runs/fixture", "status": "fixed", "verification": {"recovered": True}})
    assert driver.main(["payment-failure", "--live", "--approval-mode", "browser"]) == 0
    assert loop.resumes == []


def test_forced_nonrecovery_requires_test_gate_before_any_command(loop):
    with pytest.raises(SystemExit):
        driver.main(["payment-failure", "--live", "--force-nonrecovery"])
    assert loop.commands == []


def test_control_waits_for_verifying_and_restores_captured_swarm(monkeypatch):
    cancelled = Mock()
    cancelled.wait.side_effect = [False, False]
    response = Mock()
    response.json.return_value = {"success": True}
    get = Mock(return_value=response)
    post = Mock(return_value=response)
    monkeypatch.setattr(driver.requests, "get", get)
    monkeypatch.setattr(driver.requests, "post", post)
    service = SimpleNamespace(executor=SimpleNamespace(load_url="http://localhost/loadgen"),
        attempts=Mock(side_effect=[[{"report_id": "r", "phase": "executing"}], [{"report_id": "r", "phase": "verifying"}]]))
    control = driver.RunControl(service, "r", force_nonrecovery=True)
    control.previous_load = {"users": 37, "spawn_rate": 2.5}
    control.cancelled = cancelled
    control._run()
    assert service.attempts.call_count == 2
    get.assert_called_once_with("http://localhost/loadgen/stop", timeout=10)
    control.finish()
    post.assert_called_once_with("http://localhost/loadgen/swarm", data={"user_count": 37, "spawn_rate": 2.5}, timeout=10)
    assert [item["operation"] for item in control.interventions] == ["stop_locust_swarm", "restore_locust_swarm"]
    assert control.interventions[0]["verifier_overridden"] is False


def test_browser_wait_requires_saved_decision_not_initial_diagnosis(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"run_id": "r", "status": "diagnosed"}))
    sleeps = []
    def completed(delay):
        sleeps.append(delay)
        path.write_text(json.dumps({"run_id": "r", "status": "needs_human", "action_history": [{"decision": {"decision": "reject"}}]}))
    monkeypatch.setattr(driver.time, "sleep", completed)
    result = driver.wait_for_browser(path, "r", None)
    assert sleeps == [.5]
    assert result["status"] == "needs_human"


@pytest.mark.parametrize("requests_observed, succeeds", [(19, False), (20, True)])
def test_reset_clearance_requires_measured_requests_for_full_window(tmp_path, monkeypatch, requests_observed, succeeds):
    elapsed = [0.0]
    original = driver.wait_for_clean
    def clock():
        return elapsed[0]
    def sleep(delay):
        elapsed[0] += delay
    def wait(**kwargs):
        return original(**kwargs, clock=clock, sleep=sleep)
    monkeypatch.setattr(driver, "wait_for_clean", wait)
    monkeypatch.setattr(driver, "health_table", lambda **k: {"telemetry_available": True, "data": [
        {"service": "frontend", "status": "running", "rps": 5, "error_rate": 0},
        {"service": "load-generator", "status": "running"}], "evidence_ids": []})
    monkeypatch.setattr(driver, "LiveSampler", lambda: lambda *a: {"available": True,
        "requests_observed": requests_observed, "load_running": True, "values": [0], "evidence_ids": []})
    if not succeeds:
        with pytest.raises(RuntimeError, match="traffic-qualified recovery"):
            driver.require_clean(tmp_path, 180)
    else:
        result = driver.require_clean(tmp_path, 180)
        assert result["elapsed_s"] >= 180
        assert all(point["requests_observed"] >= 20 and point["load_running"] for point in result["samples"][-2:])
    assert elapsed[0] >= 180


def test_real_control_room_refuses_existing_mock_without_starting_process(monkeypatch):
    monkeypatch.setattr(driver.requests, "get", lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"mode": "mock"}))
    monkeypatch.setattr(driver.subprocess, "Popen", lambda *a, **k: pytest.fail("must not start another server"))
    with pytest.raises(RuntimeError, match="non-real"):
        driver.ensure_control_room()
