# Incident Zero — AI On-Call Engineer

Round 1 provides incident injection, read-only telemetry tools, and an evidence-backed report schema for the OpenTelemetry Demo. The detector, autonomous investigation loop and approval-gated Action API are planned for later rounds.

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

An existing environment can be reused. `scripts/up.ps1` automates environment setup, stack startup, helper-image build and readiness. Set `INCIDENT_ZERO_DEMO_DIR` to use a different sibling checkout. All system mutations go through `faultctl`; its overrides and runtime state stay inside this repository.

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

## Control Room

The Control Room is a plain HTML, CSS and JavaScript dashboard served by FastAPI.
There is no Node dependency, bundler, CDN or frontend build step. Its dark layout
has five views: **War Room** shows the alert, investigation steps, diagnosis,
impact, clickable evidence and approval gate; **Incidents** lists report bundles;
**Services** refreshes health every ten seconds; **Approvals** shows the pending
queue and decision history; **Safety** exposes STOP, its confirmation phrase and
the action log. Times are displayed in IST. Unknown telemetry stays unknown.

Install the Python dependencies once (an existing project environment works):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]' -r ui/requirements.txt
```

Start mock mode in the UI worktree, reading the brain checkout's recorded bundles:

```powershell
cd D:\incident-zero-ui
.\scripts\ui.ps1 -Mode mock -ReportsDir D:\incident-zero\reports
# Open http://127.0.0.1:8788
```

The equivalent command is `python -m ui.serve --mode mock --reports-dir D:\incident-zero\reports`.
With no directory argument, reports are read from the current checkout's
`reports/`. `-RunsDir` / `--runs-dir` overrides the live investigation journal
directory; by default it is the reports directory's sibling `runs/`. New report
bundles and investigation steps appear automatically.

After the UI and hands branches are merged, start real mode from that checkout:

```powershell
.\scripts\ui.ps1 -Mode real
# Open http://127.0.0.1:8787
# Equivalent: python -m ui.serve --mode real
```

Use `-Port 8789` if another process already owns 8787. To serve the page inside
the existing hands FastAPI app instead, import `router` from
`action_api.ui_routes` and mount it with **`app.include_router(ui_router)`**:

```python
from action_api.ui_routes import router as ui_router
app.include_router(ui_router)
```

The router includes `/`, `/static/app.js`, `/static/app.css`, and every `/api/*`
endpoint documented in [ui/API.md](ui/API.md). The native adapter lazily calls
`action_api.service.ActionService`; the hands app needs no additional hook module.
Real approval presents the native dry-run plan, retains world-state/token/expiry
checks, and runs execution and verification in the background. Each proposed
action needs its own approval. Service audit and attempts provide durable status
overlays; the original report and Markdown stay unchanged. The brain/hands report
writer still owns final report export and checkpoint reconciliation.

Mock mode keeps approvals and STOP in memory and resets them on restart. It never
executes fixes or simulates recovery. If the real service is not installed, the
banner explicitly says **MOCK FALLBACK** and controls remain in memory. Mock STOP
does not stop another session or the live stack. Evidence resolution tries the
read-only resolver and falls back to checksum-verified bundle snapshots; the
drawer labels the source. A saved snapshot does not establish current recovery.

Demo flow:

1. Open **War Room**. Select the newest incident or inspect the saved rehearsal.
2. Have the designated stack operator inject an incident from their separate
   terminal, with the detector/agent running. The UI itself has no injector.
3. Watch the investigation feed, then open the completed report. Click an evidence
   ID to inspect its payload and whether it came from live telemetry or a snapshot.
4. Review impact and the native dry-run plan. Tier 1 has quick Approve/Reject;
   tier 2 requires the evidence review and typed `yes`; tier 3 shows escalation
   findings with no approve button. Enter an operator name; rejection needs a reason.
5. Approve in real mode and watch execution and verification. Recovery is shown
   only when the Action API records it. Mock approval only records the decision.
6. Press **STOP** and show the latched state and action log in **Safety**. Clear it
   only by typing `I confirm the incident is over` exactly.

The saved `payment-failure-r1` bundle is a tier-3 escalation, so it deliberately
has no approval action. Use a newly diagnosed actionable bundle for the approval
part of the real demo; the dashboard never rewrites a historical diagnosis to make
it actionable. Existing journal events are observations, not timed demo playback.

Verify without a browser or the live stack:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ui_api.py
# With the mock server running:
.\.venv\Scripts\python.exe -m ui.smoke --url http://127.0.0.1:8788
```

The contract suite covers evidence checksums, all five assets/views, tier gates,
typed confirmation, stale/expired decisions, rejection, STOP, event cursors and
new bundles, and an injected fake ActionService execution/verification path.
It also checks the actual disk bundle when available; set
`INCIDENT_ZERO_TEST_REPORTS_DIR` if that bundle lives elsewhere. Tests never run
the real executor or injector.
