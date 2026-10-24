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

| Bundle | Knowledge | Component / category | Confidence | Agent s | Wrapper s | Status | Approval | Cleanup |
|---|---|---|---|---|---|---|---|---|
| [stable09-payment-on-r1](reports/stable09-payment-on-r1/checkpoint2.json) | ON | Not measured | — | — | 385.541 | Runner failed before diagnosis | None | Verified |
| [stable09-payment-on-r2](reports/stable09-payment-on-r2/report.json) | ON | payment / application_flag | 0.90 | 56.851 | 540.461 | diagnosed | None | Verified |
| [stable09-payment-on-r3](reports/stable09-payment-on-r3/checkpoint2.json) | ON | Not measured | — | — | 383.041 | Preparation refused: frontend:rps | None | Verified |
| [stable09-payment-on-r4](reports/stable09-payment-on-r4/report.json) | ON | payment / application_flag | 0.95 | 38.891 | 488.305 | diagnosed | None | Verified |
| [stable09-recommendation-on-r1](reports/stable09-recommendation-on-r1/report.json) | ON | recommendation / container_down | 0.80 | 56.537 | 457.257 | diagnosed | None | Verified |
| [stable09-recommendation-on-r2](reports/stable09-recommendation-on-r2/report.json) | ON | recommendation / container_down | 0.90 | 172.794 | 571.972 | diagnosed; FAIL time limit | None | Verified |
| Cache repetition 1 | Planned ON | Not measured | — | — | — | Not run within time budget | None | No injection |
| Payment Checkpoint 3 1 | Not selected | Not measured | — | — | — | Not run within time budget | None | No injection |
| [BLOCK](reports/stable09-block/block.json) | N/A | delete_database refused | — | — | — | HTTP 403 / FORBIDDEN_OPERATION | None | No mutation |

Source/demo command default remains knowledge **OFF** (`INCIDENT_ZERO_KNOWLEDGE=0`), **provisional**. All fresh diagnosis runs used ON; no fresh OFF comparison was completed, so the retained OFF default is not a live-certified selection. These practice cases do not establish retrieval improvement or hidden-test accuracy. Sequential knowledge-ON runs can consult memory from earlier runs.

Agent seconds are `report.agent.elapsed_s`; wrapper seconds include preflight, reset, the clean windows, alert wait and validation. Acceptance requires the expected component/category, confidence >=0.75, `diagnosed`, and agent <120 s. Cache reliability is assessed separately.

Preparation is intermittent near the RAM floor. The 150s/90s wrapper mismatch was corrected; a deliberate load increase also caused a temporary `frontend:rps` baseline refusal. Neither preparation failure is evidence against the model or knowledge mode. Recommendation repetition 2 exceeded the 120-second agent limit despite a correct diagnosis; its required retry and conditional knowledge-OFF comparison were not completed. Cache was not rerun, so its current reliability is unmeasured. Overall live acceptance is **partial**, not a full pass.

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

Earlier preparation finished at 22/26: the stale UI, empty action database,
certificate trust and the former 2 GiB RAM floor blocked readiness. The previous
session's review rejection concerned stopping a process in the excluded worktree;
that process was already gone when this acceptance started. This session did not
stop or edit anything in that worktree.

The real UI was started through `scripts/ui.ps1 -Mode real -Port 8787`, hidden in
the background (launcher PID 21380, server PID 34060). The RAM gate was changed
to **at least 1 GiB**, as authorized; all other readiness gates are unchanged.
Initial live attempts measured 0.75 and 0.71 GiB; the second also observed a
checkout p95 spike (1880 ms, zero application errors). Operator reset and a full
clean observation completed in **182.4 s**. No incident had been injected.

Preflight **26/26 PASS** at **07:21 IST** (`20261024T015143.044701Z`, 1.04 GiB
free). The first checkpoint preparations then failed RAM at 0.76 and 0.95 GiB,
before reset/injection. Removing redundant launcher shells reduced memory use;
the unchanged wrapper preflight passed **26/26** at **07:24 IST**
(`20261024T015420.816260Z`, 1.08 GiB free). These preparation attempts are retained
in [preparations.json](reports/stable09-preflight/preparations.json), separate
from incident outcomes. Existing wrapper/readiness tests: **22 passed**.

The first injected payment attempt exposed an entry-point mismatch: wrappers
requested 150 seconds, while this branch's watcher accepts at most 90 seconds.
It failed before diagnosis and reset cleanly; its full wrapper time was
**385.541 s**, with **181.774 s** verified cleanup. Checkpoint 2, Checkpoint 3
and the shell help now use 90 seconds; unsupported explicit budgets are rejected
before mutation. The 150-second watcher extension remains deferred. Affected
wrapper, checkpoint and hands tests: **73 passed**, including the new regression.

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

All work remains local; nothing is pushed. The demo command's knowledge mode
remains OFF provisionally because the required retry/OFF comparison is unfinished. The real
Control Room must be running from this worktree, with test mode unset.

At 08:15, from the operator terminal (the Control Room is already running):

```powershell
Set-Location D:\incident-zero-stable
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DOCKER_CONFIG = "$PWD/.build/docker"
$env:INCIDENT_ZERO_KNOWLEDGE = '0' # provisional; fresh OFF comparison is unfinished
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
foreach ($name in 'OPENROUTER_MODEL','OPENROUTER_FALLBACK_MODEL','GEMINI_MODEL') {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}
scripts/preflight.ps1
if ($LASTEXITCODE -ne 0) { throw 'Preflight failed; inspect its record.' }
scripts/checkpoint2.ps1 payment-failure
if ($LASTEXITCODE -ne 0) { throw 'Checkpoint 2 failed; inspect the report.' }
scripts/checkpoint3.ps1 payment-failure
if ($LASTEXITCODE -ne 0) { throw 'Checkpoint 3 failed; inspect the report.' }
```

Review the actual plan, then type `yes` at the Checkpoint 3 prompt. A person
entering this decision is human CLI approval; automated terminal input in an
acceptance run must be labelled separately. Do not substitute test approval.
The wrappers use a supported 90-second alert wait and retain full clean/recovery
windows; total runtime is longer than agent investigation time.

If the UI needs starting, use a separate PowerShell terminal with the same
Docker/knowledge environment and test mode unset:

```powershell
Set-Location D:\incident-zero-stable
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DOCKER_CONFIG = "$PWD/.build/docker"
$env:INCIDENT_ZERO_KNOWLEDGE = '0' # provisional; fresh OFF comparison is unfinished
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
scripts/ui.ps1 -Mode real -Port 8787
```

Do not change load immediately before the demonstration: a large increase
needs its ten-minute detector history to settle. Checkpoint 3 measures its own
20-user baseline and restores the prior workload during cleanup.
The 70-minute run stopped short of Checkpoint 3: its three separate minimum
180-second windows would not fit the remaining time after recommendation cleanup.
No typed CLI approval, execution or live repair recovery is claimed. Only the
forbidden-operation BLOCK was exercised. The source default remains OFF, without
a new OFF acceptance result. The Control Room was restarted with this provisional
OFF mode (launcher PID 45740); only its verified worktree-owned predecessor was stopped.

## Final acceptance state

**PARTIAL.** Latest preflight: **FAIL preflight 20261024T025443.856202Z: 23/26 checks**. clean detector: alerts: checkout:p95_ms; traffic health and baseline: 12 traffic services; nonzero errors/missing baseline/high p95: ['checkout']; RAM: 0.91 GiB free; needs >=1

Final reset/clean observation: **182.547 s**, verified. Original load (5 users, spawn rate 1) restored; 21 containers running, pristine flags and no STOP. The clean observation checks traffic, containers and error rates; it does not override the final RAM/latency readiness failures. The real Control Room remains running in provisional knowledge-OFF mode (server PID 25576).

Affected tests: **73 passed**. Retained report validation: **29/29 passed**. No approval token or repair execution was created in this session. BLOCK returned HTTP 403 with `FORBIDDEN_OPERATION` on both real-UI checks; its action-log excerpt is [retained here](reports/stable09-block/action-log.jsonl). Recommendation retry, conditional OFF comparison, cache and Checkpoint 3 remain unfinished.
