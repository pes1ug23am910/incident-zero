# Control Room HTTP contract

All URLs are same-origin. No Node, bundler, CDN, login or browser storage is required.
Bind to loopback only. `python -m ui.mock_api` listens at `http://127.0.0.1:8788`.
Install `ui/requirements.txt` into a Python 3.11+ environment first.

`INCIDENT_ZERO_REPORTS_DIR` selects the report directory (default: this checkout's
`reports`). `INCIDENT_ZERO_RUNS_DIR` selects investigation journals (default:
the `runs` sibling of that reports directory). Paths may point to the brain
checkout; these directories are read-only. The UI never reads injection journals.
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

The client passes the displayed report's `revision` when deciding. Tier 2 adds
`confirmation:"yes"`; tier 3 never has a pending item or approve action. Operator
and rejection reason cannot be blank. Invalid input returns 422, unknown IDs 404,
tier-3 approval 403, stale/expired/repeated decisions 409, STOP-blocked approval
423. Mock approvals expire ten minutes after first presentation; report changes
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

`action_api/ui_routes.py` exposes `router`, including the page and static assets.
The hands app mounts it with:

```python
from action_api.ui_routes import router as ui_router
app.include_router(ui_router)
```

The shared implementation lazily imports the hands branch's
`action_api.service.ActionService` through `ui/action_backend.py`. No changes to
the hands service or browser are needed. It presents a native dry run before
approval, forwards the explicit operator answer into the native approval gate,
then runs execute/verify in a background worker. STOP, token binding, allowlists,
cooldowns, rollback and verification remain enforced by the native service.
Compound reports expose a separate approval per action; one click approves only
the selected action. UI decisions are audited through `ActionService.log`.

The original reports are read-only. Incident JSON overlays durable service audit
and attempt records; its `markdown` remains the original report. Final report
export/checkpoint reconciliation remains owned by the brain/hands report writer.
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
