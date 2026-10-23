"""Durable approval, idempotency, exclusion, audit and rollback boundary.

State stores secrets and rollback material under ignored runs/. Audit exports
contain only token fingerprints and service names. An interrupted mutation is
never retried automatically: its persisted intent requires operator review.
"""
from copy import deepcopy
from functools import wraps
import json
from pathlib import Path
import secrets
import sqlite3
import time

from agent.policy import POLICY, SERVICES, causes_for, select_action
from agent.risk import assess
from .approval import prompt
from .safety import Blocked, digest, exclusive, now
from .verify import Verifier

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = {"restart_service": {"service": "known service"},
             "toggle_flag": {"service": "known service"},
             "throttle_load": {"users": "integer 1..100", "spawn_rate": "number 0.1..10"}}


def audited(fn):
    @wraps(fn)
    def call(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Blocked as exc:
            report = next((arg for arg in args if isinstance(arg, dict) and 'run_id' in arg), {})
            self.log(fn.__name__, report_id=report.get('run_id'), result=exc.payload())
            raise
    return call


def canonical_plan(value):
    action = value.get("action", value.get("type"))
    if action not in ALLOWLIST:
        raise Blocked("NOT_AVAILABLE_ON_COMPOSE" if action == "scale_service" else "FORBIDDEN_OPERATION")
    target, parameters = value.get("target"), value.get("parameters", {})
    if not isinstance(target, str) or target not in SERVICES:
        raise Blocked("INVALID_TARGET")
    if not isinstance(parameters, dict):
        raise Blocked("INVALID_PARAMETERS")
    if action in ("toggle_flag", "restart_service"):
        if parameters != {"service": target}:
            raise Blocked("INVALID_PARAMETERS")
    else:
        if target != "load-generator" or set(parameters) != {"users", "spawn_rate"}:
            raise Blocked("INVALID_PARAMETERS")
        users, spawn = parameters["users"], parameters["spawn_rate"]
        if type(users) is not int or not 1 <= users <= 100 or type(spawn) not in (float, int) or not .1 <= spawn <= 10:
            raise Blocked("INVALID_PARAMETERS")
    return {"action": action, "target": target, "parameters": parameters}


class ActionService:
    def __init__(self, root=ROOT, executor=None, verifier=None, clock=time.time, policy=None):
        self.root, self.clock = Path(root), clock
        self.policy = deepcopy(policy or POLICY)
        self.private = self.root / "runs" / "action-api"
        self.private.mkdir(parents=True, exist_ok=True)
        self.stop_path = self.root / "STOP"
        from .executors import LocalExecutor
        self.executor = executor or LocalExecutor(self.stop_path)
        self.verifier = verifier or Verifier(window_s=self.policy['verification_window_s'])
        self.db = self.private / "state.sqlite"
        self.log_path = self.root / "action_api" / "log.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    def connect(self):
        return sqlite3.connect(self.db, timeout=10)

    def get(self, table, key):
        with self.connect() as db:
            row = db.execute(f"SELECT value FROM {table} WHERE id=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, table, key, value):
        with self.connect() as db:
            db.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?)", (key, json.dumps(value)))

    def attempts(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT value FROM attempts")]

    def log(self, event, **fields):
        with exclusive(self.private / "audit.lock"):
            number = sum(1 for _ in self.log_path.open(encoding="utf-8")) + 1 if self.log_path.exists() else 1
            record = {"ts": now(), "event": event, **fields}
            with self.log_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, allow_nan=False) + "\n")
            return f"action_log:{number}"

    def check_stop(self):
        if self.stop_path.exists():
            raise Blocked("STOP_LATCHED", 423)

    def bind_alert(self, report, alert):
        # The checkpoint retains the full detector alert, including simultaneous
        # signals omitted by the report's compact presentation schema.
        alert = alert or report['alert']
        for key in ('signal', 'service', 'threshold'):
            if alert.get(key) != report['alert'].get(key):
                raise Blocked('ALERT_MISMATCH', 409)
        previous = self.get('alerts', report['run_id'])
        if previous is not None and previous != alert:
            raise Blocked('ALERT_CHANGED', 409)
        self.put('alerts', report['run_id'], alert)

    def verification_alert(self, report):
        return self.get('alerts', report['run_id']) or report['alert']

    def world(self, plan):
        try:
            return self.executor.snapshot(plan)
        except Blocked:
            raise
        except Exception as exc:
            raise Blocked('WORLD_STATE_UNAVAILABLE', 409) from exc

    def constraints(self, plan, report):
        self.check_stop()
        impact = assess(report)
        if impact["tier"] == 3:
            raise Blocked("TIER_3_ESCALATE", 403)
        if report.get("status") in ("no_incident", "aborted"):
            raise Blocked("NO_ACTIONABLE_INCIDENT")
        candidates = [canonical_plan(action) for cause in causes_for(report)
                      if (action := select_action(cause)) is not None]
        if plan not in candidates:
            raise Blocked("PLAN_NOT_DERIVED_FROM_CAUSE")
        # Two independent source types identifying the diagnosed cause, not two
        # rows of the same backend. A reviewer is optional, never self-judgment.
        cited = {i for cause in causes_for(report) for i in cause.get("evidence_ids", [])}
        sources = {row.get("source") for row in report.get("evidence", []) if row.get("id") in cited}
        sources.discard(None)
        if len(sources) < 2:
            raise Blocked("SECOND_SOURCE_REQUIRED")
        for attempt in self.attempts():
            if attempt["phase"] in ("executing", "verifying", "rolling_back"):
                raise Blocked("MUTATION_IN_FLIGHT", 409)
            if attempt["plan"]["target"] == plan["target"] and self.clock() - attempt["created"] < 300:
                raise Blocked("TARGET_COOLDOWN", 409)
            if attempt["report_id"] == report["run_id"] and attempt["phase"] in ("failed", "uncertain", "aborted"):
                raise Blocked("PREVIOUS_ATTEMPT_FAILED", 409)
        return impact, ", ".join(sorted(sources))

    @audited
    def dry_run(self, value, report):
        plan = canonical_plan(value)
        impact, sources = self.constraints(plan, report)
        self.verifier.preflight(self.verification_alert(report), report["run_id"])
        try:
            world = self.world(plan)
        except Blocked:
            raise
        except Exception as exc:
            raise Blocked("WORLD_STATE_UNAVAILABLE", 409) from exc
        effects = {"toggle_flag": "Restore normal application behavior and verify the original alert signals.",
                   "restart_service": "Start a fresh process and restore availability to callers.",
                   "throttle_load": f"Reduce generated load to {plan['parameters'].get('users')} users; retain measured requests for verification."}
        result = {"plan": plan, "plan_digest": digest(plan), "world_state_hash": digest(world),
                  "report_digest": digest(report), "preconditions_ok": True,
                  "predicted_effect": effects[plan["action"]], "impact": impact,
                  "decision": "REQUIRE_HUMAN", "reason_codes": impact["reason_codes"],
                  "second_source_check": sources,
                  "side_effects": "A restart interrupts in-flight requests; throttling reduces test traffic; configuration changes affect new requests.",
                  "rollback_limits": "Restart cannot restore interrupted requests. Other actions restore the captured prior settings only if world state still matches."}
        self.log("dry_run", report_id=report["run_id"], **plan, result="preview_only")
        return result

    @audited
    def approve(self, value, report, preview, operator, *, input_fn=input, output=print,
                auto_approve_for_tests=False, policy_approval=False):
        if not isinstance(operator, str) or not operator.strip():
            raise Blocked("OPERATOR_REQUIRED")
        current = self.dry_run(value, report)
        if any(current[k] != preview.get(k) for k in ("plan_digest", "world_state_hash", "report_digest")):
            raise Blocked("WORLD_OR_PLAN_CHANGED", 409)
        if policy_approval:
            if current["impact"]["tier"] not in self.policy["auto_approve_tiers"]:
                raise Blocked("POLICY_APPROVAL_DISABLED")
            output("policy approval, outside the event rules")
            approved = True
        else:
            approved = prompt(report, current, operator, auto_approve_for_tests=auto_approve_for_tests,
                              input_fn=input_fn, output=output)
        if not approved:
            ref = self.log("approval_rejected", report_id=report["run_id"], actor=operator, **current["plan"])
            return {"decision": "reject", "approved_by": operator, "requested_at": now(), "action_log_ref": ref}
        with exclusive(self.private / "mutation.lock"):
            self.constraints(current["plan"], report)
            world = self.world(current["plan"])
            if digest(world) != current["world_state_hash"]:
                raise Blocked("WORLD_STATE_CHANGED", 409)
            token = secrets.token_urlsafe(32)
            record = {"plan": current["plan"], "plan_digest": current["plan_digest"],
                      "report_digest": digest(report), "report_id": report["run_id"], "world": world,
                      "world_state_hash": digest(world), "operator": operator, "approved_at": now(),
                      "expires": self.clock() + 600, "used": False,
                      "mode": "policy" if policy_approval else "test" if auto_approve_for_tests else "human"}
            self.put("approvals", digest(token), record)
        self.log("approval_granted", report_id=report["run_id"], actor=operator,
                 token_digest=digest(token), mode=record["mode"], **current["plan"])
        return {"decision": "approve", "token": token, "approved_by": operator,
                "approved_at": record["approved_at"], "requested_at": record["approved_at"], "expires_at": record["expires"]}

    @audited
    def execute(self, value, report, token, idempotency_key):
        plan = canonical_plan(value)
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 200:
            raise Blocked("IDEMPOTENCY_KEY_REQUIRED")
        with exclusive(self.private / "mutation.lock"):
            approval = self.get("approvals", digest(token))
            if not approval:
                raise Blocked("APPROVAL_REQUIRED")
            if approval["plan_digest"] != digest(plan) or approval["report_digest"] != digest(report):
                raise Blocked("PLAN_OR_REPORT_CHANGED", 409)
            previous = self.get("attempts", idempotency_key)
            if previous:
                if previous["token_digest"] != digest(token):
                    raise Blocked("IDEMPOTENCY_CONFLICT", 409)
                if previous.get("result"):
                    self.log('execute_replay', report_id=report['run_id'], idempotency_key=idempotency_key, result='previous_result')
                    return previous["result"]
                raise Blocked("ATTEMPT_REQUIRES_REVIEW", 409)
            self.check_stop()
            if approval["expires"] <= self.clock():
                raise Blocked("APPROVAL_EXPIRED", 403)
            if approval["used"]:
                raise Blocked("APPROVAL_ALREADY_USED", 409)
            self.constraints(plan, report)
            self.verifier.preflight(self.verification_alert(report), report["run_id"])
            if digest(self.world(plan)) != approval["world_state_hash"]:
                raise Blocked("WORLD_STATE_CHANGED", 409)
            approval["used"] = True
            self.put("approvals", digest(token), approval)
            attempt = {"plan": plan, "report_id": report["run_id"], "report": report,
                       "token_digest": digest(token), "created": self.clock(), "started_at": now(),
                       "phase": "executing", "before": approval["world"], "operator": approval["operator"]}
            self.put("attempts", idempotency_key, attempt)
            self.log("execute_started", report_id=report["run_id"], actor=approval["operator"],
                     idempotency_key=idempotency_key, token_digest=digest(token), **plan)
            started = time.monotonic()
            try:
                self.check_stop()
                self.executor.execute(plan, attempt["before"])
                finished = now()
                attempt["after_hash"] = digest(self.world(plan))
                ref = self.log("execute_finished", report_id=report["run_id"], actor=approval["operator"],
                               **plan, result="applied", duration_ms=round((time.monotonic()-started)*1000))
                result = {"executed": True, "started_at": attempt["started_at"], "finished_at": finished,
                          "action_log_ref": ref, "idempotency_key": idempotency_key}
                attempt.update(phase="verifying", result=result)
                self.put("attempts", idempotency_key, attempt)
                return result
            except Exception as exc:
                attempt["phase"] = "aborted" if isinstance(exc, Blocked) and exc.status == 423 else "uncertain"
                self.put("attempts", idempotency_key, attempt)
                self.log("execute_uncertain", report_id=report["run_id"], **plan, result=attempt["phase"])
                if isinstance(exc, Blocked):
                    raise
                raise Blocked("EXECUTION_UNCERTAIN", 409) from exc

    @audited
    def verify(self, key, progress=None):
        with exclusive(self.private / "mutation.lock"):
            attempt = self.get("attempts", key)
            if not attempt:
                raise Blocked("UNKNOWN_ATTEMPT", 409)
            if attempt.get("verification"):
                return attempt["verification"]
            if attempt["phase"] != "verifying":
                raise Blocked("ATTEMPT_REQUIRES_REVIEW", 409)
            try:
                report = attempt["report"]
                verification = self.verifier.verify(self.verification_alert(report), report["run_id"], self.check_stop, progress)
                if not verification["recovered"]:
                    self.check_stop()
                    attempt["phase"] = "rolling_back"
                    self.put("attempts", key, attempt)
                    if digest(self.world(attempt["plan"])) != attempt["after_hash"]:
                        raise Blocked("ROLLBACK_WORLD_CHANGED", 409)
                    restored = self.executor.rollback(attempt["plan"], attempt["before"])
                    verification["rolled_back"] = restored["restored"]
                    verification["rollback_note"] = restored.get("reason", "Captured settings restored; recovery still requires operator review.")
                    self.log("rollback", report_id=report["run_id"], **attempt["plan"], result=restored)
                attempt["phase"] = "done" if verification["recovered"] else "failed"
            except Exception as exc:
                stopped = isinstance(exc, Blocked) and exc.status == 423
                attempt["phase"] = "aborted" if stopped else "uncertain"
                verification = {"checked_at": now(), "signal": attempt["report"]["alert"]["signal"],
                                "before": attempt["report"]["alert"].get("observed"), "after": None,
                                "recovered": False, "rolled_back": False, "outcome": "blocked",
                                "requests_observed": 0, "samples": [],
                                "rollback_note": exc.code if isinstance(exc, Blocked) else "VERIFY_OR_ROLLBACK_UNCERTAIN"}
            attempt["verification"] = verification
            self.put("attempts", key, attempt)
            self.log("verification", report_id=attempt["report_id"], result=verification)
            return verification

    def stop(self, operator):
        self.stop_path.write_text(f"{now()} {operator}\n", encoding="utf-8")
        self.log("stop", actor=operator)
        return {"stopped": True}

    @audited
    def clear_stop(self, phrase, operator):
        if phrase != "I confirm the incident is over":
            raise Blocked("STOP_CLEAR_CONFIRMATION_REQUIRED")
        with exclusive(self.private / "mutation.lock"):
            self.stop_path.unlink(missing_ok=True)
            self.log("clear_stop", actor=operator)
        return {"stopped": False}
