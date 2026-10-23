# Incident Zero — AI On-Call Engineer

Incident Zero detects anomalies in the unmodified OpenTelemetry Demo, diagnoses
them from read-only telemetry, asks a person to approve a concrete remedy, then
executes and measures recovery. The brain, Action API and Control Room share one
persisted LangGraph run and one approval boundary.

Measured results and failures belong in [BUILD_04.md](BUILD_04.md),
[BUILD_05.md](BUILD_05.md), [BUILD_06.md](BUILD_06.md) and the
[evaluation ledger](docs/EVALUATION_NOTE.md). Unit tests establish specific
properties; they do not establish live diagnostic accuracy or recovery.

## Setup

Use Python 3.11+, Docker Desktop with Linux containers, and the official demo
2.0.2 checkout at `D:\opentelemetry-demo`. Keep that checkout unmodified. Reuse
the existing local environment; if it is missing, follow a storage-cleanup notice
when present, otherwise recreate it:

```powershell
cd D:\incident-zero
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DEMO_VERSION = '2.0.2'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe -m faultctl up
.\.venv\Scripts\python.exe -m faultctl build-netem
.\.venv\Scripts\python.exe -m faultctl status
```

An existing `uv` environment may have no `pip` module. In that case install with
`uv pip install --python .venv/Scripts/python.exe -e '.[test]'` instead of the
`python -m pip` line; the environment need not be recreated.

`scripts/up.ps1` automates setup and readiness. `INCIDENT_ZERO_DEMO_DIR` selects
a different official demo checkout. The minimal stack has 21 services. The
collector's Docker API compatibility fix for this laptop is recorded in
[BUILD_01B.md](BUILD_01B.md); the repository does not change daemon settings.

Checkpoint 3 and demo wrappers capture the existing Locust swarm, set 20 users
at spawn rate 5 before the baseline, and restore the captured settings during
cleanup. Override with `-LoadUsers`; this is recorded operator setup, not an
agent remedy. The standalone Python driver leaves load unchanged unless
`--load-users` is supplied. For that deliberate workload change, the frontend
traffic baseline is the median of the final two qualified clean-window samples;
the bundle retains its prior value and metric evidence. All other anomaly checks
and thresholds remain active. The first integrated payment run at five users
produced no detector crossing within 90 seconds; sparse charge calls and metric
flushing delayed visibility. The runner still requires observed traffic and
never lengthens the alert deadline or fabricates recovery.

Keep keys and model identifiers in ignored `.env` or the process environment.
Process values take precedence. `OPENROUTER_MODEL` selects the primary;
`OPENROUTER_FALLBACK_MODEL` selects its fallback. Direct Gemini requires both
`GEMINI_API_KEY` and `GEMINI_MODEL`. No hidden default supplies a model ID.
`OPENROUTER_FAST_MODEL` and `REVIEWER_MODEL` are reserved; no reviewer runs today.
The sanitized report identifies the model that actually succeeded, token usage
and a reference cost estimate, which is not a provider invoice. Never print keys.

## Checkpoint 3: one full loop

```powershell
cd D:\incident-zero
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
.\scripts\checkpoint3.ps1 payment-failure
# Another supported rehearsal:
.\scripts\checkpoint3.ps1 container-stopped -Service recommendation
```

The command starts or reuses the real Control Room at
**http://127.0.0.1:8787**, resets the stack, measures a clean baseline, injects,
waits up to 90 seconds for an alert, investigates, writes the report and pauses
for approval. Review the same pending plan in the terminal and Control Room;
approve once on either surface. `-BrowserApproval` waits exclusively for the
browser decision. Execution and verification update the checkpoint and saved
report. The final Markdown and action-log excerpt print in the terminal.

The runner then resets and measures clean traffic again, even after an error.
Before/after windows and action verification are at least 180 seconds, with two
consecutive qualified samples, at least 20 measured frontend requests in the
two-minute window, and a running load generator. The initial and final clearance
windows make the complete mentor command longer than five minutes.

Bundles use `reports/<incident>-loop-r<n>/`, or a fresh `-ReportId`. They retain
JSON/Markdown reports, alert, sanitized model journal, evidence snapshots,
action-log excerpt, timings, and `verification-before-after.json`. Existing
bundles are never overwritten. A non-actionable diagnosis remains an escalation.

For organiser incidents, start the real UI and telemetry watcher without an
injector:

```powershell
.\.venv\Scripts\python.exe -m ui.serve --mode real
# In a second terminal:
.\.venv\Scripts\python.exe -m detect.watch --interval 10 --thresholds detect/thresholds.yaml
```

The watcher writes alerts and starts investigations. Approve from the UI, or
resume a specific report in a terminal:

```powershell
.\.venv\Scripts\python.exe -m agent.respond --report reports/<id>/report.json --operator 'Yash Verma'
.\.venv\Scripts\python.exe -m agent.respond --report reports/<id>/report.json --operator 'Yash Verma' --reject
```

For diagnosis-only rehearsals, `scripts/checkpoint2.ps1 <incident>` remains
available. It resets after diagnosis, so its paused proposal must not be reused
as authority to remediate a later incident. The response checks the current world.

## Approval and STOP

Tier 1 shows the operation, target and expected effect and asks for `y`. Tier 2
shows the evidence, independent-source check, alternatives, uncertainty,
parameters, side effects and rollback limits, and requires typed `yes`.
Critical services and all restarts require tier 2. Tier 3 has no action proposal.
`auto_approve_tiers` stays empty in `action_api/policy.yaml`.

Ten-minute tokens bind the exact plan, report, operator and world state. A changed
plan or world invalidates approval. Durable idempotency prevents replayed writes;
one mutation/verification sequence is allowed at a time, with a five-minute target
cooldown. Terminal and browser decisions share a response lock. A crash or an
uncertain attempt does not trigger an automatic retry. Raw tokens remain private.
Diagnoses older than ten minutes require a fresh investigation; a new token does
not extend an old diagnosis.

```powershell
.\.venv\Scripts\python.exe -m action_api stop --operator 'Yash Verma'
# After review, clear the latch with the exact phrase:
.\.venv\Scripts\python.exe -m action_api clear-stop --operator 'Yash Verma'
# Prompt: I confirm the incident is over
```

The Control Room STOP button, `POST /stop`, or a root `STOP` file latches the
same kill switch. It blocks new actions and interrupts verification; rollback
also obeys it. A pending approval becomes a saved `aborted` report without an
execution attempt; an active response keeps ownership while cancelling safely.
Operator reset remains available. STOP does not undo an operation
already accepted by Docker. Clearing requires the exact phrase above.

The Action API binds only to loopback. `python -m action_api serve` and
`python -m ui.serve --mode real` serve the same app on 8787; run one instance.
Its allowlist is `toggle_flag`, `restart_service`, `throttle_load`.
Other operations return BLOCK with a reason code; Compose scaling is unavailable.

## Control Room and five-minute demo

The static HTML/CSS/JavaScript UI has War Room, Incidents, Services, Approvals and
Safety views. No Node, frontend build, CDN or login is required. Evidence drawers
label live versus retained observations. Real browser approval resumes the same
checkpoint, executes through the Action API and updates the saved JSON/Markdown.
The API contract is [ui/API.md](ui/API.md).

```powershell
# Read-only rehearsal UI with process-local mock decisions; no real actions:
.\.venv\Scripts\python.exe -m ui.serve --mode mock --port 8788
# Preview the timed sequence without touching the stack:
.\scripts\demo.ps1
# Real prompt, live recovery, then BLOCK and STOP demonstrations:
.\scripts\demo.ps1 -Live
# Or approve from the browser:
.\scripts\demo.ps1 -Live -BrowserApproval
```

Preparation includes reset/clearance, **live injection, alert and diagnosis**.
Start the five-minute presentation clock at the `PRESENTATION READY` banner,
when the real plan is waiting for approval. Review the retained live alert and
evidence for about 45 seconds, approve, observe at least 180 seconds of execution
verification, then show a forbidden operation returning
`403 / FORBIDDEN_OPERATION`, STOP, and an allowed operation refused with
`423 / STOP_LATCHED`. The script does not claim injection-to-recovery fits five
minutes; initial preparation and final cleanup are outside that clock.
Verification is never shortened. An optional `-RejectedReport <path>` demonstrates
rejection of an existing real tier-2 checkpoint. Cleanup retains its measured
window and asks the operator to clear STOP explicitly.

The developer acceptance driver supports `--auto-approve-for-tests` only together
with `INCIDENT_ZERO_TEST=1`, printing that no human approval was collected.
Tonight's automated live acceptance uses this explicit exception, recorded per
bundle. The mentor and demo wrappers refuse that environment. The HTTP approval
endpoint cannot enable it. Test-only `--force-nonrecovery` stops the real Locust
swarm after execution and restores it in cleanup; it tests missing-traffic
rollback using unmodified telemetry, not persistent application failure.

## Diagnosis, evidence and injection boundaries

The first tool is `health_table`; each later model step selects one read with a
reason. The budget is 12 tool calls. The model sees telemetry, not the incident ID
or injection settings. Redaction strips control disclosures before prompting or
snapshotting. Evidence IDs must exist and support the named component; final
confidence is the minimum of model and evidence confidence. Two Docker liveness
fields remain one source. Caller connection errors and a dependency's exited
container are independent observations even when stdout supplies those errors.

A stopped dependency is `container_down`: `valkey-cart` is the cause component
and `cart` owns the downstream symptoms. `dependency_unavailable` remains for
dependency failures without an established stopped-container cause. Multiple
independent failures, insufficient confidence, unsupported fixes and data risk
escalate. Distinct users affected are not inferred from span rates.

The operator injector mounts a repository-owned overlay and performs scoped
Docker changes. It never edits `D:\opentelemetry-demo`. Reset restores mounts,
limits, liveness and network state; the runner checks that checkout remains clean.
Only the Action API's narrow setting adapter reads settings for approved writes,
rollback and world-state hashing. Diagnosis cannot read those settings.

Every reported payload is retained with a checksum. Resolve or validate it with:

```powershell
.\.venv\Scripts\python.exe -m tools.resolve '<evidence-id>' --run-dir runs/<run-id> --bundle-dir reports/<id>
.\.venv\Scripts\python.exe -m schema.validate reports/<id>/report.json
.\.venv\Scripts\python.exe -m pytest -q
```

See [architecture](docs/ARCHITECTURE.md), [control rationale](docs/WHY.md),
[schema](schema/README.md), [metrics](tools/METRICS.md), and
[logs](tools/LOGS.md). The external schema adapter preserves the internal report
and validates an additional export when a schema is supplied.

## Known limitations

- The complete practice set, unseen combinations and no-fault calibration have
  not been measured. Consult the evaluation table for actual runs; synthetic
  `reports/mock-*` bundles do not count as live accuracy or latency.
- Restart cannot restore interrupted requests or previous process state.
  Failed restart verification escalates; settings rollback requires an unchanged
  relevant world. An in-flight Docker/HTTP operation may finish before STOP.
- Missing telemetry, unsupported verification signals and insufficient traffic
  prevent `fixed`. Old evidence snapshots establish history, never recovery.
- Throttling needs readable previous users/spawn rate. Switch writes need the
  operator overlay. There is no network/resource-repair or Kubernetes executor.
- Snapshot checksums do not prove complete telemetry. The bundle manifest marks
  absent completeness proof false. No reviewer model or autonomous memory-based
  remediation is implemented.
- The API trusts the local same-user boundary. Ignored `runs/` contains checkpoints,
  tokens and rollback material; it is required to resume, and must remain private.

## Prior work

The mentors permitted Yash Verma's declared unpublished prior code. Only the
environment-loading and provider/retry structure from the earlier router was
adapted; the hands and UI add no template ports. See
[PRIOR_WORK.md](docs/PRIOR_WORK.md) and [TEAM_FORM.md](docs/TEAM_FORM.md).
Credentials, runtime state, injection journals and environments remain ignored;
sanitized report bundles are retained for review.
