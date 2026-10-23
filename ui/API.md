# Control Room HTTP contract

All URLs are same-origin. No Node, bundler, CDN, login or browser storage is required.
Bind to loopback only. `python -m ui.mock_api` listens at `http://127.0.0.1:8788`.
Install `ui/requirements.txt` into a Python 3.11+ environment first.

`INCIDENT_ZERO_REPORTS_DIR` selects the report directory (default: this checkout's
`reports`). `INCIDENT_ZERO_RUNS_DIR` selects investigation journals (default:
the `runs` sibling of that reports directory). Mock mode reads these directories.
Real mode resumes matching checkpoints and saves the final response bundle there.
The UI never reads injection journals.
Discovery accepts `reports/<bundle>/report.json` and standalone `reports/*.json`.
Partially written JSON is skipped until the next poll. Incident IDs must be unique;
the latest diagnosed report wins if IDs are repeated.

| Method | URL | Result |
| --- | --- | --- |
| GET | `/api/incidents` | Array of `{id,status,detected_at,component,category,confidence,tier,proposed_action:{type,target}}`, newest first |
| GET | `/api/incidents/{id}` | Full report plus `markdown`, `revision`, `mode`, optional `ui_decision` |
| GET | `/api/incidents/{id}/evidence/{evidence_id}` | Resolved `{id,source,data,resolved_from,captured_at?}`; URL-encode the complete evidence ID |
| GET | `/api/health` | `{rows:[{service,error_rate,p95_ms,rps,restarts,status,cpu,mem}],source,observed_at,warnings,mode}` |
| GET | `/api/approvals` | `{pending:[{id,report_id,tier,action,target,predicted_effect,expiry,revision,status}],history:[],mode}` |
| POST | `/api/approvals/{id}/approve` | Body `{operator,note,revision,confirmation?}`; returns decision |
| POST | `/api/approvals/{id}/reject` | Body `{operator,reason,revision}`; returns decision |
| GET | `/api/stop` | `{stopped:boolean,mode}` |
| POST | `/api/stop` | Latch STOP; empty body; returns latch state |
| DELETE | `/api/stop` | Body `{phrase:"I confirm the incident is over"}`; returns latch state |
| GET | `/api/log?tail=50` | `{lines:[object|string],mode}`; tail 1–500 |
| GET | `/api/events?after=0&wait=20&epoch=` | Long poll `{events,cursor,epoch,reset,mode}`; `wait` 0–20 seconds |

Dates are ISO 8601 UTC; the page displays IST. Error rates are fractions, CPU is
percent, memory is MiB. Unknown telemetry is `null`, never zero. Recorded health
is projected from the newest report's symptoms and labelled `report_snapshot`.

The client passes the pending item's `revision` when deciding (mock: report
fingerprint; real: report and displayed dry-run fingerprint). Tier 2 adds
`confirmation:"yes"`; tier 3 never has a pending item or approve action. Operator
and rejection reason cannot be blank. Invalid input returns 422, unknown IDs 404,
tier-3 approval 403, stale/expired/repeated decisions 409, STOP-blocked approval
423. Cross-origin browser mutations return 403. A changed native world state
invalidates the displayed preview; a fresh dry run must be reviewed and approved
again. Mock approvals expire ten minutes after first presentation; report changes
create a new revision. An approval is not proof of execution or recovery.

Mock state is process-local and resets on restart. Approval overlays never modify
reports, emit execution events, or claim recovery. Markdown remains the original
recorded report. Mock STOP affects this mock API only. Evidence first tries the
read-only `tools.resolve` when available, then
the selected bundle snapshot. Missing payloads return 404, never a fabricated
payload made from the evidence summary.

Events are `{id,type,at,incident_id?,run_id?,...}`. Types: `alert_raised`,
`investigation_step`, `report_ready`, `approval_requested`, `approval_decided`,
`action_executed`, `verification_result`, `stop`. Completed report events are
labelled `recorded:true`. Live steps are read from `runs/*/tools.jsonl`; alert
events come from `alert.json`. No synthetic execution or verification is emitted.
Pass the last cursor and epoch on the next poll. A server restart or expired
cursor sets `reset:true`; refresh the views and replace cached events. The ring
retains 2,000 events. An initial connection may contain historical journal events.

## Real Action API integration

`python -m ui.serve --mode real` and `python -m action_api serve` expose the same
Action API app on port 8787. `action_api/ui_routes.py` includes the page and static
assets. The app's factory mounts a Control Room with its existing lazy service:

```python
from action_api.ui_routes import create_room
from ui.api import make_router
room = create_room(service_factory)
app.include_router(make_router(room))
```

The shared implementation lazily imports
`action_api.service.ActionService` through `ui/action_backend.py`. No changes to
the hands service or browser are needed. It presents a native dry run before
approval, forwards the explicit operator answer into the native approval gate,
then resumes `agent.respond` in a background worker. STOP, token binding, allowlists,
cooldowns, rollback and verification remain enforced by the native service.
Compound reports expose the current checkpoint action; one click approves only
that action. UI decisions are audited through `ActionService.log`.

Real decisions use the canonical report in SQLite, after checking it matches the
sanitized bundle. `agent.respond` saves the final JSON, Markdown, evidence manifest
and action-log excerpt using the same writer as terminal responses. While a run
is executing, incident JSON overlays durable service audit and attempt records.
Historical bundles without a matching paused checkpoint cannot be approved.
The terminal can wait for input while the browser decides; a shared response lock
and checkpoint recheck ensure the action runs once. On Windows, the live terminal
prompt detects browser continuation and waits for the shared result.
An interrupted execution is never automatically retried by the UI. The Action
API's durable attempt state governs whether a later operation is allowed.

For a different hands implementation, an optional `action_api.ui_backend` module
takes precedence over the native adapter. It provides these synchronous functions
(called in worker threads):

```python
list_approvals()  # return the pending/history envelope above
approve(approval_id, operator, note, reason, confirmation, revision)
reject(approval_id, operator, note, reason, confirmation, revision)
get_stop()  # return {stopped, mode:"real"}
set_stop()
clear_stop(phrase)
get_log(tail)
```

The hands adapter owns dry-run preconditions, world-state token binding,
expiry, allowlists, durable audit, execution and verification. It must validate
tier/confirmation/revision and STOP again at execution. Approval IDs may differ
from report IDs; `report_id` connects them. Never return approval tokens to the UI.
If both the hook module and native service are absent, all control operations use
labelled `mock_fallback` state. If the hook module exists but lacks a function, that operation returns 503;
backend failures never silently become mock successes. The browser contract is
identical in all modes. No browser endpoint executes an arbitrary action.
