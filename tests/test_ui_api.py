"""Control Room contracts; all mutations use mock or injected fake service state."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import time
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from ui.api import CLEAR_PHRASE, ControlRoom, fingerprint, make_router
from ui.mock_api import create_app


@pytest.fixture(autouse=True)
def no_live_resolution(monkeypatch):
    def unavailable(*args, **kwargs):
        raise ValueError("Test: live resolver intentionally disconnected")
    monkeypatch.setattr(importlib.import_module("tools.resolve"), "resolve", unavailable)


def sample(identity="test-incident", tier=2):
    action = {"type": "restart_service", "target": "cart", "parameters": {"service": "cart"},
              "reason": "Restore the stopped process", "risk": "Brief interruption", "dry_run": {"performed": True, "predicted_effect": "Cart serves requests"}}
    return {"schema_version": "1.0", "incident_id": identity, "run_id": "runs/fixture", "detected_at": "2026-10-23T10:00:00+00:00",
            "diagnosed_at": "2026-10-23T10:01:00+00:00", "status": "diagnosed" if tier != 3 else "needs_human",
            "alert": {"service": "cart", "signal": "error_rate", "observed": .1, "threshold": .05, "window_s": 120},
            "root_cause": {"component": "cart", "category": "container_down", "confidence": .9, "cause": "Container stopped"},
            "impact": {"tier": tier, "rationale": "Review availability impact"},
            "investigation": [{"step": 1, "tool": "get_container_health", "why": "Check process", "finding": "Stopped", "query": "cart"}],
            "symptoms": [{"service": "cart", "signal": "error_rate", "observed": "0.1"}],
            "evidence": [{"id": "span:0123456789abcdef/0123456789abcdef", "source": "jaeger", "summary": "cart error", "raw_ref": "recorded"}],
            "proposed_action": action if tier != 3 else None, "proposed_actions": [action] if tier != 3 else [],
            "approval": {"approved": None, "required": True}, "action": {"executed": False},
            "verification": {"recovered": None, "before": None, "after": None, "checked_at": None}}


def write_report(root, report):
    bundle = root / report["incident_id"]
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (bundle / "report.md").write_text("# Recorded incident\n", encoding="utf-8")
    if report.get("evidence"):
        evidence = report["evidence"][0]
        record = {"version": 1, "id": evidence["id"], "source": evidence["source"], "data": {"operationName": "cart", "tags": [{"key": "error", "value": True}]}, "captured_at": report["detected_at"]}
        record["checksum"] = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        folder = bundle / "evidence"
        folder.mkdir(exist_ok=True)
        (folder / (hashlib.sha256(evidence["id"].encode()).hexdigest() + ".json")).write_text(json.dumps(record), encoding="utf-8")
    return bundle


@pytest.fixture
def client(tmp_path):
    reports = tmp_path / "reports"
    write_report(reports, sample())
    app = create_app(reports, tmp_path / "runs")
    with TestClient(app) as test_client:
        yield test_client


def body(client, identity="test-incident", **extra):
    return {"operator": "Local operator", "revision": client.get(f"/api/incidents/{identity}").json()["revision"], **extra}


def test_list_detail_and_resolved_evidence(client):
    response = client.get("/api/incidents")
    assert response.status_code == 200
    incident = response.json()[0]
    assert set(incident) == {"id", "status", "detected_at", "component", "category", "confidence", "tier", "proposed_action"}
    report = client.get("/api/incidents/test-incident").json()
    assert report["markdown"].startswith("# Recorded")
    identifier = report["evidence"][0]["id"]
    response = client.get("/api/incidents/test-incident/evidence/" + quote(identifier, safe=""))
    assert response.status_code == 200
    assert response.json()["resolved_from"] == "bundle_snapshot"
    assert response.json()["data"]["operationName"] == "cart"
    assert client.get("/api/incidents/test-incident/evidence/unknown").status_code == 404
    assert client.get("/api/incidents/missing").status_code == 404


def test_corrupt_snapshot_is_not_presented_as_evidence(client):
    room = client.app.state.control_room
    path = next(room.reports.glob("*/evidence/*.json"))
    value = json.loads(path.read_text())
    value["data"] = {"fabricated": True}
    path.write_text(json.dumps(value))
    identifier = sample()["evidence"][0]["id"]
    assert client.get("/api/incidents/test-incident/evidence/" + quote(identifier, safe="")).status_code == 409


def test_tier_two_decision_requires_yes_and_only_records_approval(client):
    url = "/api/approvals/test-incident/approve"
    assert client.post(url, json=body(client)).status_code == 422
    before = (client.app.state.control_room.reports / "test-incident/report.json").read_bytes()
    response = client.post(url, json=body(client, confirmation="yes", note="Reviewed sources"))
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert client.post(url, json=body(client, confirmation="yes")).status_code == 409
    queue = client.get("/api/approvals").json()
    assert not queue["pending"] and queue["history"][0]["status"] == "approved"
    report = client.get("/api/incidents/test-incident").json()
    assert report["approval"]["approved"] is True
    assert report["action"]["executed"] is False and report["verification"]["recovered"] is None
    assert before == (client.app.state.control_room.reports / "test-incident/report.json").read_bytes()
    assert "action_executed" not in {item["type"] for item in client.get("/api/events").json()["events"]}


def test_tier_one_and_rejection(client):
    write_report(client.app.state.control_room.reports, sample("quick", tier=1))
    assert client.post("/api/approvals/quick/approve", json=body(client, "quick")).status_code == 200
    assert client.post("/api/approvals/test-incident/reject", json=body(client)).status_code == 422
    response = client.post("/api/approvals/test-incident/reject", json=body(client, reason="Need more evidence"))
    assert response.status_code == 200
    assert client.get("/api/incidents/test-incident").json()["status"] == "needs_human"


def test_stop_latch_phrase_and_resume(client):
    room = client.app.state.control_room
    assert client.get("/api/stop").json()["stopped"] is False
    assert client.post("/api/stop").json()["stopped"] is True
    assert client.post("/api/approvals/test-incident/approve", json=body(client, confirmation="yes")).status_code == 423
    assert client.request("DELETE", "/api/stop", json={"phrase": "wrong"}).status_code == 422
    assert client.get("/api/stop").json()["stopped"] is True
    assert client.request("DELETE", "/api/stop", json={"phrase": CLEAR_PHRASE}).json()["stopped"] is False
    assert client.post("/api/approvals/test-incident/approve", json=body(client, confirmation="yes")).status_code == 200
    assert not (room.reports.parent / "STOP").exists()
    assert len(client.get("/api/log?tail=2").json()["lines"]) == 2
    assert client.get("/api/log?tail=0").status_code == 422


def test_stale_revision_expiry_and_blank_operator(client):
    stale = body(client, confirmation="yes")
    report = sample()
    report["root_cause"]["cause"] = "Fresh diagnosis"
    write_report(client.app.state.control_room.reports, report)
    assert client.post("/api/approvals/test-incident/approve", json=stale).status_code == 409
    assert client.post("/api/approvals/test-incident/approve", json=body(client, operator=" ", confirmation="yes")).status_code == 422
    assert client.post("/api/approvals/test-incident/approve", json={"operator": "Local operator", "confirmation": "yes"}).status_code == 409
    room = client.app.state.control_room
    room.pending_since[("test-incident", fingerprint(report))] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert client.post("/api/approvals/test-incident/approve", json=body(client, confirmation="yes")).status_code == 409
    assert client.get("/api/approvals").json()["history"][0]["status"] == "expired"


def test_tier_three_has_no_approve_action(client):
    report = sample("escalated", tier=3)
    # Even a malformed producer attaching an action cannot bypass the tier gate.
    report["proposed_action"] = sample()["proposed_action"]
    write_report(client.app.state.control_room.reports, report)
    assert "escalated" not in {item["id"] for item in client.get("/api/approvals").json()["pending"]}
    assert client.post("/api/approvals/escalated/approve", json=body(client, "escalated", confirmation="yes")).status_code == 403


def test_health_unknown_values_and_partial_report(client):
    health = client.get("/api/health").json()
    assert health["source"] == "report_snapshot"
    assert health["rows"][0]["error_rate"] == .1
    assert health["rows"][0]["cpu"] is None
    assert health["rows"][0]["status"] == "unknown"
    path = client.app.state.control_room.reports / "partial"
    path.mkdir()
    (path / "report.json").write_text('{"incident_id":')
    assert len(client.get("/api/incidents").json()) == 1


def test_event_cursor_new_bundle_and_live_steps(client):
    first = client.get("/api/events").json()
    kinds = {event["type"] for event in first["events"]}
    assert {"alert_raised", "investigation_step", "report_ready", "approval_requested"} <= kinds
    second = client.get(f'/api/events?after={first["cursor"]}&epoch={first["epoch"]}').json()
    assert not second["events"]
    room = client.app.state.control_room
    run = room.runs / "active"
    run.mkdir(parents=True)
    (run / "tools.jsonl").write_text(json.dumps({"step": 2, "tool": "get_traces", "why": "Trace dependency errors", "arguments": {"service": "cart"}, "result": {"evidence_ids": []}}) + "\n")
    live = client.get(f'/api/events?after={first["cursor"]}').json()
    assert any(event["type"] == "investigation_step" and event["run_id"] == "runs/active" for event in live["events"])
    assert client.get('/api/events?epoch=old-server').json()["reset"] is True
    write_report(room.reports, sample("new", tier=3))
    assert any(event.get("incident_id") == "new" for event in client.get(f'/api/events?after={live["cursor"]}').json()["events"])


def test_index_js_and_five_views_without_browser(client):
    html = client.get("/")
    js = client.get("/static/app.js")
    assert html.status_code == js.status_code == client.get("/static/app.css").status_code == 200
    for view in ("war-room", "incidents", "services", "approvals", "safety"):
        assert f'id="{view}"' in html.text
        assert f'data-view="{view}"' in html.text
    assert 'src="/static/app.js"' in html.text
    assert "function approvalPanel" in js.text and 'if (level === 3)' in js.text
    assert "https://" not in html.text and "http://" not in html.text
    assert client.get("/static/unknown.js").status_code == 404


def test_real_router_falls_back_without_hands_modules(tmp_path, monkeypatch):
    original = importlib.import_module
    def missing(name, *args, **kwargs):
        if name in ("action_api.ui_backend", "action_api.service"):
            raise ModuleNotFoundError(name=name)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(importlib, "import_module", missing)
    room = ControlRoom(tmp_path, real=True)
    app = FastAPI()
    app.include_router(make_router(room))
    client = TestClient(app)
    assert client.get("/api/stop").json() == {"stopped": False, "mode": "mock_fallback"}
    assert client.post("/api/stop").json()["stopped"] is True
    assert not (tmp_path / "STOP").exists()


def test_present_backend_failure_never_turns_into_mock_success(tmp_path):
    class Broken:
        def set_stop(self):
            raise RuntimeError("Backend disconnected")
    room = ControlRoom(tmp_path, real=True, backend=Broken())
    app = FastAPI()
    app.include_router(make_router(room))
    assert TestClient(app).post("/api/stop").status_code == 503
    assert room.stopped is False


def test_disk_acceptance_bundle():
    root = Path(__file__).resolve().parents[1]
    configured = os.getenv("INCIDENT_ZERO_TEST_REPORTS_DIR")
    candidates = ([Path(configured)] if configured else []) + [root / "reports", root.parent / "incident-zero/reports"]
    reports = next((path for path in candidates if (path / "payment-failure-r1/report.json").is_file()), None)
    if reports is None:
        pytest.skip("Acceptance bundle is runtime data; set INCIDENT_ZERO_TEST_REPORTS_DIR")
    with TestClient(create_app(reports)) as client:
        report = client.get("/api/incidents/payment-failure-r1").json()
        assert report["impact"]["tier"] == 3 and report["markdown"]
        assert not any(item["report_id"] == "payment-failure-r1" for item in client.get("/api/approvals").json()["pending"])
        for item in report["evidence"]:
            response = client.get("/api/incidents/payment-failure-r1/evidence/" + quote(item["id"], safe=""))
            assert response.status_code == 200, response.text
            assert response.json()["id"] == item["id"]


class FakeService:
    """No executor imports and no network; only a temporary-directory journal."""
    def __init__(self, root):
        self.stop_path = root / "STOP"
        self.log_path = root / "log.jsonl"
        self.executions = []
        self.answers = []

    def log(self, event, **fields):
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": event, **fields}) + "\n")

    def attempts(self):
        return deepcopy(self.executions)

    def dry_run(self, action, report):
        return {"impact": report["impact"], "plan": {"action": action["type"], "target": action["target"], "parameters": action["parameters"]}, "predicted_effect": "Restore service", "reason_codes": ["REVIEW"]}

    def approve(self, action, report, preview, operator, input_fn, output):
        answer = input_fn("Approve?")
        self.answers.append(answer)
        assert not self.stop_path.exists()
        return {"decision": "approve", "token": "private-test-token"}

    def execute(self, action, report, token, key):
        assert token == "private-test-token"
        result = {"executed": True, "started_at": "2026-10-23T10:02:00Z", "finished_at": "2026-10-23T10:02:01Z", "action_log_ref": "action_log:1"}
        self.executions.append({"report_id": report["run_id"], "created": 1, "phase": "verifying", "result": result, "plan": {"target": action["target"]}})
        return result

    def verify(self, key):
        verification = {"checked_at": "2026-10-23T10:05:00Z", "before": .1, "after": .001, "recovered": True, "rolled_back": False}
        self.executions[-1].update(verification=verification, phase="done")
        return verification

    def stop(self, operator):
        self.stop_path.write_text(operator)
        return {"stopped": True}

    def clear_stop(self, phrase, operator):
        assert phrase == CLEAR_PHRASE
        self.stop_path.unlink(missing_ok=True)
        return {"stopped": False}


def test_native_adapter_approval_execution_verification_and_no_token_leak(tmp_path):
    from ui.action_backend import ActionBackend
    report = sample()
    write_report(tmp_path / "reports", report)
    service = FakeService(tmp_path)
    room = ControlRoom(tmp_path / "reports", real=True)
    backend = ActionBackend(room, lambda: service)
    room._backend = backend
    app = FastAPI()
    app.include_router(make_router(room))
    client = TestClient(app)
    pending = client.get("/api/approvals").json()["pending"][0]
    assert pending["preview"]["plan"]["target"] == "cart"
    url = "/api/approvals/test-incident/approve"
    decision = {"operator": "Reviewer", "revision": pending["revision"]}
    assert client.post(url, json=decision).status_code == 422
    response = client.post(url, json={**decision, "confirmation": "yes"})
    assert response.status_code == 200
    assert "private-test-token" not in response.text
    backend.pool.shutdown(wait=True)
    assert service.answers == ["yes"]
    updated = client.get("/api/incidents/test-incident").json()
    assert updated["status"] == "fixed" and updated["verification"]["recovered"]
    assert not client.get("/api/approvals").json()["pending"]
    assert client.post(url, json={**decision, "confirmation": "yes"}).status_code == 409
    assert client.post("/api/stop").json()["stopped"] is True
    assert client.request("DELETE", "/api/stop", json={"phrase": CLEAR_PHRASE}).json()["stopped"] is False
    assert json.loads((tmp_path / "reports/test-incident/report.json").read_text())["action"]["executed"] is False
    assert not any("private-test-token" in client.get(path).text for path in ("/api/incidents", "/api/approvals", "/api/log", "/api/events"))
