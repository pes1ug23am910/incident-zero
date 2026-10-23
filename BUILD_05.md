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
merged checkout after that session hands over ownership. Exact commands and the
demo driver are added in the demo checkpoint; no live result is claimed here.

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
