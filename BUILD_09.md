# Build 09: demo-stable

24 October 2026. Local branch `demo-stable`, based on `2a7b83c5`.
This is the checkpoint demonstration line; no changes are pushed.

## Included

- `docsport`, merged with `--no-ff`: documentation, PowerShell/bash wrappers,
  preflight, morning checks, retained-report validation and regression gates.
- `knowledge`, merged with `--no-ff`: runbooks, service catalogue, SQLite-backed
  rank-bm25 retrieval, incident memory and optional graph nodes. The merge kept
  the integration-state response logic; only knowledge wiring was added there.
- `aa89109d`, cherry-picked as `cb6ef9c7b`: approval surface/mode/token identity,
  truthful rendering and correction of historical automated approvals.
- Two knowledge-addendum corrections: explicit rejection of `kb:`/`mem:` hints
  in telemetry evidence, and opaque memory identities. Stable SHA-256 memory IDs
  allow an outcome update without storing incident IDs, run IDs or report paths.
  The index rejects legacy records carrying those fields.
- Small integration fixes: knowledge test fixtures include test approval
  provenance; the operator-only preflight manifest has an exact scan exemption;
  preflight reads the attempt database when the fold-only state CLI is absent;
  PowerShell accepts `--svc` as well as `-Service`.

## Offline verification

`pytest -q -ra`: **770 passed, 3 skipped, 9 xfailed** (49.99 seconds).
Additional approval-provenance and shell portability checks: **32 passed**.
Retained report sweep before fresh rehearsals: **25/25 passed**.
Knowledge build: **15 runbooks, 23 services, 143 chunks**, no prior memories.
The disposable Linux gate was stopped at its five-minute preparation limit
(exit 137), after copying evidence and installing dependencies; pytest did not
produce a result. Linux portability is therefore **not verified**.

The three skips are two optional exported-live-fixture tests and Windows symbolic
link creation. The nine strict expected failures remain visible:

1. Synthetic-client latency exclusion.
2. Dedicated telemetry-outage alert.
3. Stopped load generator treated as traffic state.
4. SERVER-only latency query.
5. Reset of unjournaled resource changes.
6. Duplicate-alert investigation latch.
7. Separately risked proposals for independent causes.
8. Full 150-second watcher budget (current watcher caps at 90 seconds).
9. Spanmetrics and traces counted as one evidence family.

The opaque-memory regression is now a passing test, not an expected failure.

## Fresh live verification

Blocked before injection. Record every attempt, including failed preparations and retries. Agent
seconds and whole-wrapper seconds are distinct. Checkpoint 2 acceptance requires
the expected component/category, confidence >=0.75, status `diagnosed`, and agent
time below 120 seconds. Cache is recorded without claiming reliable acceptance.

| Bundle | Knowledge | Component / category | Confidence | Agent s | Wrapper s | Status | Approval | Cleanup |
|---|---|---|---|---|---|---|---|---|
| Payment, repetitions 1 and 2 | Planned ON | Not measured | — | — | — | Not run: readiness blocked | None | No injection |
| Recommendation, repetitions 1 and 2 | Planned ON | Not measured | — | — | — | Not run: readiness blocked | None | No injection |
| Cache, repetition 1 | Planned ON | Not measured | — | — | — | Not run: readiness blocked | None | No injection |
| Payment Checkpoint 3 | Not selected | Not measured | — | — | — | Not run: readiness blocked | None | No injection |
| BLOCK demonstration | N/A | Not measured | — | — | — | Not run: correct UI unavailable | None | No mutation |

There are no fresh incident run IDs to substitute into presenter documents yet.
The source default remains knowledge **OFF** until the required live repetitions
establish a demo default; this is a provisional choice, not a fresh live pass.

No retrieval-improvement or unseen-family claim follows from repeated cases.
The pre-registered nine-arm ablation remains a separate, unexecuted protocol.

## Environment and operational records

The stack endpoint is `DOCKER_HOST=tcp://localhost:2375`. The official demo checkout
is unchanged. `faultctl up` remounted the control overlay from this worktree.
The new local `.venv` was rebuilt with `uv venv .venv` and
`uv pip install --python .venv/Scripts/python.exe -e '.[test]'`.
Models and credentials are loaded from `.env`; no credential values are logged.

This machine's HTTPS interception requires Windows certificate trust. A local
`.venv/Lib/site-packages/incident_zero_system_trust.pth` contains
`import truststore; truststore.inject_into_ssl()`. TLS verification stays enabled;
this environment-only file is ignored, and must be recreated if the venv is rebuilt.
The provider catalogue then returned HTTP 200. This did not change router logic.

Initial preflight: 22/26, with failures for the old UI process, a new/empty action
database, certificate trust, and less than 2 GiB free host RAM. These are recorded
as preparation failures, not diagnosis runs. The certificate fix is verified and
demo-stable's action database has been initialized. Final readiness remains
blocked: PID 8624 owns port 8787 and serves the excluded worktree; free host RAM
was 0.78 GiB after stopping the optional Linux check (required: >2 GiB).

Automatic approval review rejected stopping PID 8624 because the user excluded
its worktree. Explicit permission to replace that process was requested; the old
server has been left running; no source files in the other worktree were edited. A separate request
asks the operator to free RAM or name an app that may be closed. No readiness
threshold or live approval gate has been bypassed.

Final operator reset and clean observation completed successfully: **182.617 s**,
all sampled error rates cleared with live traffic and running containers.
There are **21 running containers** and no `STOP` file. The ignored local record
is `.build/stable09-clean-preparation.json`; this is a cleanup observation, not
an incident diagnosis or remediation acceptance run.

## Deliberately excluded from the fold

The later fold regressed stopped-container/cache investigations to `unknown` at
the 240-second deadline according to the integration handoff. It is not merged
into this line. That regression is the reason for preserving the last known-good
brain, not a claim that the deferred hardening lacks value.

Excluded changes include `f126dccaf` brain budgets, topology/freshness/coverage
and confidence changes; `8ed43310e` revised verification, rollback and durable
operator controls; `bfcede1d2` broader knowledge corrections; and the later
`aac0eca9e` combined fold. No experimental files from the other worktree are used.
Only approval provenance was selected from that history.

Consequently this line does not claim the fold's 240-second end-to-end guarantee,
new evidence-family calibration, per-hint verdict UI, FTS5 migration, one-time
browser codes, state repair CLI, new unknown-traffic rollback semantics or broad
multi-fault acceptance. Historical rollback/STOP/browser records remain historical.
The two requested knowledge boundaries are the only addendum features added here.

## Hygiene and morning commands

History check before the live runs: zero `Co-Authored-By` trailers; all author and
committer identities are `Yash Verma <pes1ug23am910@pesu.pes.edu>`. No tracked
`.env`, `.specs`, `.build` or `runs` paths. Live flag selection is still blocked.

After replacing the old UI with permission and freeing >2 GiB RAM, run from
`D:\incident-zero-stable`. In a separate PowerShell terminal:

```powershell
Set-Location D:\incident-zero-stable
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DOCKER_CONFIG = "$PWD/.build/docker"
$env:INCIDENT_ZERO_KNOWLEDGE = '0' # provisional; replace only after live acceptance
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
scripts/ui.ps1 -Mode real
```

At 08:15 in the operator terminal:

```powershell
Set-Location D:\incident-zero-stable
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DOCKER_CONFIG = "$PWD/.build/docker"
$env:INCIDENT_ZERO_KNOWLEDGE = '0' # provisional, not live-certified
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
scripts/morning.ps1 -NoSmoke
if ($LASTEXITCODE -ne 0) { throw 'Morning checks failed; inspect their records.' }
scripts/checkpoint2.ps1 payment-failure
if ($LASTEXITCODE -ne 0) { throw 'Checkpoint 2 failed; inspect the report.' }
scripts/checkpoint3.ps1 payment-failure
```

Type `yes` only after reviewing the actual dry-run plan. These scripts include
measured clean/recovery windows; runtime exceeds the agent investigation time.
