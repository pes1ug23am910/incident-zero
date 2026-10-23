"""Docker stream, severity, evidence, and isolation behavior."""

import hashlib
import subprocess
from unittest.mock import Mock

import pytest
from tools import logs


def test_docker_fallback_reads_both_streams_filters_and_resolves(monkeypatch):
    stdout = '2026-10-23T09:00:00.123456789Z {"level":"info","message":"ready"}'
    stderr = '2026-10-23T09:00:01.123456789Z {"level":"error","message":"failed request","traceId":"abc"}'
    read = Mock(return_value=subprocess.CompletedProcess([], 0, stdout + "\n", stderr + "\n"))
    monkeypatch.setattr(logs, "container_names", lambda: ["checkout"])
    monkeypatch.setattr(logs.subprocess, "run", read)
    result = logs.get_logs("checkout", severity_min="ERROR")
    assert result["source"] == "docker"
    assert len(result["data"]) == 1
    row = result["data"][0]
    digest = hashlib.sha256(stderr.encode()).hexdigest()
    assert row["evidence_id"] == "dlog:checkout:" + digest
    assert row["trace_id"] == "abc"
    assert logs.resolve_docker_log("checkout", digest) == row
    assert read.call_args.args[0][:3] == ["docker", "logs", "--timestamps"]


def test_redact_entire_line_before_truncation(monkeypatch):
    lines = ['2026-10-23T09:00:00Z ERROR ' + "x" * 350 + ' feature_flag.key=anything',
             '2026-10-23T09:00:01Z WARN safe warning',
             '2026-10-23T09:00:02Z unclassified text']
    monkeypatch.setattr(logs, "docker_log_lines", lambda *args, **kwargs: lines)
    result = logs.get_logs("checkout")
    assert len(result["data"]) == 1
    assert result["data"][0]["body"] == "WARN safe warning"
    all_levels = logs.get_logs("checkout", severity_min="TRACE")
    assert len(all_levels["data"]) == 2


def test_docker_log_resolver_rejects_other_projects_and_bad_digests(monkeypatch):
    monkeypatch.setattr(logs, "container_names", lambda: ["checkout"])
    with pytest.raises(ValueError, match="project"):
        logs.resolve_docker_log("outside", "a" * 64)
    with pytest.raises(ValueError, match="digest"):
        logs.resolve_docker_log("checkout", "../escape")
