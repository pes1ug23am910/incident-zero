"""Adapter to the hands ActionService. Imported lazily; never bypasses its gates."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import threading

from fastapi import HTTPException

from ui.api import action_of, fingerprint, lines, now, tier_of


class ActionBackend:
    def __init__(self, room, service_factory, response_driver=None):
        self.room = room
        self.factory = service_factory
        self._service = None
        self._response_driver = response_driver
        self.lock = threading.RLock()
        self.previews = {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="control-room-response")

    @property
    def response_driver(self):
        if self._response_driver is None:
            from agent import respond
            self._response_driver = respond
        return self._response_driver

    def pending(self, report):
        return self.response_driver.pending_checkpoint(report, root=self.service.root, service=self.service)

    @property
    def service(self):
        # STOP must never wait behind slow preview or approval telemetry reads.
        if self._service is not None:
            return self._service
        with self.lock:
            if self._service is None:
                self._service = self.factory()
            return self._service

    def get_stop(self):
        return {"stopped": self.service.stop_path.exists(), "mode": "real"}

    def set_stop(self):
        result = {**self.service.stop("Control Room operator"), "mode": "real"}
        self.room.emit("stop", result)
        return result

    def clear_stop(self, phrase):
        result = {**self.service.clear_stop(phrase, "Control Room operator"), "mode": "real"}
        self.room.emit("stop", result)
        return result

    def get_log(self, tail):
        return {"lines": list(lines(self.service.log_path))[-tail:], "mode": "real"}

    def history(self):
        return [entry["ui_decision"] for entry in lines(self.service.log_path) if isinstance(entry.get("ui_decision"), dict)]

    def list_approvals(self):
        with self.lock:
            history = self.history()
            decided = {(item["id"], item.get("report_revision", item["revision"])) for item in history}
            attempts = self.service.attempts()
            pending = []
            stopped = self.get_stop()["stopped"]
            for identity, (_, report) in self.room.records().items():
                if tier_of(report) not in (1, 2) or report["status"] != "diagnosed" or (report.get("approval") or {}).get("approved") is not None:
                    continue
                try:
                    state = self.pending(report)
                except ValueError:
                    # Historical reports without a matching paused checkpoint
                    # remain inspectable but can never authorize execution.
                    continue
                revision = fingerprint(report)
                canonical = state['report']
                actions = canonical.get("proposed_actions") or [action_of(canonical)]
                for index, action in enumerate(actions):
                    if index != state.get('action_index', 0):
                        continue
                    if action.get("type") in (None, "none"):
                        continue
                    approval_id = identity if len(actions) == 1 else f"{identity}~{index + 1}"
                    if (approval_id, revision) in decided:
                        continue
                    # Durable service attempts block duplicate approvals, including after a restart.
                    if any(item.get("report_id") == report.get("run_id") and item.get("plan", {}).get("target") == action.get("target") for item in attempts):
                        continue
                    key = (approval_id, revision)
                    cached = self.previews.get(key)
                    if cached is None and not stopped:
                        try:
                            preview = self.service.dry_run(action, canonical)
                            cached = {"preview": preview, "expiry": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}
                            self.previews[key] = cached
                        except Exception as exc:
                            if not hasattr(exc, "code"):
                                raise
                            history.append({"id": approval_id, "report_id": identity, "revision": revision, "status": "blocked", "reason": exc.code})
                            continue
                    if cached is None:
                        continue
                    if datetime.fromisoformat(cached["expiry"]) <= datetime.now(timezone.utc):
                        history.append({"id": approval_id, "report_id": identity, "revision": revision, "status": "expired", "reason": "Reload the response session to request a fresh dry run."})
                        continue
                    preview = cached["preview"]
                    pending.append({"id": approval_id, "report_id": identity, "tier": preview["impact"]["tier"],
                                    "action": preview["plan"]["action"], "target": preview["plan"]["target"],
                                    "predicted_effect": preview["predicted_effect"], "expiry": cached["expiry"],
                                    "revision": fingerprint({"report": revision, "preview": preview}),
                                    "report_revision": revision, "status": "pending", "preview": preview, "action_index": index})
            return {"pending": pending, "history": list(reversed(history)), "mode": "real"}

    def approve(self, **decision):
        return self.decide(True, **decision)

    def reject(self, **decision):
        return self.decide(False, **decision)

    def decide(self, approved, approval_id, operator, note, reason, confirmation, revision):
        with self.lock:
            if approved and self.get_stop()["stopped"]:
                raise HTTPException(423, "STOP is latched")
            item = next((item for item in self.list_approvals()["pending"] if item["id"] == approval_id), None)
            if item is None or item["revision"] != revision:
                raise HTTPException(409, "Approval expired, already decided, blocked, or report changed")
            if not operator.strip() or (not approved and not reason.strip()):
                raise HTTPException(422, "Operator and rejection reason are required")
            if approved and item["tier"] == 2 and confirmation != "yes":
                raise HTTPException(422, "Tier 2 requires typing exactly yes")
            if item["tier"] not in (1, 2):
                raise HTTPException(403, "Tier 3 cannot be approved")
            path, report = self.room.record(item["report_id"])
            if fingerprint(report) != item["report_revision"]:
                raise HTTPException(409, "Report changed; review the current report")
            state = self.pending(report)
            if state.get('action_index', 0) != item['action_index']:
                raise HTTPException(409, "This action has already been decided")
            canonical = state['report']
            result = {key: value for key, value in item.items() if key != "preview"}
            result.update(operator=operator, note=note, reason=reason, status="approved" if approved else "rejected", decided_at=now(), mode="real")
            if not approved:
                self.service.log("approval_rejected", report_id=report["run_id"], actor=operator, ui_decision=result)
                answer = {'decision': 'reject', 'approved_by': operator, 'requested_at': now()}
            else:
                actions = canonical.get("proposed_actions") or [action_of(canonical)]
                action = actions[item["action_index"]]
                # This answer originates in the explicit HTTP button/typed confirmation.
                # The native gate still rechecks report, world state, tier and STOP.
                try:
                    answer = self.service.approve(action, canonical, item["preview"], operator,
                                                  input_fn=lambda _: "y" if item["tier"] == 1 else confirmation,
                                                  output=lambda _: None)
                except Exception as exc:
                    if getattr(exc, "code", "") in ("WORLD_OR_PLAN_CHANGED", "WORLD_STATE_CHANGED"):
                        self.previews.pop((approval_id, item["report_revision"]), None)
                    raise
                if answer.get("decision") != "approve":
                    raise HTTPException(409, "Action service did not approve this plan")
                self.service.log("ui_approval", report_id=report["run_id"], actor=operator, ui_decision=result)
            self.pool.submit(self.continue_response, deepcopy(report), answer, path, operator)
            self.room.emit("approval_decided", {"incident_id": item["report_id"], "decision": result})
            return result

    def continue_response(self, report, answer, path, operator):
        identity = report["incident_id"]
        try:
            final = self.response_driver.resume(report, answer, root=self.service.root, service=self.service,
                                                operator=operator, single_step=True, report_path=path)
            if final.get('action', {}).get('executed'):
                self.room.emit("action_executed", {"incident_id": identity, "action": final['action']})
            if final.get('verification', {}).get('checked_at'):
                self.room.emit("verification_result", {"incident_id": identity, "verification": final['verification']})
        except Exception as exc:
            code = getattr(exc, "code", "RESPONSE_REQUIRES_OPERATOR_REVIEW")
            self.service.log("ui_response_blocked", report_id=report["run_id"], reason=code)
            self.room.emit("response_blocked", {"incident_id": identity, "reason": code})

    def overlay(self, report):
        # The source report remains immutable. Service attempts and audit are durable.
        history = [item for item in self.history() if item.get("report_id") == report["incident_id"] and item.get("report_revision", item.get("revision")) == report["revision"]]
        if history:
            decision = history[-1]
            approved = decision["status"] == "approved"
            report["ui_decision"] = decision
            report["approval"] = {**report.get("approval", {}), "approved": approved, "approved_by": decision["operator"], "approved_at": decision["decided_at"] if approved else None}
            if not approved:
                report["status"] = "needs_human"
        attempts = [item for item in self.service.attempts() if item.get("report_id") == report.get("run_id")]
        if attempts:
            latest = max(attempts, key=lambda item: item.get("created", 0))
            if latest.get("result"):
                report["action"] = {key: value for key, value in latest["result"].items() if key != "idempotency_key"}
            if latest.get("verification"):
                report["verification"] = latest["verification"]
            expected = len(report.get("proposed_actions") or [action_of(report)])
            recovered = len(attempts) == expected and all(item.get("verification", {}).get("recovered") for item in attempts)
            if recovered:
                report["status"] = "fixed"
                report["resolved_at"] = latest["verification"].get("checked_at")
            elif latest.get("verification", {}).get("rolled_back"):
                report["status"] = "rolled_back"
            elif latest.get("phase") == "aborted":
                report["status"] = "aborted"
            elif latest.get("phase") in ("failed", "uncertain"):
                report["status"] = "needs_human"
        report["ui_source"] = "Original report with durable Action API decisions and verification overlaid"
        return report
