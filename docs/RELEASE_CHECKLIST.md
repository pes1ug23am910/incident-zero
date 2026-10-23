# Release checklist

A successful command ticks only its own gate. A FAIL or missing record means
**not ready**, never an implied pass. `scripts/release_check.ps1` runs gates
1, 5, 6 and 9 and prints all ten with ticks; bash can invoke
`python -m scripts.release_check`. Logs and JSON/Markdown summaries go under
`.build/release/`. It performs no live injection, approval or reset.

| Gate | Script / exact command | Evidence needed |
|---|---|---|
| 1. Offline suite | `scripts/release_check.ps1 -Gate 1` | All offline tests pass; strict xfails disclosed, removed when fixed |
| 2. Live readiness | `scripts/preflight.ps1` / `bash scripts/preflight.sh` | Complete PASS under `.build/preflight/`, including clean detector, fresh tools/model, no STOP/attempt/cooldown, fresh real UI and resources |
| 3. Three diagnoses | `scripts/checkpoint2.ps1 payment-failure`; `scripts/checkpoint2.ps1 container-stopped -Service recommendation`; `scripts/checkpoint2.ps1 cache-unavailable` (bash twins) | Fresh bundles on final prompt hash, correct causes/coverage and measured cleanup; old cache escalation does not pass |
| 4. Full loop / real approval | `scripts/checkpoint3.ps1 payment-failure`, then a separate run with `-BrowserApproval` (bash twins) | Real typed yes and browser code, honest surface/mode, bound action log, qualified verification and cleanup |
| 5. Portability | `scripts/crossplatform_check.ps1` / `bash scripts/crossplatform_check.sh` | Linux python:3.11 copied-source offline result; Git Bash help/preview; second laptop follows README literally before declaring that separate result |
| 6. Schema sweep | `scripts/release_check.ps1 -Gate 6` / `python -m scripts.validate_reports` | Calls `schema.validate.validate_report` for every `reports/*/report.json` with its own checksummed snapshot resolver; no live-health claim or silently omitted bundle |
| 7. Blind audit | `git archive --format=tar HEAD -o .build/release-snapshot.tar` then independent audit | Snapshot revision and findings for agent/action_api/detect/tools changes; no script can self-certify an independent audit |
| 8. Claim/evidence review | `git diff -- README.md docs/` then manual read-through | Reviewer confirms each claim has a bundle/command, otherwise says not verified; no automated tick |
| 9. Disclosure / repository hygiene | `scripts/release_check.ps1 -Gate 9` | Isolation/no-flag tests, tracked process/credential paths, configured-secret matches and commit-message/authorship counts; zero prohibited hits |
| 10. Team / prior work | `git log --format="%h %an <%ae> %s"` plus TEAM_FORM and PRIOR_WORK | Complete roster, actual member commits, tools/models, port provenance and sign-off |

At 08:15 `scripts/morning.ps1` chains preflight, payment smoke, schema sweep and
Linux portability. Tonight use `-NoSmoke` (bash: `--no-smoke`). Failed preflight
refuses the smoke even without that switch. Only the smoke may reset/inject.
Tests run in a disposable copy without credentials or live Docker access.

## Recorded docsport checks and fold handoff

Read-only preflight on 2026-10-23, 17:49/17:51 UTC: **21/25 PASS, overall FAIL**.
The idle stack had 21 running containers, zero observed traffic-service errors,
no detector alert, all five tools under 5s, resolver live round-trip and model
probe HTTP 200. Failures: inherited `INCIDENT_ZERO_TEST=1`, missing H8 state-check
CLI (read-only DB showed zero stuck/active cooldown attempts), fresh real Control
Room not verified, and available RAM below 2 GiB. No repair was attempted.

PowerShell help (`-Help`, `--help`, `-h`) and Git Bash syntax/help passed for the
eight operator/gate entry points; bash demo preview and Docker-command preview
returned 0. No up/checkpoint/live-demo execution occurred. New tests initially
returned 34 passed and 10 strict xfails; later gate results are recorded below
when executed, rather than inferred from this initial count.

The first completed Linux run returned **3 failed, 703 passed, 2 skipped,
10 xfailed**. Two failures were scanner scope for new operator-only checks and
one was the direct checkpoint default changing from 90 to 150 seconds. Direct
checkpoint compatibility has been restored; wrappers still request 150 seconds.
The operator-only readiness manifest is explicit in `scripts/preflight_checks.json`
and diagnostic imports are tested. The existing broad no-flag scanner still needs
an explicit operator-manifest exemption reviewed by the fold; do not hide it by
encoding paths, renaming data extensions or weakening the diagnostic scan.

Final executed checks on this checkout (2026-10-23 UTC; logs are local, ignored):

| Check | Actual result | Record under `.build/` |
|---|---|---|
| Final PowerShell read-only preflight, test mode cleared for this process | FAIL: 24/26; fresh real UI not verified; RAM 0.60 GiB below 2 GiB | `preflight/20261023T182419.449928Z.md` |
| PowerShell morning `-NoSmoke` | FAIL: preflight FAIL, smoke SKIP, schema PASS, Linux FAIL | `morning/20261023T181938.405174Z.md` |
| Git Bash morning `--no-smoke` | FAIL: preflight FAIL, smoke SKIP, schema PASS, Linux FAIL | `morning/20261023T182403.132946Z.md` |
| Linux python:3.11 copied-source offline suite via Bash morning | 1 failed, 706 passed, 2 skipped, 10 strict xfails | `portability/20261023T182054.949488Z.log` |
| Release gate 1, local offline suite | 1 failed, 705 passed, 3 skipped, 10 strict xfails | `release/20261023T181814.114858Z-gate1.log` |
| Release gate 6, checksummed retained-bundle validation | PASS: all 25 bundles | `release/20261023T181814.114858Z-gate6.log` |
| Release gate 9, isolation and disclosure | FAIL: same operator-manifest scanner failure; 39 tests passed; tracked process/credential paths, configured-secret matches, forbidden commit messages and unexpected authorship all zero | `release/20261023T181814.114858Z-gate9.log` |
| New test files only | 35 passed, 10 strict xfails | `tests/test_clean_stack_regressions.py`, `tests/test_regressions_oct23.py`, `tests/test_portability.py` |
| Shell entry points | All eight Bash syntax/help variants and PowerShell help variants passed; all nine PowerShell entry points including release checker also passed direct `--help`; demo previews passed | Commands documented above and tests in `tests/test_portability.py` |

The last Bash morning's preflight also encountered Git's ownership guard while
reading the official demo checkout. The final standalone preflight uses a
per-command safe-directory setting for that explicitly configured checkout and
verifies it is unchanged; it does not modify global Git settings or demo files.
The final preflight supersedes earlier readiness counts. These results do not
claim a second physical laptop was tested. No live smoke, approval or reset ran.

Strict xfail contracts (all offline):

| Test contract | Fold work needed |
|---|---|
| Synthetic-client latency/error | Exclude load-generator from service incident alerts (Addendum 5.1) |
| SERVER-only latency query | Filter latency aggregation to SERVER spans (Addendum 5.1) |
| Outage cannot be silence | Emit dedicated telemetry_outage with backend availability (Addendum 4.2) |
| Stopped load generator | Return explicit non-incident traffic state (Addendum 4.3) |
| External reset | Restore or explicitly fail read-back of unjournalled resource faults (Addendum 2) |
| Duplicate alerts | One active investigation; join repeated alerts (Addendum 3.1) |
| Two supported causes | Keep two separately risked proposals (Addendum 3.3) |
| Memory labels | Merge corrected memory; opaque IDs and no run/incident/path labels in storage/index (Knowledge Addendum 1) |
| 150-second alert budget | Extend `detect.watch.wait_for_alert` beyond the existing 90s cap (Addendum 10 H10) |
| Spanmetrics independence | Treat spanmetrics and trace/span records as the same evidence family (Addendum 3.2) |

Remove each strict xfail marker when its assertions pass; XPASS is deliberately
an error. Existing tests that assert the old behavior may also need correction
by the fold; this session owns only new test files. No final-prompt diagnosis,
human approval, nine-run ablation or six held-out rehearsal was performed here.

Public release remains a separate explicit user decision. Before it, scan all
history for process files and secrets, remove prohibited material from history,
and repeat the authorship verification. This checklist does not publish or push.
