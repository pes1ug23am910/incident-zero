# Build 05 — Approval-gated hands

The branch record below is historical. The integration round owns the stack;
its real acceptance ledger is appended at the end and in BUILD_06.md. Earlier
"deferred" statements describe the branch session, not the integrated build.

2026-10-23, branch `hands`, based on `3d32a78`. Initial `git status` was clean
and `git diff` empty; the earlier brain implementation was retained. No live
injection, reset, execution, restart, toggle or throttle was performed. The
other session owns the only demo stack. Live acceptance is deferred below.

## Implementation

- Localhost FastAPI on 8787: allowlist, dry-run, terminal approval, execute,
  verify/rollback, STOP and exact clear phrase `I confirm the incident is over`.
- Tier 1 asks for `y` after concrete operation/target/effect; tier 2 requires
  typed `yes` and displays evidence and the independent-source check. Tier 3
  never carries a proposal. Three-valued policy and reason codes are recorded.
- Durable ten-minute tokens bind the plan digest, report digest, world hash and
  operator. Idempotency survives a service restart. One mutation is in flight;
  target cooldown is five minutes. Failed/uncertain attempts fail closed.
- `agent.respond` resumes the existing SQLite thread after checking that its
  next node is exactly `approval` and the report matches. It upgrades the old
  inert preview through a separate dry-run node. No investigation is repeated.
  Future integration is one import of `build_graph` from `agent.respond`.
- Recovery uses >=180 seconds with 30-second samples, two consecutive qualified
  recoveries, >=20 measured requests, a running load generator, and every alert
  signal. Non-recovery restores captured settings when safe; STOP blocks rollback.
- Bundles retain reports, alert, sanitized model logs, action-log excerpts and
  evidence snapshots. Token values are never published. A completeness/hash
  manifest accompanies the existing immutable v1 snapshot envelope.

No model was invoked for the hands tests. The inherited primary model pin is
`openai/gpt-5`; fallback and reviewer configuration remain owned by the brain.
This session's model API cost is zero. No new template files were ported.

## Verification checkpoint

Final step-3 full command: `.\.venv\Scripts\python.exe -m pytest -q` →
**325 passed, 1 skipped in 8.58 seconds**. The skip is the existing Windows
symbolic-link privilege check. No tests were excluded and no live executor ran.
`tests/test_action_api.py` includes the six saved-bundle acceptance cases,
cross-process lock behavior, strict parameters, policy opt-in banner, new-world
rejection during a prompt, and future-evidence timestamp rejection.

The mocked Action API suite currently passes 33 cases. It includes HTTP
403/409/423, forbidden operations, dry-run immutability, token expiry/plan edits,
durable replay, concurrent execution exclusion, cooldown, STOP, rollback,
unavailable telemetry, lost traffic and old-brain-checkpoint resumption.
The full-suite result and exported synthetic bundles are recorded in the next
checkpoint below. `INCIDENT_ZERO_TEST=1` with test auto-approval is exercised
only against fakes; most tests simulate a terminal answer instead.

The two missing-helper detector tests now use the existing `scripts/checkpoint2.py`
recovered from the concurrent checkout, without running it. The requested
SPEC_04 file was absent in this worktree, so it was read from the main checkout.
`agent/graph.py`, `agent/run.py` and `tools/` are unchanged here.

Read-only probes: Locust's page exposes its spawn rate and its stats endpoint
exposes user count; frontend server-span `increase(...[2m])` returned a positive
request count. These establish read interfaces only, not remediation success.
The local demo image inventory is in `docs/DEMO_IMAGES.md`.

## Live acceptance (deferred)

Do not run these while the other session owns the stack. Run from the final
merged checkout after that session hands over ownership. These commands use the
operator rehearsal driver added with the demo deliverable; it preserves the
baseline before injection, waits up to 90 seconds for an alert, resumes approval,
validates the bundle, then resets and waits for a >=180-second clean window.
The `--live` switch is explicit because this driver mutates the only stack.

```powershell
cd D:\incident-zero
$py = '.\.venv\Scripts\python.exe'
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DEMO_VERSION = '2.0.2'
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
# Use fresh report IDs if these names already exist.
& $py -m scripts.hands_rehearsal payment-failure --live --report-id hands-live-payment --operator 'Yash Verma'
# Type yes at the tier-2 prompt. Expected: fixed only after measured recovery.
& $py -m scripts.hands_rehearsal payment-failure --live --report-id hands-live-rejected --operator 'Yash Verma' --reject
# Expected: needs_human; no action execution.
& $py -m scripts.hands_rehearsal container-stopped --svc recommendation --live --report-id hands-live-restart --operator 'Yash Verma'
# Type yes. Expected: restart_service followed by recovered, or honest escalation.
& $py -m scripts.hands_rehearsal homepage-flood --live --report-id hands-live-throttle --operator 'Yash Verma'
# Type y if tier 1; typed yes if tier 2. Traffic must remain >=20 requests/window.
& $py -m scripts.hands_rehearsal payment-failure --live --report-id hands-live-stop --operator 'Yash Verma' --stop-after-seconds 15
# The timer starts at execution, not while the human is reading. Expected: aborted.
# When the interrupted run is over, the operator clears the latch explicitly:
& $py -m action_api clear-stop --operator 'Yash Verma' --confirmation 'I confirm the incident is over'
& $py -m faultctl reset
& $py -m detect.recovery --timeout 360
git -C D:\opentelemetry-demo status --porcelain
```

Forced non-recovery is deliberately confined to mocks. The exact reproducible
command is below. Do not add a live verification override that could falsify
recovery. A live rollback acceptance case still requires a later controlled,
operator-owned fault whose real alert remains above threshold after remediation.

```powershell
& $py -m pytest -q tests/test_action_api.py -k 'rollback_restores_previous_settings or restart_nonrecovery'
```

For the API BLOCK path, start `python -m action_api serve` in one terminal and
run this in another (after the live handoff). The operation is forbidden and
must return 403 without reaching an executor; then latch STOP:

```powershell
$body = @{ action='delete_database'; target='payment'; parameters=@{}; report=@{}; idempotency_key='forbidden-demo' } | ConvertTo-Json
Invoke-WebRequest http://127.0.0.1:8787/actions/execute -Method Post -ContentType 'application/json' -Body $body -SkipHttpErrorCheck
Invoke-RestMethod http://127.0.0.1:8787/stop -Method Post -ContentType 'application/json' -Body '{"operator":"Yash Verma"}'
```

## Mock acceptance bundles

Six retained bundles under `reports/mock-*/` were generated by the actual
checkpoint response path with fake executors, fake telemetry and virtual time.
Each carries an explicit synthetic-data limitation; none is evidence that a
practice incident was diagnosed correctly or repaired on the live stack.

| Bundle | Component fixture | Action / choice | Final status | Verification time |
|---|---|---|---|---|
| mock-payment-approved | payment | toggle_flag, yes | fixed | 180 virtual seconds |
| mock-payment-rejected | payment | no | needs_human | no verification |
| mock-recommendation-restart | recommendation | restart_service, yes | fixed | 180 virtual seconds |
| mock-homepage-throttle | load-generator | throttle_load, y | fixed | 180 virtual seconds |
| mock-stop-mid-run | payment | STOP after execution | aborted | next cancellation point |
| mock-non-recovery | payment | toggle_flag, persistent failing samples | rolled_back | 180 virtual seconds |

All six bundles pass schema and offline evidence resolution, include nonempty
action-log excerpts and retain resolvable execution-log snapshots. Their
confidence of 0.90 is a fixture input, not a model estimate or calibration result.
No live timings or accuracy scores are reported.

## Not verified / integration limits

- All real executor mutations, real model diagnosis-to-fix, real rollback and
  STOP during a Docker mutation remain unverified. A Docker CLI cancellation
  cannot undo a restart already accepted by the daemon; in-flight HTTP calls
  have bounded timeouts and cannot be forcibly undone.
- Existing diagnostic snapshots use a closed v1 envelope without a `complete`
  field. Their content hashes remain intact. The bundle manifest marks absence
  of completeness proof as false. Updating the tools envelope is left to the
  tools owner; this branch does not edit `tools/`.
- Locust must expose previous users and spawn rate; otherwise throttle blocks.
  The failure-switch executor requires an operator overlay mount for writes.
- There is no live forced-failure backdoor. Forced non-recovery is a fake sampler
  in unit tests. An actual live failure must be observed without fabricating
  recovery telemetry.
- Aggregate multi-service tier 3 takes precedence over the sequential action
  queue. Eligible multiple proposals are reviewed individually; rejection does
  not approve or cancel later proposals.

## Demo and final validation

`scripts/demo.ps1` provides a safe preview by default and an explicit `-Live`
path. It uses a prepared real tier-2 checkpoint for rejection, a live tier-1
candidate, a forbidden-operation HTTP 403 demonstration, STOP and operator
cleanup. It never auto-clears STOP: the operator supplies the exact phrase.
Preflight/cleanup are outside the five-minute presentation target, and measured
alert/model delays may exceed the target. Verification is never shortened.

Executed here: PowerShell AST parse, default preview only, Python driver/response
`--help`, and all unit tests. Neither the `-Live` path nor `show_block` was run.
The stack was left under the other session's ownership, without a reset.

Final full suite: `.\.venv\Scripts\python.exe -m pytest -q` → **331 passed,
1 skipped in 9.15 seconds**. The Action API suite includes 44 cases. Export of
the six mock bundles was repeated after validating the saved JSON itself, not
only the in-memory report; all six passed. A regression covers exact sanitized
brain-checkpoint equality, preserving null approval tokens after rejection,
and explicit rejection when live preconditions are unavailable.

Read-only image inventory, approval/STOP instructions, injection mechanism,
five-minute timing limits and remaining limitations are in README and
`docs/DEMO_IMAGES.md`. No new model calls or live hands acceptance claims were
added. Commits remain on `hands`; nothing was pushed.

## Integration live ledger

The integration session merged the branch into `main` and owns the real stack.
Automated approval runs explicitly use BOTH `INCIDENT_ZERO_TEST=1` and
`--auto-approve-for-tests`. They exercise the real prompt entry point and token
gate, but the printed banner states that **no human approval was collected**.
The mentor/demo wrappers reject the test environment and collect the real
terminal or browser decision.

| Bundle | Outcome | Approval | Injection to verified report | Verification | Before / after reset windows |
| --- | --- | --- | ---: | ---: | --- |
| payment-failure-loop-r1 | No alert in 90s; no diagnosis/action | Not reached | — | — | 244.781 / 183.953 s |
| payment-failure-loop-r2 | Planned workload exceeded old baseline; injection refused | Not reached | — | — | 184.391 / 184.500 s |
| payment-failure-loop-r3 | fixed, payment toggle | Explicit test auto | 346.016 s | 182.359 s | 184.562 / 184.375 s |
| payment-failure-loop-r4 | needs_human; rejection, no mutation | CLI reject; test mode off | — | Not executed | 184.640 / 185.031 s |
| container-stopped-loop-r1 | fixed, recommendation restart | Explicit test auto | 609.922 s | 182.000 s | 184.781 / 184.656 s |
| payment-failure-loop-r5 | aborted by STOP during verification | Explicit test auto | — | Interrupted; no recovery claim | 184.281 / 184.719 s |
| payment-failure-loop-r6 | Failed forced-non-recovery acceptance; report fixed | Explicit test auto | Not claimed for this failed test | 181.969 s | 184.782 / 184.718 s |
| payment-failure-loop-r7 | rolled_back; runner failed an overstrict stop assertion | Explicit test auto | — | 182.625 s | 184.844 / 183.938 s |

The successful payment run is `runs/20261023T153512.976354Z-13778fd2`.
It diagnosed `payment` / `application_flag` at 0.90 confidence with three tool
calls in 55.95 seconds. At verification 152.343 and 182.359 seconds all four
original alert signals were 0, measured frontend requests were 984.049, and load
was running. The report became `fixed` before operator reset; cleanup is not
being counted as action-caused recovery. Full action-log and before/after samples
are retained in `reports/payment-failure-loop-r3/`.

The first attempt used five users. Failed payment calls arrived too late for a
90-second metric alert; the failure is retained. Subsequent explicit workload
preparation uses 20 users/spawn 5 and a measured clean workload baseline without
changing thresholds. The second refusal is also retained. The mentor command
captures and restores its previous swarm settings. The five-minute presentation
starts after live diagnosis preparation; it never shortens verification.

The rejection run is `runs/20261023T154711.305759Z-b5f7c99e`. Its final report
records `approved=false` and `executed=false`; the action log contains only
dry-run and rejection events. Authoritative world hashes before and after the
decision match. It finished 145.453 seconds after injection, then the operator
reset and completed the separate clean window. This is rejection acceptance,
not action-caused recovery.

The recommendation restart run is `runs/20261023T160004.705486Z-ad2f6cb4`.
It diagnosed `recommendation/container_down` at 0.90, performed the tier-2
`restart_service` action, and reached `fixed` before reset. Final verification
samples at 151.953/182.000 seconds observed the container running, load running,
and 892.045/1220.081 measured requests. The response phase took 200.141 seconds;
the long diagnosis accounts for most of the 609.922-second injection-to-recovery
time. Action-log lines 30–35 and all reset measurements are retained.

The STOP run is `runs/20261023T161808.661278Z-149073c4`. Payment was diagnosed
at 0.90 with three calls in 42.98 seconds. Execution began at 16:19:10.097 UTC;
the requested timer latched STOP at 16:19:25.263 UTC. Verification recorded
`STOP_LATCHED` at 16:19:25.692 UTC and the final report is `aborted`, with no
rollback or recovery claim. Response duration was 30.985 seconds; injection to
aborted report was 137.438 seconds. The global STOP entry is retained at action
log line 41, alongside this run's lines 36–42. STOP remained latched through
operator reset and its qualified clean window, then was explicitly cleared.

The cancellation handler at the time discarded partial verifier samples; the
empty sample list/zero request field does not mean traffic was absent. Console
progress recorded an initial failing sample at 1.938 seconds, but its values
were not reconstructed into the report. Before/after clean samples remain intact.

The first forced non-recovery attempt (`payment-failure-loop-r6`) failed its
operator control: `/loadgen/stop` exceeded the 10-second HTTP deadline. The
response still finished as `fixed`, with final request counts 56.005/70.005 and
a running load container; the runner correctly returned failure. This is not
rollback acceptance. Its 199.703-second response and clean reset windows are
retained. The run exposed that container liveness alone cannot establish an
actively running Locust swarm; residual/probe traffic can exceed 20 requests.
The subsequent verifier requires an observed running swarm with positive users
as well as container liveness, and the operator stop must be read back. The
retry is retained separately rather than replacing this result.

The stronger verifier did roll back in r7
(`runs/20261023T164609.601361Z-807c1a76`): all seven samples refused recovery;
the final two observed Locust `stopped` with one remaining user and 40.003/52.003
requests. Captured payment settings were restored and `recovered=false`.
The runner nevertheless failed because its operator stop assertion required
zero users. The official stack reported stopped state with a lingering user.
The generic readback now accepts observed `stopped` with a valid nonnegative
integer count, retaining that count exactly; running-with-zero still fails.
Thirty-four isolated runner tests passed. R7 remains unchanged, and r8 repeats
acceptance with that corrected assertion. R7 response duration was 206.188 seconds.
