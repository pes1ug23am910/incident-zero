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

## Control Room acceptance

Pending the live browser run. No browser approval or live recovery is claimed
by this preflight checkpoint.
