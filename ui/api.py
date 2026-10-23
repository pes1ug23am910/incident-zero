"""Shared HTTP contract. Disk reads are confined; mock state never touches the stack."""
from __future__ import annotations

import asyncio
from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).parent / "static"
CLEAR_PHRASE = "I confirm the incident is over"


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None  # A writer may be between truncate and flush; retry next poll.


def lines(path):
    try:
        with path.open(encoding="utf-8-sig") as source:
            for line in source:
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        yield value
                except ValueError:
                    continue
    except OSError:
        return


def inside(path, root):
    return path.resolve().is_relative_to(root.resolve())


def action_of(report):
    return report.get("proposed_action") or next(iter(report.get("proposed_actions") or []), {})


def tier_of(report):
    return (report.get("impact") or {}).get("tier", 3)


def fingerprint(report):
    # Approval binds to the complete reviewed document, not only its identifier.
    return hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()


class Decision(BaseModel):
    operator: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=2000)
    reason: str = Field(default="", max_length=2000)
    confirmation: str = Field(default="", max_length=20)
    revision: str = Field(default="", max_length=64)


class ClearStop(BaseModel):
    phrase: str = Field(max_length=200)


class ControlRoom:
    def __init__(self, reports_dir=None, runs_dir=None, *, real=False, backend=None):
        self.reports = Path(reports_dir or os.getenv("INCIDENT_ZERO_REPORTS_DIR", ROOT / "reports")).resolve()
        self.runs = Path(runs_dir or os.getenv("INCIDENT_ZERO_RUNS_DIR", self.reports.parent / "runs")).resolve()
        self.real = real
        self._backend = backend
        self._native = None
        self.lock = threading.RLock()
        self.stopped = False
        self.decisions = {}
        self.pending_since = {}
        self.journal = deque(maxlen=1000)
        self.events = deque(maxlen=2000)
        self.seen = set()
        self.sequence = 0
        self.epoch = uuid4().hex
        self.health_cache = None
        self.health_time = 0

    def backend(self):
        if not self.real:
            return None
        if self._backend is not None:
            return self._backend
        try:
            return importlib.import_module("action_api.ui_backend")
        except ModuleNotFoundError as exc:
            if exc.name not in ("action_api", "action_api.ui_backend"):
                raise HTTPException(503, "Action backend dependency is unavailable") from exc
        try:
            service_module = importlib.import_module("action_api.service")
        except ModuleNotFoundError as exc:
            if exc.name not in ("action_api", "action_api.service"):
                raise HTTPException(503, "Action backend dependency is unavailable") from exc
            return None
        with self.lock:
            if self._native is None:
                from ui.action_backend import ActionBackend
                self._native = ActionBackend(self, service_module.ActionService)
            return self._native

    def mode(self):
        return "real" if self.backend() is not None else ("mock_fallback" if self.real else "mock")

    def delegate(self, name, **kwargs):
        backend = self.backend()
        function = getattr(backend, name, None)
        if function is None:
            raise HTTPException(503, f"Action backend does not provide {name}; operation refused")
        # The documented hook surface is synchronous; FastAPI runs it off the event loop.
        try:
            return function(**kwargs)
        except HTTPException:
            raise
        except Exception as exc:
            if hasattr(exc, "status") and hasattr(exc, "code"):
                raise HTTPException(exc.status, exc.code) from exc
            raise HTTPException(503, "Action backend unavailable; operation was not confirmed") from exc

    def records(self):
        records = {}
        paths = sorted([*self.reports.glob("*/report.json"), *self.reports.glob("*.json")])
        for path in paths:
            if not inside(path, self.reports):
                continue
            report = read_json(path)
            if not isinstance(report, dict) or not report.get("incident_id") or "status" not in report:
                continue
            identity = str(report["incident_id"])
            if "/" in identity or "\\" in identity or identity in (".", ".."):
                continue
            old = records.get(identity)
            if old is None or str(report.get("diagnosed_at") or "") >= str(old[1].get("diagnosed_at") or ""):
                records[identity] = (path, report)
        return records

    def record(self, identity):
        item = self.records().get(identity)
        if not item:
            raise HTTPException(404, "Incident not found")
        return item

    def detail(self, identity):
        path, original = self.record(identity)
        report = deepcopy(original)
        decision = self.decisions.get((identity, fingerprint(original)))
        if decision:
            report["approval"] = {**report.get("approval", {}), "approved": decision["status"] == "approved",
                                  "approved_by": decision["operator"], "approved_at": decision["decided_at"]}
            report["ui_decision"] = decision
            if decision["status"] == "rejected":
                report["status"] = "needs_human"
        try:
            report["markdown"] = path.with_suffix(".md").read_text(encoding="utf-8-sig") if inside(path.with_suffix(".md"), self.reports) else ""
        except OSError:
            report["markdown"] = ""
        report["revision"] = fingerprint(original)
        report["mode"] = self.mode()
        backend = self.backend()
        if backend is not None and hasattr(backend, "overlay"):
            report = backend.overlay(report)
        return report

    def incidents(self):
        result = []
        for identity in self.records():
            report = self.detail(identity)
            cause = report.get("root_cause") or next(iter(report.get("root_causes") or []), {})
            action = action_of(report)
            result.append({"id": identity, "status": report["status"], "detected_at": report.get("detected_at"),
                           "component": cause.get("component"), "category": cause.get("category"),
                           "confidence": cause.get("confidence"), "tier": tier_of(report),
                           "proposed_action": {"type": action.get("type"), "target": action.get("target")}})
        return sorted(result, key=lambda item: str(item["detected_at"] or ""), reverse=True)

    def snapshot(self, report_path, evidence):
        identifier = evidence["id"]
        path = report_path.parent / "evidence" / (hashlib.sha256(identifier.encode()).hexdigest() + ".json")
        if not inside(path, report_path.parent):
            raise HTTPException(404, "Evidence snapshot unavailable")
        record = read_json(path)
        if not isinstance(record, dict):
            raise HTTPException(404, "Evidence snapshot unavailable; summary is not a resolved payload")
        checksum = record.pop("checksum", None)
        canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if record.get("id") != identifier or record.get("source") != evidence.get("source") or hashlib.sha256(canonical).hexdigest() != checksum:
            raise HTTPException(409, "Evidence snapshot identity or checksum mismatch")
        return {**record, "resolved_from": "bundle_snapshot"}

    def evidence(self, identity, evidence_id):
        path, report = self.record(identity)
        item = next((item for item in report.get("evidence", []) if item.get("id") == evidence_id), None)
        if item is None:
            raise HTTPException(404, "Evidence is not cited by this incident")
        try:
            from tools.resolve import resolve
            # Only a confined run in this repository can be passed to the tools resolver.
            run = report.get("run_id")
            if not run or not inside(ROOT / run, ROOT / "runs"):
                raise ValueError("No local run for live resolution")
            return resolve(evidence_id, run_dir=run)
        except Exception:
            pass
        return self.snapshot(path, item)

    def emit(self, kind, data, key=None):
        with self.lock:
            if key is not None and key in self.seen:
                return
            if key is not None:
                self.seen.add(key)
            self.sequence += 1
            self.events.append({"id": self.sequence, "type": kind, "at": now(), **data})

    def log(self, action, **data):
        self.journal.append({"ts": now(), "action": action, "mode": self.mode(), **data})

    def approvals(self):
        if self.backend() is not None:
            return self.delegate("list_approvals")
        return self.mock_approvals()

    def mock_approvals(self):
        pending, history = [], list(self.decisions.values())
        for identity, (_, report) in self.records().items():
            action = action_of(report)
            revision = fingerprint(report)
            eligible = tier_of(report) in (1, 2) and report["status"] == "diagnosed" and action.get("type") not in (None, "none")
            if not eligible or (identity, revision) in self.decisions:
                continue
            approval = report.get("approval") or {}
            if approval.get("approved") is not None or (report.get("action") or {}).get("executed"):
                continue
            key = (identity, revision)
            with self.lock:
                expiry = self.pending_since.setdefault(key, datetime.now(timezone.utc) + timedelta(minutes=10))
            item = {"id": identity, "report_id": identity, "tier": tier_of(report), "action": action["type"],
                    "target": action.get("target"), "predicted_effect": (action.get("dry_run") or {}).get("predicted_effect") or action.get("reason", "Not supplied"),
                    "expiry": expiry.isoformat(), "revision": revision, "status": "pending"}
            if datetime.now(timezone.utc) >= expiry:
                history.append({**item, "status": "expired"})
            else:
                pending.append(item)
        return {"pending": pending, "history": sorted(history, key=lambda item: item.get("decided_at", ""), reverse=True), "mode": self.mode()}

    def decide(self, identity, decision, approved):
        if not decision.operator.strip():
            raise HTTPException(422, "Operator is required")
        if not approved and not decision.reason.strip():
            raise HTTPException(422, "Rejection reason is required")
        if self.backend() is not None:
            return self.delegate("approve" if approved else "reject", approval_id=identity, **decision.model_dump())
        with self.lock:
            if self.stopped and approved:
                raise HTTPException(423, "STOP is latched")
            _, report = self.record(identity)
            if tier_of(report) not in (1, 2):
                raise HTTPException(403, "Tier 3 requires human escalation; no approval action exists")
            item = next((item for item in self.approvals()["pending"] if item["id"] == identity), None)
            if not item:
                raise HTTPException(409, "Approval is no longer pending or has expired")
            if not decision.revision or decision.revision != item["revision"]:
                raise HTTPException(409, "Report changed or revision missing; review the current report")
            if approved and tier_of(report) == 2 and decision.confirmation != "yes":
                raise HTTPException(422, "Tier 2 requires typing exactly yes")
            result = {**item, **decision.model_dump(), "status": "approved" if approved else "rejected", "decided_at": now(), "mode": self.mode()}
            self.decisions[(identity, item["revision"])] = result
            self.log(result["status"], incident_id=identity, operator=decision.operator, note=decision.note, reason=decision.reason)
            self.emit("approval_decided", {"incident_id": identity, "decision": result})
            return result

    def stop(self):
        if self.backend() is not None:
            return self.delegate("get_stop")
        return {"stopped": self.stopped, "mode": self.mode()}

    def set_stop(self, stopped, phrase=""):
        if not stopped and phrase != CLEAR_PHRASE:
            raise HTTPException(422, "Confirmation phrase does not match")
        if self.backend() is not None:
            return self.delegate("set_stop" if stopped else "clear_stop", **({} if stopped else {"phrase": phrase}))
        with self.lock:
            self.stopped = stopped
            self.log("stop" if stopped else "clear_stop")
            self.emit("stop", self.stop())
        return self.stop()

    def action_log(self, tail):
        if self.backend() is not None:
            return self.delegate("get_log", tail=tail)
        recorded = []
        for path, _ in self.records().values():
            log = path.parent / "action-log.jsonl"
            if inside(log, self.reports):
                recorded.extend({**item, "recorded": True} for item in lines(log))
        return {"lines": (recorded + list(self.journal))[-tail:], "mode": self.mode()}

    def health(self):
        if time.monotonic() - self.health_time < 9 and self.health_cache is not None:
            return self.health_cache
        if self.real:
            try:
                from tools import health_table
                value = health_table()
                rows = [{**row, "cpu": row.get("cpu_percent"), "mem": row.get("memory_mb")} for row in value.get("data", [])]
                self.health_cache = {"rows": rows, "source": "live", "observed_at": now(), "warnings": value.get("warnings", []), "mode": self.mode()}
                self.health_time = time.monotonic()
                return self.health_cache
            except (ImportError, OSError, ValueError):
                pass
        # Mock health is a projection of recorded observations; never invent healthy services.
        rows, observed_at = {}, None
        records = sorted(self.records().values(), key=lambda item: str(item[1].get("detected_at", "")))
        for _, report in records[-1:]:
            observed_at = report.get("detected_at")
            for symptom in report.get("symptoms", []):
                service = symptom.get("service", "unknown")
                row = rows.setdefault(service, {"service": service, "error_rate": None, "p95_ms": None, "rps": None, "restarts": None, "status": "unknown", "cpu": None, "mem": None})
                key = {"latency_p95": "p95_ms"}.get(symptom.get("signal"), symptom.get("signal"))
                if key in ("error_rate", "p95_ms", "rps", "restarts"):
                    try:
                        row[key] = float(symptom["observed"])
                    except (ValueError, TypeError, KeyError):
                        pass
        return {"rows": list(rows.values()), "source": "report_snapshot", "observed_at": observed_at, "warnings": ["Recorded symptoms only; missing values are unknown, not healthy."], "mode": self.mode()}

    def scan(self):
        for identity in self.records():
            report = self.detail(identity)
            base = {"incident_id": identity, "run_id": report.get("run_id"), "recorded": True}
            self.emit("alert_raised", {**base, "alert": report.get("alert")}, (identity, "alert"))
            for step in report.get("investigation", []):
                self.emit("investigation_step", {**base, "step": step}, (identity, "step", fingerprint(step)))
            revision = fingerprint({key: value for key, value in report.items() if key != "markdown"})
            self.emit("report_ready", {**base, "status": report["status"]}, (identity, "report", revision))
            if (report.get("action") or {}).get("executed"):
                self.emit("action_executed", {**base, "action": report["action"]}, (identity, "action", fingerprint(report["action"])))
            if (report.get("verification") or {}).get("checked_at"):
                self.emit("verification_result", {**base, "verification": report["verification"]}, (identity, "verification", fingerprint(report["verification"])))
        # Read only the detector and investigation journals, never operator/injection state.
        for directory in sorted(self.runs.glob("*"))[-100:]:
            if not directory.is_dir() or not inside(directory, self.runs):
                continue
            run_id = "runs/" + directory.name
            alert_path = directory / "alert.json"
            alert = read_json(alert_path) if inside(alert_path, self.runs) else None
            if isinstance(alert, dict):
                self.emit("alert_raised", {"run_id": run_id, "alert": alert, "recorded": False}, (run_id, "alert", fingerprint(alert)))
            journal = directory / "tools.jsonl"
            if not inside(journal, self.runs):
                continue
            for step in lines(journal):
                result = step.get("result") or {}
                compact = {"step": step.get("step"), "tool": step.get("tool"), "query": json.dumps(step.get("arguments", {})),
                           "why": step.get("why"), "finding": result.get("error") or "Tool result recorded", "evidence_ids": result.get("evidence_ids", [])}
                self.emit("investigation_step", {"run_id": run_id, "step": compact, "recorded": False}, (run_id, "step", fingerprint(compact)))
        for item in self.approvals()["pending"]:
            self.emit("approval_requested", {"incident_id": item.get("report_id", item["id"]), "approval": item}, ("approval", item["id"], item.get("revision"), item.get("expiry")))


def make_router(room):
    router = APIRouter()

    @router.get("/", include_in_schema=False)
    @router.get("/index.html", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    @router.get("/static/{filename}", include_in_schema=False)
    def asset(filename: str):
        if filename not in ("app.js", "app.css"):
            raise HTTPException(404)
        return FileResponse(STATIC / filename, headers={"Cache-Control": "no-cache"})

    @router.get("/api/incidents")
    def incidents():
        return room.incidents()

    @router.get("/api/incidents/{identity}")
    def incident(identity: str):
        return room.detail(identity)

    @router.get("/api/incidents/{identity}/evidence/{evidence_id:path}")
    def evidence(identity: str, evidence_id: str):
        return room.evidence(identity, evidence_id)

    @router.get("/api/health")
    def health():
        return room.health()

    @router.get("/api/approvals")
    def approvals():
        return room.approvals()

    @router.post("/api/approvals/{identity}/approve")
    def approve(identity: str, decision: Decision):
        return room.decide(identity, decision, True)

    @router.post("/api/approvals/{identity}/reject")
    def reject(identity: str, decision: Decision):
        return room.decide(identity, decision, False)

    @router.get("/api/stop")
    def stop():
        return room.stop()

    @router.post("/api/stop")
    def latch():
        return room.set_stop(True)

    @router.delete("/api/stop")
    def clear(body: ClearStop = Body(...)):
        return room.set_stop(False, body.phrase)

    @router.get("/api/log")
    def log(tail: int = Query(default=50, ge=1, le=500)):
        return room.action_log(tail)

    @router.get("/api/events")
    async def events(request: Request, after: int = Query(default=0, ge=0), wait: float = Query(default=0, ge=0, le=20), epoch: str = ""):
        deadline = time.monotonic() + wait
        while True:
            await run_in_threadpool(room.scan)
            with room.lock:
                reset = bool(epoch and epoch != room.epoch) or after > room.sequence or bool(room.events and after < room.events[0]["id"] - 1)
                found = [item for item in room.events if item["id"] > (0 if reset else after)]
                response = {"events": found, "cursor": room.sequence, "epoch": room.epoch, "reset": reset, "mode": room.mode()}
            if found or time.monotonic() >= deadline or await request.is_disconnected():
                return response
            await asyncio.sleep(1)

    return router
