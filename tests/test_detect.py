"""Threshold, timing and cleanup contracts without live infrastructure."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from detect.core import Detector, Thresholds, anomalies, baseline_from_metrics, load_thresholds
from detect.recovery import clean_sample, wait_for_clean
from detect.watch import wait_for_alert


def table(**overrides):
    rows = [dict(service="frontend", status="running", restarts=0, error_rate=0,
                 p95_ms=50, rps=5, cpu_percent=3, memory_mb=10),
            dict(service="recommendation", status="running", restarts=0, error_rate=0,
                 p95_ms=20, rps=2, cpu_percent=1, memory_mb=10)]
    for row in rows:
        row.update(overrides.get(row["service"], {}))
    return {"data": rows, "telemetry_available": True,
            "evidence_ids": ["container:recommendation:Status=exited",
                             'metric:query{service_name="frontend"}@100=0.1']}


def test_all_service_anomalies_retained_and_primary_matches_schema():
    result = Detector().evaluate(table(frontend={"error_rate": .2},
                                       recommendation={"status": "exited"}), now=100)
    assert {(row["service"], row["signal"]) for row in result["anomalies"]} == {
        ("frontend", "error_rate"), ("recommendation", "container_status")}
    assert result["signal"] == "error_rate"
    assert result["window_s"] >= 120
    stopped = Detector().evaluate(table(recommendation={"status": "exited"}), now=100)
    assert stopped["signal"] == "container_health"
    assert stopped["observed"] == 1
    assert stopped["threshold"] == 0
    assert stopped["details"]["observed"] == "exited"


@pytest.mark.parametrize("field,value,expected", [("error_rate", .0499, False),
    ("error_rate", .05, True), ("p95_ms", 1499, False), ("p95_ms", 1500, True)])
def test_threshold_boundaries(field, value, expected):
    assert bool(Detector().evaluate(table(frontend={field: value}))) == expected


def test_missing_measurements_are_not_zero_or_alerts():
    result = table(frontend={"rps": None, "error_rate": None, "p95_ms": None},
                   recommendation={"rps": None, "error_rate": None, "p95_ms": None})
    result["telemetry_available"] = False
    assert Detector().evaluate(result) is None
    assert clean_sample(result)[0] is False


def test_debounce_is_per_service_and_keeps_other_anomalies_visible():
    detector = Detector()
    first = table(frontend={"error_rate": .2})
    assert detector.evaluate(first, now=100)
    assert detector.evaluate(first, now=279) is None
    second = detector.evaluate(table(frontend={"error_rate": .2},
                                     recommendation={"status": "exited"}), now=279)
    assert second["service"] == "recommendation"
    assert {row["service"] for row in second["anomalies"]} == {"frontend", "recommendation"}
    assert detector.evaluate(first, now=280)


def test_restarts_use_observed_delta_and_expire_after_window():
    detector = Detector()
    assert detector.evaluate(table(recommendation={"restarts": 7}), now=0) is None
    assert detector.evaluate(table(recommendation={"restarts": 8}), now=20) is None
    alert = detector.evaluate(table(recommendation={"restarts": 9}), now=40)
    assert alert["signal"] == "restart_count" and alert["observed"] == 2
    assert detector.evaluate(table(recommendation={"restarts": 9}), now=400) is None


def test_oom_and_cpu_capacity_are_observable_without_incident_names():
    unhealthy = table(recommendation={"oom_killed": True, "cpu_limit_nanos": 50_000_000,
                                       "cpu_percent": 4.8})
    found = anomalies(unhealthy)
    assert {row["signal"] for row in found} == {"oom_killed", "cpu_limit_saturation"}


def test_new_cpu_cap_detected_from_observed_baseline_even_with_low_traffic():
    detector = Detector()
    assert detector.evaluate(table(recommendation={"cpu_limit_nanos": 0}), now=0) is None
    result = detector.evaluate(table(recommendation={"cpu_limit_nanos": 50_000_000,
                                                      "cpu_percent": .1}), now=30)
    assert result["signal"] == "resource_limits"
    assert result["details"]["signal"] == "cpu_limit_nanos_reduced"
    assert result["observed"] == 50_000_000 and result["baseline"] == 0


def test_resource_reduction_needs_a_baseline_and_significant_decrease():
    detector = Detector()
    assert detector.evaluate(table(recommendation={"cpu_limit_nanos": 100_000_000}), now=0) is None
    assert detector.evaluate(table(recommendation={"cpu_limit_nanos": 90_000_000}), now=30) is None
    assert detector.evaluate(table(recommendation={"cpu_limit_nanos": 50_000_000}), now=60)
    assert Detector().evaluate(table(recommendation={"cpu_limit_nanos": 50_000_000}), now=0) is None


def test_high_steady_memory_does_not_trigger_without_growth():
    detector = Detector()
    baseline = table(recommendation={"memory_limit_bytes": 100_000_000, "memory_mb": 96})
    assert detector.evaluate(baseline, now=0) is None
    assert detector.evaluate(baseline, now=20) is None
    detector = Detector()
    assert detector.evaluate(table(recommendation={"memory_limit_bytes": 100_000_000,
                                                  "memory_mb": 60}), now=0) is None
    assert detector.evaluate(baseline, now=20)["details"]["signal"] == "memory_ratio"


def test_flood_baseline_excludes_latest_two_minutes():
    end = 1000
    result = {"window": {"to": datetime.fromtimestamp(end, timezone.utc).isoformat()},
              "data": [{"metric": {"service_name": "frontend"}, "values":
                        [[300, 4], [600, 5], [800, 6], [900, 100], [1000, 100]]}]}
    detector = Detector()
    detector.baseline = baseline_from_metrics(result, Thresholds())
    assert detector.baseline == {"frontend": 5}
    alert = detector.evaluate(table(frontend={"rps": 15}), now=end)
    assert alert["signal"] == "traffic" and alert["baseline"] == 5


def test_threshold_configuration_rejects_short_rate_window_and_unknown_keys(tmp_path):
    path = tmp_path / "thresholds.yaml"
    path.write_text("rate_window_s: 60\n", encoding="utf-8")
    with pytest.raises(ValueError, match="120"):
        load_thresholds(path)
    path.write_text("mystery: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown"):
        load_thresholds(path)


class FakeClock:
    now = 0

    def clock(self):
        return self.now

    def sleep(self, duration):
        assert 0 <= duration <= 30
        self.now += duration


def test_clean_verification_waits_full_window_even_if_always_clean():
    clock = FakeClock()
    result = wait_for_clean(sample=lambda **kwargs: table(), clock=clock.clock, sleep=clock.sleep)
    assert result["verified"] and result["elapsed_s"] == 180
    assert [row["elapsed_s"] for row in result["samples"]] == list(range(0, 181, 30))


def test_clean_verification_requires_two_recent_samples():
    clock = FakeClock()
    def sample(**kwargs):
        return table(frontend={"error_rate": .2 if clock.now < 180 else 0})
    result = wait_for_clean(sample=sample, clock=clock.clock, sleep=clock.sleep)
    assert result["verified"] and result["elapsed_s"] == 210


def test_missing_telemetry_never_verifies_recovery():
    clock = FakeClock()
    result = wait_for_clean(sample=lambda **kwargs: {"data": [], "telemetry_available": False},
                            clock=clock.clock, sleep=clock.sleep, timeout_s=180)
    assert not result["verified"]
    with pytest.raises(ValueError, match="180"):
        wait_for_clean(window_s=60)


def test_alert_wait_deadline_and_stop(tmp_path):
    clock = FakeClock()
    class Poller:
        def poll(self, **kwargs):
            return None
    assert wait_for_alert(Poller(), run_dir=tmp_path, clock=clock.clock, sleep=clock.sleep,
                          stop_path=tmp_path / "STOP") is None
    assert clock.now == 90
    (tmp_path / "STOP").touch()
    with pytest.raises(RuntimeError, match="STOP"):
        wait_for_alert(Poller(), run_dir=tmp_path, stop_path=tmp_path / "STOP")


def test_checkpoint_cleanup_runs_after_agent_failure(tmp_path, monkeypatch):
    from scripts import checkpoint2
    records = []
    monkeypatch.setattr(checkpoint2, "ROOT", tmp_path)
    def path(name=None, **kwargs):
        directory = tmp_path / "runs" / (name or "anonymous")
        directory.mkdir(parents=True, exist_ok=True)
        return directory
    monkeypatch.setattr(checkpoint2, "run_path", path)
    def command(arguments, **kwargs):
        records.append(arguments)
        if arguments[:2] == ["faultctl", "inject"]:
            return {"runs": [{"run_id": "operator-run"}]}
        if arguments[0] == "agent.run":
            raise RuntimeError("model unavailable")
        return {}
    monkeypatch.setattr(checkpoint2, "command", command)
    monkeypatch.setattr(checkpoint2, "check_demo_unchanged", lambda: None)
    monkeypatch.setattr(checkpoint2, "require_clean", lambda *args: {"verified": True})
    monkeypatch.setattr(checkpoint2.Detector, "prime_baseline", lambda *args, **kwargs: None)
    monkeypatch.setattr(checkpoint2.Detector, "poll", lambda *args, **kwargs: None)
    monkeypatch.setattr(checkpoint2, "wait_for_alert", lambda *args, **kwargs: {"signal": "error_rate"})
    monkeypatch.setattr(checkpoint2, "write_alert", lambda value, directory: directory / "alert.json")
    assert checkpoint2.main(["example", "--report-id", "unique-example"]) == 1
    assert [args[:2] for args in records].count(["faultctl", "reset"]) == 2
    assert records[-1][:2] == ["faultctl", "reset"]
    agent_args = next(args for args in records if args[0] == "agent.run")
    assert "unique-example" in agent_args


def test_checkpoint_existing_bundle_refused_before_mutation(tmp_path, monkeypatch):
    from scripts import checkpoint2
    monkeypatch.setattr(checkpoint2, "ROOT", tmp_path)
    (tmp_path / "reports" / "existing").mkdir(parents=True)
    monkeypatch.setattr(checkpoint2, "command", lambda *a, **k: pytest.fail("must not mutate"))
    with pytest.raises(SystemExit):
        checkpoint2.main(["example", "--report-id", "existing"])
