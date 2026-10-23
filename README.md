# Incident Zero - AI On-Call Engineer

Incident Zero detects anomalies in the OpenTelemetry Demo, investigates them
through read-only tools, and writes evidence-backed diagnoses in the team's
schema. This session builds the brain for Checkpoint 2. It proposes actions and
assesses their risk; **no proposed action is executed**. The Action API, actual
human approval tokens, execution, verification and rollback are a later session.

See [BUILD_01B.md](BUILD_01B.md) for earlier live telemetry verification,
[BUILD_04.md](BUILD_04.md) for the diagnosis ledger, and
[the checkpoint brief](docs/CHECKPOINT2_BRIEF.md) for the three live presentations.
A configured model or a passing unit test is not a verified live diagnosis.

## Setup

Use Python 3.11 or newer, Docker Desktop with Linux containers, and the official
demo 2.0.2 checkout at `D:\opentelemetry-demo`. Its minimal Compose file has
**21 services**. Keep that checkout unmodified.

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

Reuse an existing environment; recreate a missing one from the commands above.
If a storage-cleanup notice exists in the checkout, follow its rebuild command.
`scripts/up.ps1` automates environment setup, stack startup and readiness.
`INCIDENT_ZERO_DEMO_DIR` selects a different demo checkout.

The collector's Docker statistics receiver uses API 1.25. This laptop's daemon
compatibility fix is documented in BUILD_01B.md; check
`docker version --format '{{.Server.MinAPIVersion}}'` if collector export fails.
Do not treat missing application metrics as a healthy system. Repository scripts
do not change daemon configuration.

Both entry points are installed:

```powershell
.\.venv\Scripts\python.exe -m faultctl list
.\.venv\Scripts\faultctl.exe list
```

## Model configuration

Keep credentials in the ignored local `.env` or process environment. Do not print
or commit keys. Existing process values override `.env`. Set these model names
explicitly; runtime code does not supply hidden model defaults.

| Variable | Role / value |
| --- | --- |
| `OPENROUTER_API_KEY` | Local OpenRouter credential |
| `OPENROUTER_MODEL` | Primary: `openai/gpt-5` |
| `OPENROUTER_FALLBACK_MODEL` | OpenRouter fallback: `google/gemini-2.5-pro` |
| `GEMINI_API_KEY` | Optional direct-provider fallback credential |
| `GEMINI_MODEL` | Direct-provider model, for example `gemini-2.5-pro`; **must be configured** for that route to exist |
| `OPENROUTER_FAST_MODEL` | `openai/gpt-5-mini`, reserved for cheap helpers; the investigation does not route to it |
| `REVIEWER_MODEL` | `google/gemini-2.5-pro`, reserved for a future reviewer; no reviewer is implemented |

OpenRouter requests medium reasoning effort. Routing tries the configured primary,
then its OpenRouter fallback, then direct Gemini when both its key and model are
set. Transient failures are retried once before falling back. The report and
sanitized `llm.jsonl` identify the model that actually succeeded, token usage and
a reference estimate using $1.25/M input and $10/M output tokens. This reference
estimate is not a provider invoice or the actual price of every fallback model.
Temperature 0 and logged prompts make inputs reproducible, not outputs.

## Diagnose an incident

Run one rehearsal at a time. The single command resets, waits for clean telemetry,
records a baseline, injects, waits up to 90 seconds for an alert, runs the agent,
validates and prints the Markdown report, then resets and waits for error rates
to clear. It prints elapsed seconds for every stage and attempts final cleanup
even if a stage fails.

```powershell
.\scripts\checkpoint2.ps1 payment-failure
.\scripts\checkpoint2.ps1 container-stopped -Service recommendation
.\scripts\checkpoint2.ps1 cache-unavailable
.\scripts\checkpoint2.ps1 cpu-starve -Service recommendation
```

The first three are the checkpoint cases; the fourth demonstrates abstention.
Run them in that order before further practice cases. The required repetition
count and actual outcomes belong in BUILD_04.md. The script generates a unique
report-bundle name; use `-ReportId <unique-name>` when you need a chosen name.
Existing bundles are never replaced. Error-rate clearance is checked for at
least 180 seconds with 30-second samples; a reset exit code alone is insufficient.

For a detector-managed investigation:

```powershell
.\.venv\Scripts\python.exe -m detect.watch --interval 10 --thresholds detect/thresholds.yaml
```

The watcher writes an alert and starts the investigator unless STOP is present.
`--no-agent` observes without starting investigations. For an existing alert:

```powershell
.\.venv\Scripts\python.exe -m agent.run --alert runs/<run-id>/alert.json --incident-id <report-id> --out reports/<report-id>/report.json
.\.venv\Scripts\python.exe -m schema.validate reports/<report-id>/report.json
.\.venv\Scripts\python.exe -m reports.render reports/<report-id>/report.json
```

Replace placeholders with actual paths. `python -m agent run ...` is also
supported. The incident ID labels output only; it never enters the model prompt.
`python -m detect.once` prints one alert with its saved path, or an explicit
`no_alert` result. An empty/missing backend response is not proof of no incident.

Creating a root `STOP` file stops further investigation and refuses injection
or resumption; operator reset remains available. A paused graph can record a
rejection with `python -m agent.respond --report reports/<report-id>/report.json
--reject`. Approval and execution are unavailable in this brain build.

## How the agent decides

The LangGraph StateGraph runs observe -> investigate -> diagnose -> assess_risk
-> propose. Observe always calls health_table across known services. The model
selects one structured read per iteration, with a reason, from metrics, traces,
logs, container health and deploy history. The total budget is 12 tools.

Tool payloads are treated as untrusted data. Redaction removes incident-setting
disclosures before prompting or snapshotting. Code rejects invented evidence IDs,
checks component support, and computes evidence confidence from independent
positive sources and signal magnitude. Final confidence is the minimum of model
and evidence confidence. The action type is selected in code from the cause
category; targets must be known services.

The loop retains multiple causes and tracks symptoms still unexplained through
the dependency graph. Caller symptoms may follow from a dependency failure;
independent failures remain separate causes. Reports contain confidence-ordered
`root_causes`, the first-cause `root_cause` alias, limitations, and impact before
any proposed actions. Confidence below 0.6 or unsupported remedies escalate.
A clean finding requires observed healthy traffic, not merely absent errors.

Tier 1 is for a single auxiliary/core service, a reversible proposal and confidence
at least 0.75; its future quick approval must show action, target and effect.
Critical services and restarts require tier 2 review. Tier 3 suppresses proposals
for multiple independent failures, unsafe data risk or inadequate confidence.
`auto_approve_tiers` remains empty. See [WHY.md](docs/WHY.md) for the rationale.

Eligible proposals reach a separate local preview and an approval interrupt.
`SqliteSaver` persists `runs/checkpoints.sqlite` with `thread_id = run_id`.
The responder requires the exact saved approval node before resuming. Even direct
approval resumption reaches an inert execute node in this build; recovery is not
claimed. Local checkpoints are needed for resumption even when report evidence
has been retained separately.

## Telemetry and retained reports

Prometheus is at `http://localhost:9090`. Jaeger's API is available through
`http://localhost:8080/jaeger/ui/api`; its direct host port and OpenSearch's host
port are ephemeral. Tools discover the OpenSearch port, and logs use index
`otel`. See [metrics](tools/METRICS.md) and [log fields](tools/LOGS.md).

Docker stdout/stderr supplies missing application logs with `dlog:` IDs.
Payment also falls back to Docker when OpenSearch has no matching records.
Use `--severity-min TRACE` to include unclassified stdout. Rate windows are at
least two minutes because spanmetrics flushes about once a minute.

Every cited payload is snapshotted in `runs/<run-id>/evidence/`. Windows-safe
filenames are SHA-256 digests; each record keeps the full ID and a checksum.
Finished bundles under `reports/<report-id>/` contain report JSON and Markdown,
the alert, sanitized LLM log, graph events, evidence copies, and the action-log
excerpt. That excerpt is empty in this session because no action ran.

The resolver tries live evidence, then run snapshots, then an explicitly selected
report bundle, reporting the origin. Snapshots preserve observations, not current
recovery. For retained evidence after run expiry:

```powershell
.\.venv\Scripts\python.exe -m tools.resolve '<evidence-id>' --run-dir runs/<run-id> --bundle-dir reports/<report-id>
.\.venv\Scripts\python.exe -m schema.validate reports/<report-id>/report.json
```

The [team schema](schema/README.md) is primary. The
[external mapping adapter](schema/MAPPING.md) is identity until another schema
is supplied. Export with:

```powershell
.\.venv\Scripts\python.exe -m schema.export reports/<report-id>/report.json --schema <their-schema.json>
```

This retains report.json and writes validated report.external.json alongside it.
Unmapped output fields are dropped; required unavailable values are explicitly
marked with notes. Unrepresentable required values make export fail visibly.
The agent also accepts `--external-schema` to keep both files during bundling.

## How incidents are injected

The minimal demo has no writable control API. The operator's faultctl changes a
local copy of `src/flagd/demo.flagd.json`, mounts that copy using a repository-owned
Compose override, and checks the applied state. It does **not** edit the file in
`D:\opentelemetry-demo`. The original source is read only to preserve and verify
pristine bytes. Only the injection package accesses those settings for rehearsal.

Infrastructure incidents use scoped Docker operations or a temporary NET_ADMIN
helper. Reset restores the original mount and limits, starts stopped components,
removes network impairment, and verifies cleanup. After every reset, the official
checkout must be clean:

```powershell
.\.venv\Scripts\python.exe -m faultctl reset
git -c safe.directory=D:/opentelemetry-demo -C D:\opentelemetry-demo status --porcelain
```

This overlay is the implemented boundary for the requirement to leave the demo
unmodified. An instruction describing an in-place source edit does not describe
this implementation. The checkpoint script additionally waits for live error-rate
clearance after reset before declaring the stack clean.

## Tests and prior work

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Offline fixtures verify inference and safety properties without mutating the
demo. Live results, failed attempts, model choices and calibration belong in
BUILD_04.md and [EVALUATION_NOTE.md](docs/EVALUATION_NOTE.md); no unit-test result
substitutes for those measurements.

The mentors permitted Yash Verma's unpublished prior code with a declaration.
Only environment-loading and provider/retry structure from the prior LLM router
were adapted into `agent/llm_router.py`; see the file-by-file
[prior-work record](docs/PRIOR_WORK.md). No prior prompts, documents, reports or
build outputs were copied. Team disclosures belong in [TEAM_FORM.md](docs/TEAM_FORM.md).

Credentials, runtime state, injection journals, local environments and private
specifications remain ignored. Report bundles are retained for review.
