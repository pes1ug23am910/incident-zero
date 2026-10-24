# Incident Zero - AI On-Call Engineer

This is the integrated team repository for an AI on-call engineer on the official
OpenTelemetry Astronomy Shop demo: telemetry tools, detector, investigation,
Action API, approval interface, operator scripts and retained reports. The earlier
GitHub **agent-only subset** lacks the hands/Action API, integrated Control Room,
retained reports and this setup guide; it cannot demonstrate the full
approval-to-recovery loop. Use the integrated checkout for the demo.

Historical outcomes and failures are in [the evaluation note](docs/EVALUATION_NOTE.md).
Live recoveries so far were approved through the test harness; a human-approved
run is scheduled at 09:30. The later browser run was automated acceptance, not a
person approving. Real human CLI and browser approval remain **not verified**.

## Setup and run

Use Python 3.11, Docker with Compose v2, and PowerShell 7 or bash. The official
demo is a sibling checkout at tag `2.0.2`, using `docker-compose.minimal.yml`.
Pin `DEMO_VERSION=2.0.2`: the tag's `latest` setting can select incompatible 3.x
images. The measured minimal stack has 21 containers ([BUILD_01B](BUILD_01B.md)).
Preflight requires more than 5 GiB free disk and at least 1 GiB available RAM.

**Docker daemon prerequisite:** if the collector reports that API 1.25 is too
old, merge `"min-api-version": "1.24"` into the Docker Engine `daemon.json`
settings and apply/restart Docker before starting the stack. Preserve other
settings. This is a host prerequisite, not a demo configuration edit. Confirm
the venue's allowance with the mentor. Never restart Docker while another
session owns the stack.

PowerShell, from the integrated checkout:

```powershell
git clone --branch 2.0.2 --depth 1 https://github.com/open-telemetry/opentelemetry-demo ../opentelemetry-demo
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e '.[test]'
$env:DEMO_VERSION = '2.0.2'
# This laptop's already-configured endpoint only:
$env:DOCKER_HOST = 'tcp://localhost:2375'
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
./scripts/up.ps1 -DemoDir ../opentelemetry-demo
# Separate terminal; start a fresh process after code changes:
./scripts/ui.ps1 -Mode real -Port 8787
```

Bash:

```bash
git clone --branch 2.0.2 --depth 1 https://github.com/open-telemetry/opentelemetry-demo ../opentelemetry-demo
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
export DEMO_VERSION=2.0.2
unset INCIDENT_ZERO_TEST
# Git Bash on this demo laptop only: export DOCKER_HOST=tcp://localhost:2375
bash scripts/up.sh --demo-dir ../opentelemetry-demo
# Separate terminal:
bash scripts/ui.sh --mode real --port 8787
```

For Git Bash on Windows, create/install the venv using the PowerShell block;
wrappers find `.venv/Scripts/python.exe`. On Unix they find `.venv/bin/python`.
`INCIDENT_ZERO_PYTHON` overrides the bash interpreter. For an existing uv venv
without pip, install with `uv pip install --python .venv/Scripts/python.exe -e
'.[test]'`. `INCIDENT_ZERO_DEMO_DIR` overrides the sibling demo path. All wrappers
preserve `DOCKER_HOST`; when unset they choose the Windows named pipe or Unix
Docker socket. They do not enable a Docker listener.

Keep keys and model IDs in ignored `.env` or process variables:
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_FALLBACK_MODEL`; optional
direct Gemini uses `GEMINI_API_KEY` and `GEMINI_MODEL`. Process values take
precedence. Preflight checks the configured models without printing keys.

After the real Control Room is listening at **http://127.0.0.1:8787**:

| Purpose | PowerShell | bash |
|---|---|---|
| Read-only readiness | `scripts/preflight.ps1` | `bash scripts/preflight.sh` |
| Morning without injection | `scripts/morning.ps1 -NoSmoke` | `bash scripts/morning.sh --no-smoke` |
| Morning with payment smoke | `scripts/morning.ps1` | `bash scripts/morning.sh` |
| Payment diagnosis | `scripts/checkpoint2.ps1 payment-failure` | `bash scripts/checkpoint2.sh payment-failure` |
| Stopped recommendation | `scripts/checkpoint2.ps1 container-stopped -Service recommendation` | `bash scripts/checkpoint2.sh container-stopped --svc recommendation` |
| Human-approved loop | `scripts/checkpoint3.ps1 payment-failure` | `bash scripts/checkpoint3.sh payment-failure` |
| Browser approval | add `-BrowserApproval` | add `--browser-approval` |
| Demo preview / execute | `scripts/demo.ps1` / add `-Live` | `bash scripts/demo.sh` / add `--live` |
| Linux offline suite | `scripts/crossplatform_check.ps1` | `bash scripts/crossplatform_check.sh` |

Checkpoints reset and inject real incidents: exclusive stack ownership is required.
Preflight never repairs failures. `morning --no-smoke` skips its only stack-changing
step; it still probes the model, validates reports and launches an isolated Linux
test container. Every entry point accepts `-Help`, `--help` and `-h` with exit 0.
For organiser-injected incidents run `python -m detect.watch --interval 10`;
duplicate-investigation handling still needs the fold regression fix.

**Latest acceptance preflight: PASS, 26/26 at 08:45 IST on 24 October.**
The stopped-recommendation demo default is **knowledge OFF**: set
`$env:INCIDENT_ZERO_KNOWLEDGE = '0'` before its PowerShell command (bash:
`export INCIDENT_ZERO_KNOWLEDGE=0`). The single fresh OFF run diagnosed
`recommendation / container_down` at **0.90 confidence in 59.673 s** agent time.
This morning's ON runs were **0.80 / 56.537 s** and **0.90 / 172.794 s**
(rounded **0.80 / 57 s**, **0.90 / 173 s**); the second exceeded the <120 s gate.
OFF therefore has a fresh passing rehearsal for this case; one run does not
establish general superiority or reliability. Cache was skipped because fewer
than nine minutes remained before the 08:57 handoff. See [BUILD_10](BUILD_10.md)
for timings and handoff evidence, and [BUILD_09](BUILD_09.md) for earlier partial
acceptance. Human-approved Checkpoint 3 remains the operator's 09:00 run.

## Approval gate and kill switch

The Action API allowlists `restart_service`, `toggle_flag` and `throttle_load`.
Scaling returns `NOT_AVAILABLE_ON_COMPOSE`. Preview shows the target, predicted
effect and risk. Approval binds a single-use, expiring token to the plan, report,
operator and world; execution rechecks it. Tier 2 requires typed `yes`. Wrappers
refuse `INCIDENT_ZERO_TEST=1`. Removing the legacy ability for test approval to
drive live writes and correcting approval provenance are fold safety gates.

Set STOP with `python -m action_api stop --operator "Yash Verma"`, or create the
root file (`New-Item STOP` / `touch STOP`) when the API is unavailable. Clear it
after reviewing the incident with `python -m action_api clear-stop --operator
"Yash Verma"` and the phrase `I confirm the incident is over`. STOP blocks new
changes and interrupts waits; it cannot undo a command already accepted by Docker.

Verification lasts at least 180 seconds and requires two fresh healthy samples
with traffic. Baseline-relative traffic and actual sample-age checks are fold
requirements; merged live behavior is not verified. Unknown verification must
escalate without automatically re-enabling a failure switch. Historical rollback
bundles used older behavior. Approval records must include operator, surface
(`cli`, `browser`, `test`), mode (`live`, `test`), timestamp and token ID.

## Knowledge and limitations

[KNOWLEDGE.md](docs/KNOWLEDGE.md) explains runbooks, the service catalogue and
incident memory. That branch exists; its corrected FTS5/BM25 integration is fold
work. No retrieval accuracy improvement is claimed; the nine-run ablation is empty.

Confidence is heuristic, not calibrated probability. Spanmetrics and traces share
the same source observations; correcting historical independence scoring is a
fold gate. Aggregate metrics hide rare operations. The detector can misclassify
synthetic-client latency and unavailable telemetry; one clean recording is not
proof for every laptop. Ten strict xfails document outstanding regressions.

The optional reviewer is **built, not live-verified**. It is off by default;
`INCIDENT_ZERO_REVIEWER=1` enables it before risk assessment and proposals.
`REVIEWER_MODEL` comes from the environment / `.env` and must be a vendor-qualified
OpenRouter model from a different vendor than every primary model used. No model
ID is hardcoded and reviewer fallback is disabled. It can request up to three
additional reads through the existing telemetry tools (separate from the primary
12-call investigation budget), then records
`review {verdict, objections, extra_evidence}` in JSON and Markdown. An
evidence-citing objection that stands caps the affected cause below 0.60 and
suppresses proposals; review never raises confidence or overwrites original model
and evidence scores. Reviewer model requests are retained in `review-llm.jsonl`;
additional snapshots are retained with the bundle. An unavailable or invalid
review is disclosed, with confidence unchanged. Primary offline replay disables
new reviewer calls; replay of reviewer decisions is not implemented. The live
session must enable the switch, verify the configured vendor differs, run a fresh
diagnosis without approving execution, and inspect the reviewer transcript,
at-most-three reads, resolvable evidence, schema-valid bundle and non-increasing
confidence. Exercise a supported objection to confirm escalation/no proposal,
and a no-objection case to confirm confidence stays unchanged; record latency and
provider failures before claiming live verification.

The allowlist cannot remove packet loss, resource caps or external restart loops.
A toggle can affect several switches for one service; restart has irreversible
process effects. Snapshots prove retained observations, not present health. The
API trusts the same user on localhost, not a multi-user identity service. One-time
browser codes, unknown-verification handling and stuck-attempt recovery need fold
fixes. Organiser schema, hidden-test accuracy, second-laptop setup and a complete
timed live presentation are not verified.

| Symptom | Check / next step |
|---|---|
| Low free RAM | 16 GB laptop with Docker Desktop: 1 GiB free is the realistic floor; below that, close browsers |
| Collector restart-loop / old API | `docker logs otel-collector`; apply the daemon prerequisite before starting |
| Jaeger proxy-only | Set `JAEGER_URL=http://localhost:8080/jaeger/ui/api`; tools try the published port first |
| OpenSearch ephemeral port | `docker port opensearch 9200`; tools discover it, or set `OPENSEARCH_URL` |
| Images/attributes differ | Pin `DEMO_VERSION=2.0.2`; do not use 3.x `latest` |
| Missing venv/imports | Install `.[test]`; respect any local storage-cleanup notice |
| Stuck attempt/cooldown | After the fold: `python -m action_api.state check`; review/resolve or wait, never delete the DB |
| Fresh Control Room unverified | Restart real mode after source changes; preflight checks Windows listener start time or API revision/start metadata |
| No alert/provider unavailable | Retain failure; show a labelled recorded bundle, never lower thresholds or invent output |
| Public-image credential helper error | Use an isolated anonymous Docker configuration; preserve normal credentials |
| Fresh pytest needs ignored `.build` | Create `.build` and use `--basetemp=.build/pytest`, or the Linux gate's `/tmp` base; plain fresh-clone pytest remains H13 fold work |
| Slow Linux gate copy | Many retained evidence files are copied from the read-only mount before testing |

Deliverables: [architecture](docs/ARCHITECTURE.md), [reports](reports/),
[evaluation](docs/EVALUATION_NOTE.md), [team form](docs/TEAM_FORM.md).
Also see [release gates](docs/RELEASE_CHECKLIST.md),
[checkpoint answers](docs/CHECKPOINT_ANSWERS.md), [demo](docs/DEMO_SCRIPT.md),
[fault grammar](docs/FAULTCTL.md) and [prior work](docs/PRIOR_WORK.md).
