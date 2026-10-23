"""Recorded idle telemetry plus explicit synthetic perturbations; no live I/O."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from detect.core import Detector, baseline_from_metrics
from detect.recovery import clean_sample

FIXTURE = Path(__file__).parent / "fixtures/clean_stack_oct23.json"


@pytest.fixture
def idle():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_recorded_idle_stack_has_zero_errors_and_no_alert(idle):
    assert idle["read_only"] and idle["provenance"]["stack_changed"] is False
    detector = Detector()
    detector.baseline = baseline_from_metrics(idle["baseline_metrics"], detector.thresholds)
    assert idle["detector_alert"] is None
    assert detector.evaluate(idle["health"], debounce=False) is None
    traffic = [r for r in idle["health"]["data"] if (r.get("rps") or 0) > 0]
    assert len(traffic) >= 10
    assert all(r["error_rate"] == 0 for r in traffic)
    assert clean_sample(idle["health"])[0]


@pytest.mark.xfail(strict=True, reason="fold: Addendum 5 item 1 exclude load-generator CLIENT spans")
def test_slow_synthetic_client_is_not_an_application_latency_alert(idle):
    health = deepcopy(idle["health"])
    row = next(r for r in health["data"] if r["service"] == "load-generator")
    row.update(p95_ms=4000, error_rate=0.25, span_kind="SPAN_KIND_CLIENT")
    assert Detector().evaluate(health, debounce=False) is None


@pytest.mark.xfail(strict=True, reason="fold: Addendum 4 item 2 dedicated telemetry_outage alert")
def test_telemetry_outage_cannot_be_silent(idle):
    health = deepcopy(idle["health"])
    health.update(telemetry_available=False, backend_availability={"prometheus": False, "jaeger": False})
    for row in health["data"]:
        row.update(rps=None, error_rate=None, p95_ms=None)
    alert = Detector().evaluate(health, debounce=False)
    assert alert and alert["signal"] == "telemetry_outage"


@pytest.mark.xfail(strict=True, reason="fold: Addendum 4 item 3 stopped load generator is non-incident traffic state")
def test_stopped_load_generator_is_not_an_app_incident(idle):
    health = deepcopy(idle["health"])
    for row in health["data"]:
        row.update(rps=0, error_rate=None, p95_ms=None)
        if row["service"] == "load-generator":
            row["status"] = "exited"
    result = Detector().evaluate(health, debounce=False)
    assert result and result.get("status") == "no_incident"
    assert result.get("traffic_state") == "load_generator_stopped"


def test_stale_good_metrics_do_not_hide_a_stopped_container(idle):
    health = deepcopy(idle["health"])
    next(r for r in health["data"] if r["service"] == "payment")["status"] = "exited"
    alert = Detector().evaluate(health, debounce=False)
    assert any(r["service"] == "payment" and r["signal"] == "container_status" for r in alert["anomalies"])
    assert not clean_sample(health)[0]


@pytest.mark.xfail(strict=True, reason="fold: Addendum 5 item 1 SERVER-only latency query")
def test_latency_query_excludes_synthetic_client_spans():
    from tools.queries import build_queries
    query = build_queries()["p95_latency_by_service"]
    assert 'span_kind="SPAN_KIND_SERVER"' in query
