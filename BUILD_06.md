# Build 06 — Integration and live acceptance

Integration began on 2026-10-23 after the Day 2 shortlist. All commits are local
on `main`; no push was run. The demo remains at `D:\opentelemetry-demo`, with
`DOCKER_HOST=tcp://localhost:2375`. Model IDs are read from the local environment.

## Repository integration

- `deb44df`: reviewed and committed the brain work, retained the historical
  diagnosis bundles, corrected observation-family scoring and stopped-dependency
  taxonomy. Full brain suite: 508 passed, 3 skipped.
- `2b1026b`: merged `hands`. Kept the newer checkpoint runner's baseline checks,
  no-fault/combo support, interruption cleanup and UTF-8 output; retained hands
  code, tests and rationale.
- `5b624c3`: merged `ui`, retaining the Control Room and its tests.
- `git worktree list` now lists only `D:\incident-zero` on `main`. Duplicate
  source files and environments were removed. Some protected pytest/uv cache
  files remain in the old paths; they are not Git checkouts.

## Preflight observations

The old mock Control Room processes on port 8788 were stopped. Merged FastAPI
and Uvicorn dependencies were installed in the main environment. A local
Chromium launch succeeded for the browser acceptance check.

`faultctl status` observed all 21 containers running, reachable shop,
Prometheus, Jaeger, OpenSearch and load UI, and 97 new frontend trace IDs over
60 seconds. The official demo checkout was clean. A real verifier read observed
320.02 measured frontend requests in its two-minute window, load running and
frontend error rate 0. These preflight reads are not remediation acceptance.

The review fixed two live blockers before acceptance: the request-count query
parser now accepts metric label selectors, and the Action API uses the same
observation families as the brain. An exited container and dependent stdout
errors can corroborate one another; copies of application logs cannot.

## Live acceptance

Results will be recorded from retained bundles, including failures. The
verification window remains at least 180 seconds, with two consecutive samples
below every original alert threshold, at least 20 measured frontend requests,
and the load generator running. Operator reset is recorded separately from
action-caused recovery.

The first payment attempt, `payment-failure-loop-r1`, produced no detector alert
within 90 seconds at five Locust users. No diagnosis or action ran. Payment logs
did contain failed charges, first appearing about 59 seconds after injection;
metric export latency prevented a timely threshold crossing. The retained
before/after clean windows were 244.781 and 183.953 seconds. The initial window
also exposed observability-proxy errors caused by offline test fixture lookups;
those tests were isolated, and full suites are no longer run during rehearsals.

At 15:23:24 UTC the operator requested 20 users at spawn rate 5, preserving the
previous five users/rate 1 for final restoration. `payment-failure-loop-r2`
verified clean traffic but refused injection because that planned increase was
above the detector's historical traffic baseline. No action ran. The runner now
records the measured clean workload baseline when load preparation is explicitly
requested; thresholds remain unchanged and other anomalies still block injection.

## Control Room acceptance

The first successful integrated CLI loop is `payment-failure-loop-r3`: `fixed`
after 346.016 seconds from injection, with a real 182.359-second action
verification window and qualified 184.562/184.375-second reset windows.
Approval was the explicit test-auto path, not a human decision. The real Control
Room served its status and report; browser approval acceptance remains separate.

The completed real browser approval is recorded below as r9. The earlier
browser preflight checkpoint alone did not establish approval or recovery.

The CLI rejection bundle `payment-failure-loop-r4` finished as `needs_human`.
The authoritative state hashes match before/after the rejection, and no execute
event exists. Test mode was off. Its final reset was followed by 185.031 seconds
of qualified clean monitoring.

During the recommendation restart run, five proposed finishes initially omitted
the root component from `explains_symptoms`, despite correctly diagnosing its
exited container. The model eventually corrected the omission: nine tool calls,
394.16 seconds. A subsequent generic coverage fix counts a positively supported
cause as explaining its own observed component. Caller/sibling coverage and the
0.75 confidence gate remain unchanged; 133 focused tests passed. The live run
used the prior rules, so no latency improvement is claimed from that change.

Integration review also tightened shared approval behavior: terminal entry joins
an already-owned browser response; browser previews remain bound to the original
checkpoint's plan/report/world hashes; STOP cancels a waiting approval as well as
blocking execution and interrupting verification. Ten isolated integration tests
exercise these paths with network and subprocess access denied. The waiting-STOP
browser runner test also passed. These tests do not substitute for the live
mid-verification STOP and browser acceptance recorded below.

`container-stopped-loop-r1` recovered recommendation through a real restart:
`fixed` at 609.922 seconds after injection, 182.000 seconds of verification,
and clean 184.781/184.656-second before/after windows. The two final action
samples had 892.045/1220.081 measured requests, a running load generator and a
running recommendation container. The Control Room was restarted after this
run to load the reviewed approval/STOP fixes before the remaining cases.

`payment-failure-loop-r5` passed the mid-verification STOP path: `aborted`,
137.438 seconds after injection. STOP was observed about 0.43 seconds after
latching, prevented rollback, and remained set during the 184.719-second clean
reset window. Its action-log export was refreshed from the unchanged canonical
final checkpoint after fixing export to include global safety events within a
run's action interval. The partial-sample loss in the original cancellation
handler is recorded honestly in BUILD_05; no samples were fabricated.

Subsequent cancellation handling retains each actual progress sample and its
last measured request count, while keeping the result blocked/unrecovered and
leaving `after` unknown. Thirteen isolated integration tests passed, including
STOP and a callback exception after one sample. This fixes future evidence
retention; it does not fill in the missing r5 observations retrospectively.

`payment-failure-loop-r6` failed the forced-non-recovery acceptance: its operator
stop request timed out, while residual traffic and container liveness satisfied
the old load-running check. The report is genuinely `fixed` under those recorded
rules, but the runner failed and no rollback is claimed. Its clean windows were
184.782/184.718 seconds. This prompted explicit Locust state/user observation in
the verifier and confirmed stop readback for the retry. Earlier live successes
used container liveness per sample and separately recorded operator load setup;
they are not being relabelled as runs of the stronger check.

The stronger check passed 43 isolated sampler/integration tests. Every live
sample now reads actual Locust state and user count; recovery requires
`state=running`, a positive integer user count and a running container. Unknown
or unavailable load state fails closed. Action samples retain the observation
time/state/count and an immutable `load_observed` action-log snapshot. The
180-second and 20-request requirements are unchanged. The forced operator stop
now confirms `stopped` with zero users, recording any HTTP response uncertainty;
29 isolated runner tests cover this and actual browser-vs-terminal approval
metadata. The retry uses this implementation.

R7 demonstrated actual `rolled_back` behavior with the stronger verifier, but
its harness failed the zero-user assertion despite Locust reporting stopped.
The final action samples contained 40.003/52.003 requests, `load_state=stopped`,
`load_user_count=1`, and `load_running=false`. Verification lasted 182.625 seconds;
cleanup was qualified for 183.938 seconds. The operator readback now retains any
valid nonnegative remaining count in a stopped state, rather than asserting it
must be zero. This is an assertion correction, not a recovery-policy change.
The separate r8 run uses it; r7's failure remains in its original metadata.

R8 passed complete forced-non-recovery acceptance: `rolled_back`, runner
`failed=false`, real 182.750-second verification and qualified
184.984/184.093-second before/after windows. Locust's stopped state with one
remaining user was confirmed and retained. Residual requests and zero alert
values did not bypass the active-swarm gate. This is a traffic-qualification
rollback test, not a persistent-application-error test.

## Completed real Control Room loop

`payment-failure-loop-r9` (`runs/20261023T171108.246095Z-f4afce0d`)
ran through the actual `scripts/checkpoint3.ps1 payment-failure` wrapper, with
test approval disabled and the terminal displaying its approval prompt. A
local Playwright driver entered operator `Integration acceptance`, typed `yes`
in the real Control Room form and clicked once. This was automated browser
acceptance through the real gate, not an unaided human decision or a test bypass.
The terminal joined that same response; the audit contains one execute event.

The report is `fixed` at 313.078 seconds after injection. Action verification
lasted 183.500 seconds. The last two samples contained 1260.084/1188.079 measured
requests, cleared alert signals, and an observed running Locust swarm with 21
users. The browser displayed `fixed` 200.843 seconds after its approval click.
Qualified before/after reset windows lasted 184.047/183.922 seconds. The runner
finished with `failed=false`, actual approval path `browser`, and waiter
`terminal`. Browser observations, screenshots, retained terminal chunks, the
report, evidence snapshots and the action-log excerpt are in its bundle.

Browser review exposed two presentation/queue issues. Long evidence observations
now expand on demand while preserving the full snapshot drawer. Historical
expired diagnoses now skip preview creation using the same ten-minute freshness
guard as execution. Previously polling appended repeated `DIAGNOSIS_EXPIRED`
refusals; it did not grant stale action authority. Thirty-five isolated checks
covered queue expiry and the shared response/STOP behavior.

## Final checks

The whole suite passed: **670 passed, 3 skipped in 37.59 seconds**. An initial
quiet run stalled without a diagnostic and was stopped; the verbose retry
exposed five offline report-repair fixtures selecting the new live graph and
a source-guard false positive on hexadecimal checksums. Explicit diagnosis-only
fixtures and whole-word port matching fixed those failures; guard coverage was
preserved. The final checksum regression also passed separately.

Real safety probe `safety-loop-r1` passed at 17:31:20–17:31:22 UTC:
`delete_database` returned HTTP 403 / `FORBIDDEN_OPERATION`; after latching STOP,
an allowed restart dry run returned HTTP 423 / `STOP_LATCHED`. No mutation
started. The explicit clear phrase cleared STOP. The bundle retains console
output and original audit lines 1949–1952. This probes the demo's actual safety
commands; the complete five-minute presentation has not been timed.

Offline retained-artifact audit passed for 25 reports, 2,596 references and
9,024 snapshots. All 14 available manifests matched; 11 earlier brain-only
bundles predate that manifest format. Network and subprocess calls were denied
during this validation. A scan of 36,307 current tracked/report files found no
configured credential value or recognized credential/private-key format. These
counts precede the separate final-state and safety bundles.
