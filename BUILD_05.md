# Build 05 — Approval-gated hands

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
