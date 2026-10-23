"""Exercise the operator boundary without needing or modifying Docker."""
from argparse import Namespace
import json
from pathlib import Path
import subprocess

import pytest

from faultctl.cli import Controller, FaultError, FLAGS, INFRA, write_json


@pytest.fixture
def controller(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    package = root / "faultctl"
    package.mkdir(parents=True)
    demo = tmp_path / "official-demo"
    original = demo / "src" / "flagd" / "demo.flagd.json"
    original.parent.mkdir(parents=True)
    original.write_text(json.dumps({"flags": {key: {"defaultVariant": "off", "variants": {"off": False, "on": True, "100%": 1, "50%": 0.5}} for key, _, _ in FLAGS.values()}}), encoding="utf-8")
    (package / "config.yaml").write_text(json.dumps({"demo_dir": str(demo), "compose_file": "docker-compose.minimal.yml", "demo_version": "2.0.2", "netem_image": "test-helper", "containers": {"payment": "payment", "recommendation": "recommendation", "flagd": "flagd"}}), encoding="utf-8")
    monkeypatch.delenv("INCIDENT_ZERO_DEMO_DIR", raising=False)
    control = Controller(root)
    monkeypatch.setattr(control, "services", lambda: {name: {"container_name": name} for name in ("payment", "recommendation", "flagd")})
    monkeypatch.setattr(control, "inspect", lambda target: {"HostConfig": {"NanoCpus": 0, "Memory": 100, "MemorySwap": 200}, "State": {"Status": "running", "StartedAt": "before"}, "RestartCount": 0, "Mounts": [{"Source": str(original.parent), "Destination": "/etc/flagd"}]})
    monkeypatch.setattr(control, "status", lambda **kwargs: {"ok": True, "checks": [{"check": "mock-stack", "ok": True}]})
    monkeypatch.setattr(control, "compose", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "", ""))
    return control


def options(**kwargs):
    return Namespace(svc=kwargs.get("svc"), rate=kwargs.get("rate", "100%"), delay=kwargs.get("delay", "800ms"), loss=kwargs.get("loss", 10))


def test_all_spec_incidents_are_available():
    assert len(FLAGS) == 8
    assert {"container-stopped", "restart-loop", "cache-unavailable", "network-latency", "cpu-starve", "memory-starve"} == set(INFRA)


def test_pristine_copy_does_not_change_source(controller):
    before = controller.source.read_bytes()
    controller.ensure_pristine()
    assert controller.pristine.read_bytes() == before
    assert controller.source.read_bytes() == before


def test_changed_source_refuses_overwrite(controller):
    controller.ensure_pristine()
    before = controller.pristine.read_bytes()
    controller.source.write_text("{}", encoding="utf-8")
    with pytest.raises(FaultError, match="differs"):
        controller.ensure_pristine()
    assert controller.pristine.read_bytes() == before
    assert controller.source.read_text(encoding="utf-8") == "{}"


def test_stop_refuses_all_injection(controller):
    (controller.root / "STOP").touch()
    with pytest.raises(FaultError, match="STOP"):
        controller.inject("payment-failure", options())
    assert not controller.state_path.exists()


def test_service_allowlist_rejects_arbitrary_container(controller):
    with pytest.raises(FaultError, match="allowlisted"):
        controller.inject("cpu-starve", options(svc="other-teams-container"))
    assert not controller.state_path.exists()


def test_invalid_flag_variant_never_mutates(controller):
    with pytest.raises(FaultError, match="variant"):
        controller.inject("payment-failure", options(rate="bogus"))
    assert not controller.state_path.exists()


def test_failed_mutation_is_journaled_before_command(controller, monkeypatch):
    def failing_run(command, **kwargs):
        assert controller.state()["incidents"][0]["phase"] == "prepared"
        assert list((controller.root / "runs").glob("*/injected.json"))
        raise FaultError("Docker unavailable")
    monkeypatch.setattr(controller, "run", failing_run)
    with pytest.raises(FaultError, match="Docker unavailable"):
        controller.inject("cpu-starve", options(svc="recommendation"))
    assert controller.state()["incidents"][0]["phase"] == "failed"


def test_flag_mutation_is_repo_local(controller, monkeypatch):
    before = controller.source.read_bytes()
    controller.ensure_pristine()
    monkeypatch.setattr(controller, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "reload received", ""))
    monkeypatch.setattr("faultctl.cli.time.sleep", lambda _: None)
    monkeypatch.setattr(controller, "inspect", lambda target: {"Mounts": [{"Source": str(controller.active.parent), "Destination": "/etc/flagd"}]})
    controller.set_flag("paymentFailure", "100%")
    assert controller.source.read_bytes() == before
    assert controller.pristine.read_bytes() == before
    assert json.loads(controller.active.read_text())["flags"]["paymentFailure"]["defaultVariant"] == "100%"
    override = json.loads(controller.override.read_text())
    assert Path(override["services"]["flagd"]["volumes"][0]["source"]).is_relative_to(controller.root)


def test_reset_allowed_with_stop_and_cancels_worker(controller):
    (controller.root / "STOP").touch()
    state = {"incidents": [{"run_id": "sample", "incident_id": "restart-loop", "target": "payment", "before": {"NanoCpus": 0, "Memory": 100, "MemorySwap": 200}}], "flag_override": False}
    write_json(controller.state_path, state)
    marker = controller.root / "runs" / "sample" / "loop.json"
    write_json(marker, {"cancelled": False, "target": "payment", "manual_restarts": 3})
    result = controller.reset(timeout_s=0)
    assert result["ok"]
    assert json.loads(marker.read_text())["cancelled"] is True
    assert controller.state()["incidents"] == []
    assert (controller.root / "STOP").exists()


def test_reset_failure_keeps_recovery_journal(controller, monkeypatch):
    write_json(controller.state_path, {"incidents": [{"run_id": "sample", "incident_id": "cpu-starve", "target": "payment", "before": {"NanoCpus": 0, "Memory": 100, "MemorySwap": 200}}], "flag_override": False})
    def fail(*args, **kwargs):
        raise FaultError("recreate failed")
    monkeypatch.setattr(controller, "compose", fail)
    result = controller.reset(timeout_s=0)
    assert not result["ok"]
    assert not result["fault_state_clean"]
    assert controller.state()["incidents"]


def test_readiness_failure_is_not_a_success(controller, monkeypatch):
    write_json(controller.state_path, {"incidents": [], "flag_override": True})
    write_json(controller.override, {"unused": True})
    monkeypatch.setattr(controller, "status", lambda **kwargs: {"ok": False, "checks": [{"check": "telemetry", "ok": False}]})
    result = controller.reset(timeout_s=0)
    assert result["fault_state_clean"] is True
    assert result["stack_ready"] is False
    assert result["ok"] is False
    assert not controller.override.exists()
    assert controller.state()["flag_override"] is False


def test_cancelled_loop_never_restarts(controller, monkeypatch):
    marker = controller.root / "runs" / "sample" / "loop.json"
    write_json(marker, {"cancelled": True, "target": "payment"})
    monkeypatch.setattr(controller, "run", lambda *args, **kwargs: pytest.fail("Cancelled loop attempted a command"))
    controller.loop(marker)


def test_stopped_network_target_gets_final_qdisc_readback(controller, monkeypatch):
    write_json(controller.state_path, {"incidents": [{"run_id": "sample", "incident_id": "network-latency", "target": "payment", "before": {"NanoCpus": 0, "Memory": 100, "MemorySwap": 200}}], "flag_override": False})
    monkeypatch.setattr(controller, "inspect", lambda target: {"State": {"Status": "exited"}})
    commands = []
    def qdisc(target, *args, **kwargs):
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, "qdisc noqueue 0: root refcnt 2", "")
    monkeypatch.setattr(controller, "netem", qdisc)
    result = controller.reset(timeout_s=0)
    assert result["ok"]
    assert commands == [("qdisc", "show", "dev", "eth0")]
    assert any(check["check"] == "netem-final:payment" for check in result["checks"])


def test_compose_version_override_and_cwd(controller, monkeypatch):
    monkeypatch.undo()
    seen = {}
    def record(command, **kwargs):
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr("faultctl.cli.subprocess.run", record)
    controller.compose("up", "-d")
    assert seen["env"]["DEMO_VERSION"] == "2.0.2"
    assert seen["cwd"] == controller.root
    assert str(controller.demo / "docker-compose.minimal.yml") in seen["command"]
