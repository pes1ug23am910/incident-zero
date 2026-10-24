# Why these controls exist

**Audit qualification (October 23):** the historical implementation described
below has unresolved safety findings. Test approvals in older reports are not
human decisions; browser r9 was automated. Unknown/trafficless verification must
escalate without automatic rollback, rather than use the historical r7/r8 path.
Actual sample age, baseline-relative affected-service traffic, already-clear
alerts, bounded locks, fresh server state and browser codes require the fold
fixes. Spanmetrics and spans share one evidence family. Refer to
[ARCHITECTURE.md](ARCHITECTURE.md) and [EVALUATION_NOTE.md](EVALUATION_NOTE.md) for
the current status; the historical examples below do not certify those fixes.

The integrated loop can change the live stack only through a concrete approved
plan. These rules distinguish diagnosis, authorization, command success and
measured recovery. Actual live results are in [BUILD_05](../BUILD_05.md) and
[BUILD_06](../BUILD_06.md); fixtures do not establish live behavior.

## Telemetry drives diagnosis

The detector reads metrics and container health. It never asks the injector
what failed. `health_table` is the first investigation call; every subsequent
structured read has a reason, and the 12-call budget bounds cost and repetition.
The incident ID is output metadata and is excluded from prompts. Control settings
and revealing telemetry attributes are stripped before prompting/snapshotting.

The setting adapter is a separate write boundary: it reads prior settings only
for approved remediation, world-state hashing and rollback. That information
never becomes diagnostic evidence. Checks: `test_agent_isolation.py`,
`test_no_flag_reads.py`, `test_redact.py`, `test_graph_routes.py` and `test_detect.py`.

## Independent evidence supports the component

The builder rejects invented IDs and unsupported component claims. A retained
observation includes its source and checksum; the resolver labels live, snapshot
and bundle-snapshot origins. An old observation does not prove present health.

Final confidence is the smaller of model and evidence confidence. Two runtime
fields from the same container are one source. An exited dependency plus caller
connection errors supplies independent runtime and application observations,
including when Docker stdout supplies the errors. Duplicate exports of the same
log do not multiply confidence. A stopped dependency is `container_down`, naming
the dependency as component and the caller as symptom owner. This avoids fixing
the healthy caller while preserving the meaning of dependency unavailability.

The confidence rule is a heuristic requiring calibration, not an established
probability. Multiple causes and unexplained symptoms remain visible. Checks:
`test_planted_evidence.py`, `test_trace_origins.py`, `test_snapshots.py`,
`test_bundle_resolution.py` and `test_calibration.py`.

## The allowlist and risk tier determine the review

Telemetry prose cannot select arbitrary shell commands. Code maps supported
causes to `toggle_flag`, `restart_service` or `throttle_load`, with known service
targets and strict parameters. Unsupported operations return BLOCK and a reason
code. Critical services and restarts require tier 2; unsafe data risk, independent
multi-service failures and unsupported remedies become tier 3 with no proposal.

Tier 1 asks for `y` after showing the concrete plan. Tier 2 adds evidence,
alternatives, uncertainty, side effects and rollback limits and requires typed
`yes`. The UI additionally requires an operator name and a rejection reason.
No reviewer model is implemented; independent observations supply the second
source check. Checks: `test_risk.py`, `test_injection.py`, `test_action_api.py`,
`test_ui_api.py` and `test_response_integration.py`.

## Tokens bind one approval to one plan and world

A dry run changes nothing. It checks the plan and current preconditions, then
shows the exact operation, target, parameters, predicted effect and limits.
After the human decision the service repeats those checks and issues a durable
ten-minute token bound to the plan digest, report digest, operator and world
hash. A report edit, changed container/configuration or expired approval cannot
authorize a different write. A boolean inside model output is never authority.
The browser's fresh preview must also match the original checkpoint's plan,
report and world hashes. Reloading the page after an operator reset cannot
give the earlier diagnosis new authority over a changed system.

Reports are sanitized presentation files. The response code compares them with
the private checkpoint, including sanitized/null-token equivalence, before
binding an approval to that canonical report. Raw tokens stay in ignored runtime
state. Public reports/logs contain redacted receipts or fingerprints. The HTTP
endpoint cannot request the test bypass. A diagnosis older than ten minutes, or
one with a missing, malformed, naive or more-than-45-seconds-future timestamp,
returns `DIAGNOSIS_EXPIRED`. A new preview must not turn an old paused finding
into new authority; regenerate the diagnosis and retain its history read-only.
Checks: `test_action_api.py` and
`test_response_integration.py` cover missing/expired tokens, changed worlds, edited
reports and canonical checkpoint binding.

## Idempotency and shared response ownership prevent duplicate writes

An execution records durable intent before the mutation. Replaying the same key
returns that attempt's result; an uncertain or failed attempt is never blindly
retried. A new key does not evade a five-minute target cooldown or an active
mutation/verification sequence. This matters when a browser double-clicks, a
request times out, a process restarts, or a terminal and browser approve together.

The response lock covers the checkpoint transition and its execution, not the
time a human spends reading. The winner rechecks the pending node before resume;
the other surface observes its completion. Both use the same LangGraph thread
and report writer. Tokens alone would not prevent two different approvals from
advancing the same checkpoint. Durable attempts and checkpoint ownership address
both boundaries. Checks: concurrent/restart/idempotency cases in
`test_action_api.py` and `test_response_integration.py`.

If the browser starts or finishes before the terminal enters `resume`, the
terminal joins that same original diagnosis under the shared lock. It waits for
verification and bundle persistence before returning to operator cleanup; a
changed report is still rejected. Otherwise a fast browser decision could make
the terminal report an error and reset the stack during an active verification.

## STOP survives an API restart

The kill switch is a root file plus terminal and HTTP/UI controls. Every new
mutation checks it, verification checks it between samples, and rollback obeys
it too. A file remains effective if the API process exits. Only the exact phrase
`I confirm the incident is over` clears it. The application never clears STOP
just because a timer elapsed or a report completed.

STOP during a pending approval also persists `aborted` in the canonical
checkpoint and bundle, with an `approval_aborted` audit event and no execution
attempt. The terminal, browser wait and HTTP/UI STOP routes share this helper.
If an active response owns the lock, it keeps ownership and handles cancellation;
the pending-abort path does not race it. Clearing the latch later does not erase
an already observed STOP outcome. Cancellation retains samples already observed
and the last measured request count, while keeping recovery false; an interrupted
window cannot prove `fixed`.

STOP cannot undo a command already accepted by Docker. Bounded HTTP calls may
finish before the next check. Operator reset remains available for cleanup while
STOP is latched, and the runner records that cleanup separately from remediation.
Checks: `test_action_api.py`; the live BLOCK/STOP demonstration prints
`403 / FORBIDDEN_OPERATION` and `423 / STOP_LATCHED`.

## Recovery needs enough real traffic over enough time

A successful command does not prove that users can complete requests. The
verifier checks every signal in the original alert, every 30 seconds, over at
least 180 seconds. Two consecutive final samples must satisfy recovery, observe
at least 20 frontend server requests in the two-minute counter window, and show
the load-generator container running plus current Locust state `running` with
`user_count > 0`. Request counts are measured increases,
not an RPS extrapolation. Missing telemetry or stopped traffic prevents `fixed`.
The actual swarm observation and its time are retained. A live container can
host a stopped swarm, while residual/background requests still exceed 20; the
first forced non-recovery attempt exposed that gap. Unknown/unavailable swarm
state fails closed. This rule applies to every incident, not a rehearsal name.

The >=180-second window accommodates spanmetrics flushing and trailing error
history. Both initial/final reset windows in the full-loop runner apply the same
request-count and load checks in addition to all-service health. The bundle saves
samples and stage timings; a reset exit code alone is insufficient. Checks:
verification cases in `test_action_api.py`, `test_hands_rehearsal.py` and
`test_detect.py`. The five-minute presentation never shortens these windows.
The timed demo starts after a real diagnosis is ready, reviewing its retained
live alert/evidence before approval. Injection and investigation are explicitly
preparation; their latency is retained in the bundle, not hidden in a claimed
five-minute injection-to-recovery time.

The mentor/demo wrappers explicitly prepare 20 Locust users and spawn rate 5,
capturing and restoring the initial swarm even after failure. The first live
five-user attempt missed the 90-second detector deadline. Increasing real traffic
before a fresh baseline is an operator setup adjustment; inventing metrics or
silently extending the alert deadline would hide that failure.
The next attempt correctly refused the load increase against its older five-user
traffic baseline. Explicit workload preparation now derives only the frontend
traffic baseline from the last two measured clean-window samples and retains
their evidence. It does not suppress errors, latency, container/resource signals
or change any threshold; existing anomalies still prevent injection.

## Rollback is conditional and observable

Non-recovery restores captured settings only if rollback is safe and the relevant
world still matches. `toggle_flag` restores the previous setting and
`throttle_load` restores the previous users/spawn rate. A restart cannot restore
interrupted requests or the old process, so failed verification escalates.
STOP forbids rollback too; no silent compensation overrides operator control.

The forced live non-recovery rehearsal explicitly stops the Locust swarm after
real execution, leaving its container running. It records the stopped swarm, uses the
unmodified sampler and restores the previous swarm during operator cleanup.
The control allows a 45-second stop response and then checks actual stopped
state with a valid remaining-user count. Locust may report residual users after
stopping; the observed count is retained rather than assumed zero. A timed-out
response is recorded as uncertain; only an observed stopped swarm confirms the
intervention. Cleanup waits for the outstanding
request before restoring users, preventing a late stop from undoing restoration.
This rehearsal checks refusal to claim recovery without an active workload and rollback;
it does not demonstrate a persistent application fault after remediation.
The complete [r8 live run](../reports/payment-failure-loop-r8/report.json)
demonstrated that guard and an actual settings rollback even with positive
residual request counts; operator cleanup recovery was measured separately.

## Test exceptions and audit are explicit

Default policy has `auto_approve_tiers: []`. The developer bypass requires both
`INCIDENT_ZERO_TEST=1` and `--auto-approve-for-tests`, and prints that no human
approval was collected. Automated live acceptance records this path honestly.
Checkpoint 3 and demo wrappers refuse the test environment. Real browser
acceptance uses the actual operator confirmation flow.

Append-only audit records, checkpoint state, report/action history, before/after
measurements and sanitized model/tool journals make each claim inspectable.
Snapshots retain observations after backend expiry; they do not establish
completeness or current recovery. The schema refuses inconsistent approvals,
actions and `fixed` claims. Calibration separates repeated tuning runs from
held-out runs; temperature zero makes inputs repeatable, not model outputs.
