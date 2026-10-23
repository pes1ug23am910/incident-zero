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

Pending the live browser run. No browser approval or live recovery is claimed
by the browser preflight checkpoint.

The CLI rejection bundle `payment-failure-loop-r4` finished as `needs_human`.
The authoritative state hashes match before/after the rejection, and no execute
event exists. Test mode was off. Its final reset was followed by 185.031 seconds
of qualified clean monitoring.
