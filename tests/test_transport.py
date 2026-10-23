"""Backend failures retain bounded retries without a short whole-tool cutoff."""

import json
import subprocess
from unittest.mock import Mock

import pytest
import requests

from faultctl.cli import Controller
from tools import common


def response(data=None, status=200):
    result = Mock(ok=status < 400, status_code=status, text="backend unavailable")
    result.json.return_value = {} if data is None else data
    result.raise_for_status.side_effect = None if status < 400 else requests.HTTPError(str(status))
    return result


def test_http_read_retries_once_with_eight_second_timeout(monkeypatch):
    fetch = Mock(side_effect=[requests.Timeout("busy"), response({"data": "ready"})])
    monkeypatch.setattr(common.requests, "get", fetch)
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)
    assert common.get_json("http://backend/read") == {"data": "ready"}
    assert fetch.call_count == 2
    assert all(call.kwargs["timeout"] == 8 for call in fetch.call_args_list)


def test_backend_status_failure_retries_only_once(monkeypatch):
    fetch = Mock(return_value=response(status=503))
    monkeypatch.setattr(common.requests, "get", fetch)
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)
    with pytest.raises(common.BackendError, match="503"):
        common.get_json("http://backend/read")
    assert fetch.call_count == 2


def test_docker_retry_preserves_both_log_streams(monkeypatch):
    command = Mock(side_effect=[subprocess.TimeoutExpired("docker", 8),
        subprocess.CompletedProcess([], 0, "stdout record", "stderr record")])
    monkeypatch.setattr(common.subprocess, "run", command)
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)
    assert common.docker("logs", "checkout", include_stderr=True) == "stdout record\nstderr record"
    assert command.call_count == 2
    assert all(call.kwargs["timeout"] == 8 for call in command.call_args_list)


def test_jaeger_discovers_published_port_before_proxy(monkeypatch):
    monkeypatch.delenv("JAEGER_URL", raising=False)
    command = Mock(return_value="0.0.0.0:52684\n[::]:52684\n")
    monkeypatch.setattr(common, "docker", command)
    assert common.jaeger_endpoints() == ["http://localhost:52684/jaeger/ui/api",
                                        "http://localhost:8080/jaeger/ui/api"]
    command.assert_called_once_with("port", "jaeger", "16686")


def test_jaeger_proxy_is_fallback_after_failed_direct_read(monkeypatch):
    monkeypatch.setattr(common, "jaeger_endpoints", lambda: ["http://direct/api", "http://proxy/api"])
    fetch = Mock(side_effect=[common.BackendError("direct unavailable"), {"data": ["payment"]}])
    assert common.jaeger_json("services", fetch=fetch) == {"data": ["payment"]}
    assert [call.args[0] for call in fetch.call_args_list] == ["http://direct/api/services", "http://proxy/api/services"]
    assert not any(call.kwargs for call in fetch.call_args_list)


def test_jaeger_direct_read_does_not_touch_proxy(monkeypatch):
    monkeypatch.setattr(common, "jaeger_endpoints", lambda: ["http://direct/api", "http://proxy/api"])
    fetch = Mock(return_value={"data": []})
    params = {"service": "checkout"}
    assert common.jaeger_json("/traces", params=params, fetch=fetch) == {"data": []}
    fetch.assert_called_once_with("http://direct/api/traces", params=params)


def test_missing_port_discovery_uses_proxy(monkeypatch):
    monkeypatch.delenv("JAEGER_URL", raising=False)
    monkeypatch.setattr(common, "docker", Mock(side_effect=common.BackendError("not published")))
    assert common.jaeger_endpoints() == ["http://localhost:8080/jaeger/ui/api"]


def test_tool_remains_observable_after_three_second_target(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(common.time, "monotonic", lambda: clock[0])
    fetch = Mock(return_value=response({"data": []}))
    monkeypatch.setattr(common.requests, "get", fetch)

    @common.bounded("fixture")
    def sample():
        clock[0] = 4.0
        common.get_json("http://backend/read")
        return common.envelope("sample", "fixture", "sample", common.window(), [])

    result = sample()
    assert not result.get("error")
    assert result["elapsed_s"] == 4
    assert fetch.call_args.kwargs["timeout"] == 8


def test_faultctl_status_uses_direct_jaeger_for_services_and_traffic(monkeypatch):
    controller = Controller.__new__(Controller)
    controller.services = lambda: {"frontend": {"container_name": "frontend"}}

    def docker_read(command, **kwargs):
        if command[1] == "inspect":
            output = json.dumps([{"Name": "/frontend", "State": {"Status": "running"}}])
        else:
            output = "0.0.0.0:52000\n"
        return subprocess.CompletedProcess(command, 0, output, "")

    controller.run = docker_read
    monkeypatch.setattr(common, "docker", lambda *args: "0.0.0.0:52684\n")
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)
    seen = []
    trace_reads = []

    def fetch(url, **kwargs):
        seen.append((url, kwargs))
        if url.endswith("/services"):
            return response({"data": ["frontend", "checkout", "payment"]})
        if url.endswith("/traces"):
            trace_reads.append(url)
            return response({"data": [{"traceID": str(index)} for index in range(len(trace_reads))]})
        return response({"status": "green"})

    monkeypatch.setattr(common.requests, "get", fetch)
    result = controller.status(traffic_seconds=1)
    assert result["ok"]
    jaeger_reads = [(url, kwargs) for url, kwargs in seen if "/jaeger/" in url]
    assert len(jaeger_reads) == 3
    assert all(url.startswith("http://localhost:52684/") for url, _ in jaeger_reads)
    assert all(kwargs["timeout"] == 8 for _, kwargs in seen)
    assert all("elapsed_s" in check for check in result["checks"])
