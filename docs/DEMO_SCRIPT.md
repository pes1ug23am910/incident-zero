# Demo script v2: five minutes, with honest preparation

The full reset-to-cleanup rehearsal takes longer than five minutes. Historical
payment loop r3 took 346.016 seconds from injection to response completion;
recommendation loop r1 took 609.922 seconds. Prepare the real alert and diagnosis
before starting the presentation clock. Never shorten the 180-second verification
window. A complete timed five-minute rehearsal is **not verified**.

## Before presentation, exclusive stack owner only

At 08:15 run `scripts/morning.ps1` or `bash scripts/morning.sh`. For read-only
work use `-NoSmoke` / `--no-smoke`. Require preflight PASS, review attempts/cooldown,
remove test mode from the operator shell and start a fresh real Control Room after
code changes. Do not clear STOP or resolve an attempt without reviewing its cause.

Use the interpreter installed in README. PowerShell:

```powershell
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
./scripts/ui.ps1 -Mode real -Port 8787
# Another terminal, after preflight passes:
./scripts/demo.ps1 -Live -Incident payment-failure -ReportId mentor-payment-01
# To approve only in the browser, add -BrowserApproval.
```

Bash:

```bash
unset INCIDENT_ZERO_TEST
bash scripts/ui.sh --mode real --port 8787
# Another terminal:
bash scripts/demo.sh --live --incident payment-failure --report-id mentor-payment-01
# To approve only in the browser, add --browser-approval.
```

Choose a new report ID for each rehearsal. The runner prepares traffic (20 users
by default), resets, measures clean traffic, injects and diagnoses. It prints
`PRESENTATION READY` before the decision. Captured workload is restored during
cleanup. Open http://127.0.0.1:8787 and the report path printed by the runner.
Tail `action_api/log.jsonl` (`Get-Content -Wait -Tail 3` or `tail -f`).

## Timed sequence

| Clock | Presenter action | Evidence / words |
|---|---|---|
| 0:00-0:15 | Show alert and architecture | This is the live incident prepared before this clock; injection and diagnosis times remain in the bundle |
| 0:15-0:35 | Show component, confidence, why-column and one evidence ID | Resolve it with `python -m tools.resolve "ID" --bundle-dir reports/mentor-payment-01`; say whether live or snapshot |
| 0:35-0:45 | Review exact plan, target, predicted effect and rollback meaning; type `yes` once | After H11 lands, browser approval also needs the one-time terminal code. Record real operator, surface and mode |
| 0:45-3:50 | Let execution and the full verification window run | Explain freshness, traffic sufficiency and two consecutive healthy samples; never count operator reset as agent recovery |
| 3:50-4:30 | Show terminal result, report and action log | Fixed, mitigated, unresolved or escalated as measured; report failed verification honestly |
| 4:30-4:50 | Runner invokes `python -m scripts.show_block --operator "Yash Verma"` | Forbidden dry run returns 403/FORBIDDEN_OPERATION; STOP is latched; allowed dry run returns 423/STOP_LATCHED |
| 4:50-5:00 | Show limitations and approval provenance | This is one measured case, not hidden-test accuracy; point to the evaluation ledger |

The live safety probe retained at [safety-loop-r1/acceptance.json](../reports/safety-loop-r1/acceptance.json)
backs BLOCK and STOP endpoint behavior. It does not prove the whole timed sequence.
After presentation the runner resets, measures at least 180 seconds of clean
traffic, and requests explicit STOP clearing. Cleanup is outside the five minutes.

Rejection is a separate prepared report: `python -m agent.respond --report
reports/REJECTION-ID/report.json --operator "Yash Verma"`, then type `no`. Never
reject and reuse the same completed checkpoint as if it were a new approval.
Alternatively the demo's `-RejectedReport` / `--rejected-report` performs a
labelled CLI rejection; that flag is not proof of a human answering a prompt.

## If a live step fails

| Failure risk | Operator response and disclosure |
|---|---|
| No alert within budget | Default wrappers use 90s; 150s detector support remains a fold xfail. Inspect `python -m detect.once`; retain timeout. Never lower thresholds on stage |
| Diagnosis/token expires | Approve within eight minutes of the report; obtain a fresh report/preview after expiry. Do not reuse a token |
| Tier-2 input typo | Read the prompt; H9 must re-ask up to three times. Old snapshot rejects typos; do not pretend it accepted |
| Stuck attempt or cooldown | `python -m action_api.state check` after H8 lands; review and resolve through that interface, or wait. Do not delete attempt state |
| Audit lock contention / polling spam | Retain blocked outcome, stop presentation and investigate; H6/H7 bounded lock/cached preview fixes must land before relying on the loop |
| Locust timeout / too few requests | Say verification is unknown; escalate. H3 must prevent automatic rollback that silently turns the failure switch back on |
| Stale or mock Control Room | Start a fresh real process before preparing the incident; never restart it in the middle of active verification |
| STOP already exists | Review the previous incident and clear with the explicit phrase only when safe; do not hide or bypass STOP |
| Overlay missing after recreate | Inspect `docker inspect flagd`; stack owner prepares the overlay with `faultctl up` outside presentation, then preflight again |
| PowerShell/venv/test-mode issue | Use pwsh 7 and README's venv; unset test mode. Avoid Windows PowerShell 5 stderr-pipeline traps |
| Diagnosis takes several minutes / model fails | Payment recording r6 and loop r3 are backups; label them recorded. Recommendation loop-r1 investigation took 394.157s; do not claim a 90s guarantee |

If verification fails, preserve that result. The current source's automatic
rollback on unknown traffic is an audit defect, not a safe fallback demonstration.
Use the corrected fold, or show the recorded limitation without executing a fix.
No fallback requires changing the official demo or calling a live test auto-approval.
