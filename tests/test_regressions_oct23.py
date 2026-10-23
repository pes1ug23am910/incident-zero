"""Incident-class regressions. Strict xfails name the outstanding fold contract.

All Docker/provider calls in these tests are fakes. Removing an xfail is part of
landing its fix: an unexpected pass intentionally fails the suite.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from test_faultctl import controller

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_live_io(monkeypatch):
    import requests
    def forbidden(*args, **kwargs):
        raise AssertionError("Regression fixture attempted live I/O")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


def example():
    return json.loads((ROOT / "schema/examples/valid.json").read_text())


def test_outermost_span_does_not_replace_origin():
    from tools.traces import trace_summary
    trace = json.loads((ROOT / "tests/fixtures/payment_failure_trace.json").read_text())
    result = trace_summary(trace)
    assert result["first_error_span"]["service"] == "payment"
    assert result["first_error_span"]["operation"].endswith("PaymentService/Charge")
    assert len(result["error_spans"]) > 8


def test_flag_name_in_report_string_is_rejected_without_echo():
    from schema.validate import validate_report, fixture_resolver
    report = example()
    report["root_cause"]["cause"] = "paymentFailure"
    errors = validate_report(report, resolver=fixture_resolver(ROOT / "schema/examples/evidence_fixture.json"))
    assert errors and any("root_cause.cause" in e for e in errors)
    assert all("paymentFailure" not in e for e in errors)


def test_flag_update_does_not_recreate_control_container(controller, monkeypatch):
    controller.prepare_overlay()
    monkeypatch.setattr(controller, "inspect", lambda _: {"Mounts": [
        {"Source": str(controller.active.parent), "Destination": "/etc/flagd"}]})
    monkeypatch.setattr("faultctl.cli.time.sleep", lambda _: None)
    monkeypatch.setattr(controller, "compose", lambda *a, **k: pytest.fail("recreate causes unrelated side blips"))
    calls = []
    monkeypatch.setattr(controller, "run", lambda a, **k: calls.append(a) or subprocess.CompletedProcess(a, 0, "reload", ""))
    controller.set_flag("paymentFailure", "100%")
    assert all(call[:2] == ["docker", "logs"] for call in calls)


def test_jaeger_proxy_only_is_usable(monkeypatch):
    from tools import common
    monkeypatch.setattr(common, "docker", lambda *a, **k: "")
    monkeypatch.setenv("JAEGER_URL", "http://proxy-only/jaeger/ui/api")
    calls = []
    result = common.jaeger_json("services", fetch=lambda url: calls.append(url) or {"data": ["payment"]})
    assert result["data"] == ["payment"]
    assert calls == ["http://proxy-only/jaeger/ui/api/services"]


def test_read_budget_accepts_a_2_6_second_response(monkeypatch):
    from tools import common
    class Response:
        ok = True
        def json(self):
            return {"observed_after_s": 2.6}
    def get(url, **kwargs):
        assert kwargs["timeout"] > 2.6
        return Response()
    monkeypatch.setattr(common.requests, "get", get)
    assert common.get_json("http://fixture") == {"observed_after_s": 2.6}


def test_log_fallback_is_scoped_to_requested_demo_service(monkeypatch):
    from tools import logs
    calls = []
    monkeypatch.setattr(logs, "container_names", lambda: ["checkout", "payment"])
    monkeypatch.setattr(logs, "docker", lambda *a, **k: calls.append(a) or "")
    assert logs.docker_log_lines("checkout") == []
    assert calls[0][-1] == "checkout"
    with pytest.raises(ValueError):
        logs.docker_log_lines("unrelated-container")
    assert len(calls) == 1


@pytest.mark.xfail(strict=True, reason="fold: Addendum 2 reset external faults, not only injection journal")
def test_reset_detects_unjournaled_resource_limit_change(controller, monkeypatch):
    controller.ensure_pristine()
    calls = []
    monkeypatch.setattr(controller, "services", lambda: {"payment": {"deploy": {"resources": {"limits": {"cpus": "1"}}}}})
    monkeypatch.setattr(controller, "inspect", lambda _: {
        "HostConfig": {"NanoCpus": 50_000_000, "Memory": 100, "MemorySwap": 200},
        "State": {"Status": "running"}, "Mounts": []})
    def compose(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(controller, "compose", compose)
    result = controller.reset(timeout_s=0)
    # A reset may restore the limit or explicitly fail read-back; success with the
    # injected cap intact is never acceptable. No external command is permitted.
    assert not result["ok"] or any("--force-recreate" in a and "payment" in a for a in calls)


def test_memory_reaped_service_remains_an_oom_alert_after_detector_restart():
    from detect.core import Detector
    health = {"telemetry_available": True, "evidence_ids": [], "data": [{
        "service": "recommendation", "status": "exited", "oom_killed": True,
        "memory_mb": None, "rps": 0, "error_rate": 0, "p95_ms": 0, "restarts": 0}]}
    alert = Detector().evaluate(health, now=100)
    assert any(a["signal"] == "oom_killed" for a in alert["anomalies"])


def test_model_unavailable_is_not_a_deterministic_success(tmp_path):
    from agent.llm_router import Router, ModelUnavailable
    router = Router(tmp_path, env={})
    with pytest.raises(ModelUnavailable):
        router.complete([], [])
    assert router.summary()["model"].startswith("failed:")
    assert router.summary()["models_used"] == []


def test_prompt_hash_tracks_actual_prompt_and_report_builder():
    from agent import prompts, reporting
    current = hashlib.sha256(prompts.SYSTEM.encode()).hexdigest()
    assert prompts.PROMPT_SHA256 == current == reporting.PROMPT_SHA256


@pytest.mark.xfail(strict=True, reason="fold: Addendum 3 item 1 single active investigation latch")
def test_duplicate_alerts_join_running_investigation(tmp_path, monkeypatch):
    import detect.watch as watch
    calls = []
    monkeypatch.setattr(watch, "ROOT", tmp_path)
    monkeypatch.setattr(watch, "run_path", lambda **kwargs: tmp_path)
    monkeypatch.setattr(watch, "write_alert", lambda *a: tmp_path / "alert.json")
    monkeypatch.setattr(watch.Detector, "prime_baseline", lambda *a, **k: None)
    ticks = iter([{"anomalies": [{"service": "payment"}]}, {"anomalies": [{"service": "payment"}]}])
    def poll(*args, **kwargs):
        try:
            return next(ticks)
        except StopIteration:
            raise KeyboardInterrupt
    monkeypatch.setattr(watch.Detector, "poll", poll)
    monkeypatch.setattr(watch.time, "sleep", lambda _: None)
    class Running:
        def poll(self):
            return None
    monkeypatch.setattr(watch.subprocess, "Popen", lambda *a, **k: calls.append(a) or Running())
    assert watch.main([]) == 0
    assert len(calls) == 1


@pytest.mark.xfail(strict=True, reason="fold: Addendum 3 item 3 risk per action for two supported causes")
def test_two_causes_keep_two_separately_reviewed_proposals():
    from agent.policy import propose
    report = example()
    report["status"] = "diagnosed"
    report["root_causes"] = [{"component": component, "category": category, "confidence": .9,
        "confidence_model": .9, "confidence_evidence": .9, "cause": "fixture", "evidence_ids": [],
        "explains_symptoms": [component]} for component, category in
        [("payment", "application_flag"), ("recommendation", "container_down")]]
    result = propose(report)
    assert {(a["type"], a["target"]) for a in result["proposed_actions"]} == {
        ("toggle_flag", "payment"), ("restart_service", "recommendation")}


@pytest.mark.parametrize("identifier", ["kb:cache#confirm", "mem:opaque-example"])
def test_hint_ids_are_never_telemetry_evidence(identifier):
    from schema.validate import validate_report, fixture_resolver
    report = example()
    report["evidence"][0]["id"] = identifier
    errors = validate_report(report, resolver=fixture_resolver(ROOT / "schema/examples/evidence_fixture.json"))
    assert errors and any("evidence" in e for e in errors)


@pytest.mark.xfail(strict=True, reason="fold: Addendum 7 and Knowledge Addendum item 1 opaque memory ids", raises=(ModuleNotFoundError, AssertionError))
def test_memory_ids_and_index_records_do_not_leak_incident_label(tmp_path):
    from memory.store import MemoryStore
    from schema.validate import fixture_resolver
    indexed = []
    class Index:
        def upsert_memory(self, record, **kwargs):
            indexed.append(deepcopy(record))
    report = example()
    report["incident_id"] = "payment-failure-r3"
    memory = MemoryStore(tmp_path, Index(), resolver=fixture_resolver(ROOT / "schema/examples/evidence_fixture.json"))
    memory.remember(report, report_path=Path("reports/payment-failure-r3/report.json"))
    assert indexed
    assert "payment-failure" not in json.dumps(indexed)
    assert all("payment-failure" not in p.name + p.read_text() for p in tmp_path.glob("*.json"))


@pytest.mark.xfail(strict=True, reason="fold: Addendum 10 H10 configurable 150s alert wait")
def test_150_second_alert_budget_uses_virtual_clock(tmp_path):
    from detect.watch import wait_for_alert
    now = [0.0]
    class Quiet:
        def poll(self, **kwargs):
            return None
    def sleep(seconds):
        now[0] += seconds
    assert wait_for_alert(Quiet(), run_dir=tmp_path, timeout_s=150,
                          clock=lambda: now[0], sleep=sleep, stop_path=tmp_path / "STOP") is None
    assert now[0] == 150


@pytest.mark.xfail(strict=True, reason="fold: Addendum 3 item 2 spanmetrics and traces share one family")
def test_spanmetrics_do_not_double_count_traces():
    from agent.evidence import observation_family
    metric = 'metric:query{__query__="rate(traces_span_metrics_calls_total[2m])",service_name="payment"}@100=1'
    assert observation_family(metric, {"source": "prometheus", "data": {"query": "traces_span_metrics_calls_total"}}) == observation_family("trace:" + "a" * 32, {"source": "jaeger"})
