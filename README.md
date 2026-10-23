# Incident Zero — AI On-Call Engineer

Incident Zero includes telemetry tools, a checkpointed investigation graph and
an approval-gated Action API. The hands implementation passes mocked acceptance;
live remediation acceptance is deferred while another session owns the demo.
See [BUILD_05.md](BUILD_05.md) for verified results and exact follow-up commands.

## Setup and run

Use Python 3.11 or newer, Docker Desktop with Linux containers, and the official demo 2.0.2 checkout at `D:\opentelemetry-demo`. Keep that checkout unmodified. Its minimal Compose file contains 21 containers.

Before starting the demo, merge `"min-api-version": "1.24"` into Docker's existing `daemon.json` (Docker Desktop: Settings → Docker Engine), then apply and restart Docker.
The demo's collector uses Docker API 1.25; a daemon minimum above 1.25 rejects its statistics receiver and prevents application telemetry from reaching the backends.

Verify `docker version --format '{{.Server.MinAPIVersion}}'` reports `1.24`. Preserve the daemon's other settings. The existing local connection on this machine is `DOCKER_HOST=tcp://localhost:2375`; no script here changes daemon configuration.

```powershell
cd D:\incident-zero
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DEMO_VERSION = '2.0.2'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe -m faultctl up
.\.venv\Scripts\python.exe -m faultctl build-netem
.\.venv\Scripts\python.exe -m faultctl status
.\.venv\Scripts\python.exe -m tools.cli health_table
```

An existing environment can be reused. `scripts/up.ps1` automates environment setup, stack startup, helper-image build and readiness. Set `INCIDENT_ZERO_DEMO_DIR` to use a different sibling checkout. Operator injection/reset uses `faultctl`; agent remediation uses only the approval-gated Action API. Runtime state stays inside this repository.

```powershell
.\.venv\Scripts\python.exe -m faultctl inject payment-failure
.\.venv\Scripts\python.exe -m tools.cli get_traces checkout
.\.venv\Scripts\python.exe -m tools.cli get_logs payment
.\.venv\Scripts\python.exe -m tools.cli get_logs checkout --severity-min TRACE
.\.venv\Scripts\python.exe -m faultctl reset
.\.venv\Scripts\python.exe -m pytest -q
```

Always reset after a rehearsal; reset remains available when the repository's `STOP` file blocks injection. The ready check observes new frontend traces for 60 seconds. Metric queries use at least two-minute rate windows because spanmetrics update about once a minute, so historical errors can remain visible after requests recover.

## Telemetry and evidence

Prometheus uses `http://localhost:9090`; Jaeger's API is `http://localhost:8080/jaeger/ui/api`. OpenSearch's published port is discovered automatically. See [metric names](tools/METRICS.md) and [log fields and Docker log fallback](tools/LOGS.md) for observations from this stack. Container state comes from Docker inspection, because old Prometheus samples can outlive a stopped container.

Every diagnostic tool filters incident-setting disclosures before returning or saving data. Checkout, product-catalog, shipping, email and frontend logs are read from Docker stdout/stderr with `dlog:` evidence IDs. Payment also falls back to Docker when OpenSearch has no matching records. Use `--severity-min TRACE` to include unclassified stdout messages.

Tools accept `--run-dir runs/<run-id>` and create a timestamped run when omitted. Evidence is retained under that run's `evidence/` directory. Filenames are SHA-256 digests of evidence IDs because IDs contain characters illegal in Windows filenames; each JSON payload retains the full ID, and tool results map IDs to paths. The resolver tries the live backend first, then the retained snapshot, and reports `resolved_from` explicitly. A snapshot establishes what was observed at capture time; it does not establish current recovery.

```powershell
.\.venv\Scripts\python.exe -m tools.cli health_table --run-dir runs/rehearsal
.\.venv\Scripts\python.exe -m tools.resolve 'container:payment:Status=running' --run-dir runs/rehearsal
.\.venv\Scripts\python.exe -m schema.validate schema/examples/valid.json
.\.venv\Scripts\python.exe -m reports.render schema/examples/valid.json
```

The [schema guide](schema/README.md) documents strict evidence, approval and report rules. Example reports are labelled illustrations. [BUILD_01B.md](BUILD_01B.md) records the follow-up live commands, timings and remaining unverified requirements; the earlier build notes preserve the collector failure observed before the daemon fix.

Runtime evidence, injection journals, local environments, credentials and private specifications are ignored by Git. Nothing here edits the official demo checkout.

## How incidents are injected

Both `python -m faultctl` and the installed `faultctl` console script are
available. Operators inject practice faults and reset them; the investigator
never reads the injection journal. The measured implementation writes a local
operator overlay and mounts it into the configuration service. It does **not**
edit `D:\opentelemetry-demo\src\flagd\demo.flagd.json`; this supersedes the
earlier proposed source-file injection mechanism, as recorded in BUILD_01B.
Reset removes the overlay and restores the pristine configuration. After reset,
`git -C D:\opentelemetry-demo status --porcelain` must be empty, and
`python -m detect.recovery --timeout 360` must verify clean metrics before the
next incident. Spanmetric history can take about 120 seconds to clear.

The demo revision is **2.0.2**, minimal mode, **21 services**. A read-only
`docker images --digests` capture is retained in [DEMO_IMAGES.md](docs/DEMO_IMAGES.md).
That inventory identifies locally present images; it is not a claim that a live
mutation acceptance run used them.

## Approval gate and kill switch

```powershell
# A real diagnosis must already be paused at approval in runs/checkpoints.sqlite.
.\.venv\Scripts\python.exe -m agent.respond --report reports/<id>/report.json --operator 'Yash Verma'
# Explicit rejection does not need functioning mutation preconditions.
.\.venv\Scripts\python.exe -m agent.respond --report reports/<id>/report.json --operator 'Yash Verma' --reject
# Optional localhost HTTP interface (approval prompts appear in this terminal):
.\.venv\Scripts\python.exe -m action_api serve
.\.venv\Scripts\python.exe -m action_api stop --operator 'Yash Verma'
.\.venv\Scripts\python.exe -m action_api clear-stop --operator 'Yash Verma' --confirmation 'I confirm the incident is over'
```

Tier 1 shows the concrete operation, target and expected effect and asks for a
human `y` (one key on a Windows terminal). Tier 2 shows the full evidence table,
independent-source check, alternatives, uncertainty, exact parameters, risk,
side effects, rollback limits and verification criteria, then requires typed
`yes`. Tier 3 escalates and proposes no action. Hard risk rules override the
heuristic score. The policy outcomes are REQUIRE_HUMAN, ESCALATE and BLOCK;
blocked requests include a reason code.

`action_api/policy.yaml` keeps `auto_approve_tiers: []`. A deliberately enabled
policy tier prints `policy approval, outside the event rules`; our demo never
enables it. The test-only CLI bypass requires both `INCIDENT_ZERO_TEST=1` and
`--auto-approve-for-tests`, prints a banner and is used only with fake executors
in tests. The HTTP endpoint cannot request that bypass.

Tokens expire in ten minutes and bind the operation/target/parameter digest,
report digest, operator and world-state hash. Edits or external world changes
invalidate them. Execution requires an idempotency key; replay returns the
recorded result. One mutation/verification sequence may run at a time, with a
five-minute target cooldown. A failed attempt requires a fresh investigation
and approval; a process crash with uncertain effects is never retried blindly.

The root `STOP` file or `POST /stop` blocks new changes and interrupts the
verification wait. Rollback also obeys STOP. Only the exact clear phrase above
removes the latch. Every executed action and recovery decision is audited in
`action_api/log.jsonl`; each report bundle includes its excerpt and evidence
snapshots. Public bundles contain redacted approval receipts, never usable tokens.

`agent.respond` checks the persisted thread is at `approval` and that the saved
report matches. Dry run and execution are separate nodes from `interrupt()`;
the token travels in the resume value and the human is asked once. For future
brain integration, import `build_graph` from `agent.respond` in the entry point.
Existing inert-brain checkpoints work through the response command already.

Recovery requires every original alert signal to be healthy on two consecutive
30-second samples over at least 180 seconds, at least 20 measured frontend server
requests in the two-minute window, and a running load generator. Lost traffic
or telemetry never counts as recovery. Reversible settings are restored on
non-recovery if the world still matches; a failed restart escalates.

## Demo

`scripts/demo.ps1` without arguments prints the five-minute presentation plan
without touching the stack. After exclusive stack handoff, use
`scripts/demo.ps1 -Live -RejectedReport reports/<paused-tier2>/report.json`.
Prepare the real tier-2 checkpoint beforehand; the live tier-1 example defaults
to the catalog incident. If the model escalates or proposes another tier, show
that honest outcome instead of forcing approval. The script demonstrates the
approved path, rejection, an HTTP 403 forbidden operation, and STOP, then resets
and verifies cleanup. Clearing STOP asks the operator for the exact phrase.

Preflight and cleanup are outside the presentation clock. Alert/model latency
can make the live sequence longer than five minutes; do not shorten the required
verification window. Individual acceptance runs use
`python -m scripts.hands_rehearsal <incident> --live --report-id <fresh-id> --operator 'Yash Verma'`.
No live driver was executed in this hands session.

## Known limitations

- Live diagnosis-to-fix, real rollback and real STOP cancellation are unverified
  here. Reports under `reports/mock-*` are explicitly synthetic and cannot be
  used to claim model accuracy, calibration or live latency. No model was used
  for these hands tests; the inherited brain primary pin is `openai/gpt-5`.
- Restart cannot recover interrupted requests or previous process state.
  Cancelling Docker's client cannot undo a restart already accepted by the
  daemon. An in-flight HTTP request can finish before its timeout or STOP check.
- Throttle requires readable prior user count and spawn rate. Switch writes
  require a matching operator overlay; official demo source writes are refused.
- Unsupported verification signals, missing telemetry and insufficient request
  volume fail closed. Low traffic after throttling can require rollback even if
  application errors improve. Snapshot evidence proves history, not recovery.
- Existing v1 diagnostic snapshots have content checksums but no explicit
  completeness field. The hands bundle adds a hash/completeness manifest and
  marks unproven completeness false; the shared tools format still needs the
  tools owner's update. That limitation is not hidden by a passing unit suite.
- Independent multi-service causes escalate at tier 3. Eligible action queues
  are handled one at a time. There is no Kubernetes scaling executor, network
  repair executor or reviewer model invocation in the hands path.
- The API trusts the same-user local operator boundary; it is not a hosted,
  authenticated multi-user service. Bind only to localhost. Private SQLite
  state under ignored `runs/` includes rollback material and token records.

## Prior work

The mentors permitted declared unpublished prior code. The complete port list
and adaptations are in [PRIOR_WORK.md](docs/PRIOR_WORK.md). The hands modules
were written for this contract and add no template ports. The event-required
tools declaration remains in [TEAM_FORM.md](docs/TEAM_FORM.md).
