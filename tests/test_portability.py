"""Offline shell contracts and isolation of the Linux gate."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.crossplatform_check import docker_command
from scripts.platform_support import ROOT, docker_host

NAMES = ("preflight", "morning", "crossplatform_check", "up", "checkpoint2", "checkpoint3", "demo", "ui")


@pytest.mark.parametrize("platform,expected", [("win32", "npipe:////./pipe/docker_engine"),
                                                ("linux", "unix:///var/run/docker.sock")])
def test_docker_host_defaults_and_operator_override(platform, expected):
    assert docker_host({}, platform) == expected
    assert docker_host({"DOCKER_HOST": "tcp://operator-host:1234"}, platform) == "tcp://operator-host:1234"


def test_linux_gate_mount_is_read_only_and_does_not_forward_credentials(tmp_path):
    command = docker_command(tmp_path / "repo with spaces")
    assert command[command.index("--mount") + 1].endswith(",target=/repo,readonly")
    assert "python:3.11" in command
    assert "-e" not in command
    assert "--exclude=.env" in command[-1] and "--exclude=runs" in command[-1]
    assert "DOCKER_HOST=tcp://127.0.0.1:1" in command[-1]
    assert "not live" in command[-1] and "--basetemp=/tmp/" in command[-1]


def test_operator_readiness_checks_are_outside_diagnostic_imports():
    import ast
    for directory in ("agent", "detect", "tools"):
        for path in (ROOT / directory).glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom):
                    assert node.module not in {"scripts.preflight", "scripts.operator"}
                if isinstance(node, ast.Import):
                    assert not any(n.name in {"scripts.preflight", "scripts.operator"} for n in node.names)
            assert "preflight_checks.json" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", NAMES)
def test_bash_help_from_other_directory_needs_no_environment(name, tmp_path):
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not installed on this host; Linux gate exercises this")
    script = (ROOT / "scripts" / (name + ".sh")).as_posix()
    # No shell interpolation. Git Bash accepts Windows drive paths via argv.
    env = dict(os.environ, INCIDENT_ZERO_PYTHON="missing-interpreter", DOCKER_HOST="tcp://127.0.0.1:1")
    for flag in ("--help", "-Help", "-h"):
        result = subprocess.run([bash, script, flag], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert "Usage:" in result.stdout


@pytest.mark.parametrize("name", NAMES)
def test_shell_files_use_portable_paths_and_help_aliases(name):
    bash = (ROOT / "scripts" / (name + ".sh")).read_bytes()
    assert b"\r\n" not in bash
    assert b"BASH_SOURCE[0]" in bash
    ps = (ROOT / "scripts" / (name + ".ps1")).read_text()
    assert "Usage:" in ps and "[Alias('h','-help')]" in ps
    assert "tcp://localhost:2375" not in ps


def test_morning_no_smoke_does_not_dispatch_checkpoint(monkeypatch, tmp_path):
    from scripts import morning
    calls = []
    monkeypatch.setattr(morning, "ROOT", tmp_path)
    monkeypatch.setattr(morning, "run_module", lambda *a: calls.append(a) or 0)
    assert morning.main(["--no-smoke"]) == 0
    assert [a[0] for a in calls] == ["scripts.preflight", "scripts.validate_reports", "scripts.crossplatform_check"]


def test_failed_preflight_refuses_smoke_but_runs_read_only_gates(monkeypatch, tmp_path):
    from scripts import morning
    calls = []
    monkeypatch.setattr(morning, "ROOT", tmp_path)
    monkeypatch.setattr(morning, "run_module", lambda *a: calls.append(a) or int(a[0] == "scripts.preflight"))
    assert morning.main([]) == 1
    assert not any(a[0] == "scripts.operator" for a in calls)
