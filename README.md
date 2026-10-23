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
