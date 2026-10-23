# Evaluation note

This ledger separates historical diagnosis runs, live integrated response runs,
and synthetic safety fixtures. Reports are the evidence; unrun cases do not have
estimated results. Practice cases are tuning data and do not establish the
organisers' unseen-incident score.

## Historical diagnosis runs

These runs reset, inject, detect and investigate, then reset again. They did not
execute proposals. The incident identifier was report metadata, excluded from
the model prompt. Seconds below are `diagnosed_at - detected_at` from each report;
the checkpoint brief also records the slightly shorter subprocess duration.

| Report | Component / category | Confidence | Tools | Alert to diagnosis, s | Status | Interpretation |
| --- | --- | ---: | ---: | ---: | --- | --- |
| [payment-failure-r1](../reports/payment-failure-r1/report.json) | ad / unknown | 0.30 | 1 | 3.812 | needs_human | Provider TLS failure; alert-owner placeholder, no model diagnosis |
| [payment-failure-r2](../reports/payment-failure-r2/report.json) | payment / application_flag | 0.70 | 4 | 117.247 | needs_human | Correct cause named; insufficient confidence for action |
| [payment-failure-r3](../reports/payment-failure-r3/report.json) | payment / application_flag | 0.90 | 3 | 89.499 | diagnosed | Correct diagnosis and tier-2 proposal |
| [payment-failure-r4](../reports/payment-failure-r4/report.json) | payment / application_flag | 0.90 | 3 | 58.422 | diagnosed | First of three consecutive complete accepted rehearsals |
| [payment-failure-r5](../reports/payment-failure-r5/report.json) | payment / application_flag | 0.90 | 3 | 59.456 | diagnosed | Correct diagnosis and both cleanup windows |
| [payment-failure-r6](../reports/payment-failure-r6/report.json) | payment / application_flag | 0.90 | 3 | 59.140 | diagnosed | Correct diagnosis and both cleanup windows |
| [container-stopped-r1](../reports/container-stopped-r1/report.json) | recommendation / container_down | 0.85 | 3 | 57.858 | diagnosed | Correct diagnosis and tier-2 restart proposal |
| [container-stopped-r2](../reports/container-stopped-r2/report.json) | recommendation / container_down | 0.90 | 2 | 43.636 | diagnosed | Correct diagnosis and tier-2 restart proposal |
| [container-stopped-r3](../reports/container-stopped-r3/report.json) | recommendation / container_down | 0.90 | 3 | 94.914 | diagnosed | Correct diagnosis; missed 90-second target |
| [cache-unavailable-r1](../reports/cache-unavailable-r1/report.json) | valkey-cart / container_down | 0.55 | 12 | 514.076 | needs_human | Correct cause component; exhausted budget, no approved recovery |
| [cache-unavailable-r2](../reports/cache-unavailable-r2/report.json) | valkey-cart / container_down | 0.55 | 6 | 209.544 | needs_human | Provider routes failed; missing positive caller-error corroboration |

Successful historical model calls used `openai/gpt-5`; the report identifies
failed fallback attempts separately. Runtime model IDs now come only from `.env`
or process configuration. The cache reports remain unchanged after scoring fixes.
A stopped dependency is `container_down`: `valkey-cart` is the cause and `cart`
is the symptom owner. The two cache runs did **not** meet the required confident
diagnosis/three-consecutive-run acceptance, despite naming the correct component.

The historical set has 11 retained runs across only three incident families.
Seven have confident correct diagnoses and proposals; the remaining four
escalate, including the provider failure. This is repeated tuning, not a 10-case
practice sweep or a held-out accuracy estimate. New independent observations and
scoring changes have not retroactively changed any report's measured confidence.

## Live full-loop acceptance

Each integrated bundle records the actual approval path, stage timings,
action-log excerpt, original alert, action samples and before/after cleanup
measurements. The current `fixed` rule requires every original alert signal to recover on two
consecutive samples over >=180 seconds, >=20 measured requests, and a running
load-generator container plus observed Locust `running` state with positive users.
Rejection and STOP do not claim recovery caused by an action.
Recovery seconds use the runner's injection-to-finished measurement after final
bundle validation; the underlying action samples retain their own elapsed times.

Automated developer acceptance explicitly enables `INCIDENT_ZERO_TEST=1` with
`--auto-approve-for-tests`; it does not collect a human decision. The mentor/demo
wrappers reject that environment. Browser acceptance uses the real confirmation.

| Incident / bundle | Final status | Approval path | Action | Injection to verified recovery, s | Measured outcome |
| --- | --- | --- | --- | ---: | --- |
| [payment-failure-loop-r1](../reports/payment-failure-loop-r1/hands-rehearsal.json) | Run failed before diagnosis | Test auto configured; no decision reached | None | — | No detector alert in 90s at five users; clean before 244.781s and after 183.953s |
| [payment-failure-loop-r2](../reports/payment-failure-loop-r2/hands-rehearsal.json) | Run refused before injection | Test auto configured; no decision reached | None | — | New 20-user traffic exceeded the historical five-user baseline; clean before 184.391s and after 184.500s |
| [payment-failure-loop-r3](../reports/payment-failure-loop-r3/report.json) | fixed | Explicit developer test auto-approval | toggle_flag payment | 346.016 | All four alert signals zero in final two samples; 984.049 measured requests; load running; 182.359s verification |
| [payment-failure-loop-r4](../reports/payment-failure-loop-r4/report.json), rejection | needs_human | CLI explicit reject; test mode off | None executed | — | Before/after authoritative world hashes match; response finished 145.453s after injection; action log contains preview and rejection only |
| [container-stopped-loop-r1](../reports/container-stopped-loop-r1/report.json), recommendation | fixed | Explicit developer test auto-approval | restart_service recommendation | 609.922 | Container running on final two samples; 892.045/1220.081 measured requests; load running; 182.000s verification |
| [payment-failure-loop-r5](../reports/payment-failure-loop-r5/report.json), STOP during response | aborted | Explicit developer test auto-approval, then STOP | toggle_flag executed; verification interrupted | — | STOP 15s after execution began; no recovery or rollback claimed; response finished 137.438s after injection |
| [payment-failure-loop-r6](../reports/payment-failure-loop-r6/hands-rehearsal.json), forced traffic loss | Acceptance failed; saved report says fixed | Explicit developer test auto-approval | toggle_flag payment | — | Operator swarm-stop request timed out; old verification accepted 56.005/70.005 measured requests with the container running; rollback was not exercised |
| [payment-failure-loop-r7](../reports/payment-failure-loop-r7/hands-rehearsal.json), forced traffic loss retry | rolled_back in report; runner failed its stop confirmation | Explicit developer test auto-approval | toggle_flag payment, then captured setting restored | — | Real rollback after 182.625s; stopped swarm with one remaining user prevented recovery despite 40.003/52.003 measured requests; harness incorrectly required zero users |
| [payment-failure-loop-r8](../reports/payment-failure-loop-r8/report.json), forced traffic loss complete retry | rolled_back | Explicit developer test auto-approval | toggle_flag payment, then captured setting restored | — | Complete runner passed; 182.750s verification refused recovery with stopped swarm; response finished 322.844s after injection; operator cleanup recovered separately |
| [payment-failure-loop-r9](../reports/payment-failure-loop-r9/report.json), real Control Room approval | fixed | Real browser confirmation, automated acceptance; terminal waiter | toggle_flag payment | 313.078 | Actual checkpoint3 wrapper passed; 183.500s verification, both alert values zero; 1260.084/1188.079 requests; Locust running with 21 observed users |

The successful payment run used
`runs/20261023T153512.976354Z-13778fd2`. Its clean before/after windows were
184.562/184.375 seconds; approval, execution and verification together took
201.391 seconds. The [action log](../reports/payment-failure-loop-r3/action-log.jsonl)
records lines 22–27, including the explicit test approval and actual setting
change. The operator-prepared traffic baseline and retained measurements are in
the [runner record](../reports/payment-failure-loop-r3/hands-rehearsal.json).
The 346.016-second injection-to-finish result exceeds five minutes: the timed
presentation therefore prepares the real alert and diagnosis before its clock.

The rejection run retained an unchanged executor-world fingerprint before and
after the decision, observed before operator cleanup. Its clean windows were
184.640/185.031 seconds. The [action log](../reports/payment-failure-loop-r4/action-log.jsonl)
contains lines 28–29 (dry run, rejection), with no execute entry; the report says
`approval.approved = false` and `action.executed = false`. No remediation recovery
time is claimed for rejection; reset recovery belongs to the operator.

The stopped-recommendation run used
`runs/20261023T160004.705486Z-ad2f6cb4`. It diagnosed `container_down` at 0.90
confidence with nine tool calls; the investigation itself took 394.157 seconds,
well beyond the 90-second presentation target. Approval, execution and
verification took 200.141 seconds. The [action log](../reports/container-stopped-loop-r1/action-log.jsonl)
contains lines 30–35, including the approved restart and measured recovery.
Qualified clean windows before/after were 184.781/184.656 seconds. This establishes
the live restart path, without claiming that diagnosis latency is demo-ready.

The STOP run used `runs/20261023T161808.661278Z-149073c4`. The toggle completed,
then STOP interrupted verification and prevented rollback. The
[action log](../reports/payment-failure-loop-r5/action-log.jsonl) includes the
STOP event between execution and `STOP_LATCHED` verification. Response time was
30.985 seconds; before/after operator-cleanup windows were 184.281/184.719 seconds.
Its empty aborted-verification sample list and zero request field are cancellation
placeholders, not a measurement that no traffic ran. No 180-second action
verification completed and no remediation recovery time is claimed. The current
handler retains observed partial samples on cancellation; historical r5 was not
reconstructed or rewritten to claim those observations.

The forced non-recovery case stops the **Locust swarm** after real execution,
leaving its container running. It uses actual unchanged telemetry, then restores
the captured users/spawn rate during operator cleanup. This checks traffic-loss
qualification and rollback; it does not demonstrate an application signal that
remains above threshold despite remediation.

The first forced attempt, r6 (`runs/20261023T162708.899517Z-3196e5c8`), failed
acceptance. Its `/loadgen/stop` response timed out after ten seconds and did not
establish stopped swarm state. The old verifier checked container liveness and
counted requests, accepting 56.005/70.005 requests in its final two samples over
181.969 seconds. The saved `fixed` report is retained honestly, but does not prove
the requested non-recovery/rollback path. The runner failed before final timing
validation; its response phase took 199.703 seconds, with clean before/after
windows of 184.782/184.718 seconds. The revised operator control allows a longer
request, retains uncertainty and requires observed `stopped` state. The reported
remaining-user count is retained rather than assumed zero. No request-count
threshold or telemetry value is changed for the retry.
The verifier now independently requires observed Locust `running` state and
positive users as well as container liveness; stopped/unknown state fails closed
even when residual request counters exceed 20. The r6 report retains the older
container-only qualification and is not retroactively counted as rollback success.

The next attempt, r7 (`runs/20261023T164609.601361Z-807c1a76`), exercised real
rollback. Its final samples at 152.594/182.625 seconds observed Locust `stopped`
with one remaining user; `load_running` was false despite positive request
counts. The captured setting was restored and the report says `rolled_back`,
`recovered = false`. The [action log](../reports/payment-failure-loop-r7/action-log.jsonl)
contains load observations, rollback and verification at lines 50–63. The runner
still failed because its operator stop confirmation incorrectly demanded zero
remaining users. That failure is retained; current confirmation accepts observed
`stopped` state with a valid nonnegative user count and records it honestly.
The response phase took 206.188 seconds; qualified before/after cleanup windows
were 184.844/183.938 seconds. No injection-to-recovery time is claimed for rollback.

The complete retry, r8 (`runs/20261023T165913.243864Z-df3099ba`), passed with
`rolled_back` and no operator-control error. Both the stop response and observed
stopped swarm were confirmed. Final samples at 152.750/182.750 seconds had
80.005/72.005 measured requests and zero alert values, but Locust remained stopped
with one reported user, so recovery correctly stayed false. The actual captured
setting was restored. Response took 205.125 seconds and finished 322.844 seconds
after injection; clean before/after windows were 184.984/184.093 seconds.
Its [action log](../reports/payment-failure-loop-r8/action-log.jsonl) retains
the run's approval, execution, load observations, rollback and verification.

The real Control Room run, r9 (`runs/20261023T171108.246095Z-f4afce0d`), used
the actual `scripts/checkpoint3.ps1` terminal flow and approved through the browser
as `Integration acceptance`. Browser automation entered the real confirmation;
this was an automated acceptance decision, not a person approving. The bundle
records `approval_waiter = terminal`, `approval_path = browser`, and test auto
approval disabled. The [action log](../reports/payment-failure-loop-r9/action-log.jsonl)
contains `ui_approval`, one execution start/finish and measured verification.
The terminal joined that same result and waited before cleanup. The response
phase took 219.734 seconds; qualified before/after windows were 184.047/183.922
seconds. JSON/Markdown and action evidence persisted with `fixed`, and the whole
runner completed without failure. This establishes the shared browser/terminal
gate; it does not establish a separate timed five-minute presentation.

Commands and detailed timings are
in [BUILD_05](../BUILD_05.md); browser observations are in
[BUILD_06](../BUILD_06.md).

## Synthetic acceptance retained separately

The separate live [safety probe](../reports/safety-loop-r1/acceptance.json)
returned HTTP 403 / `FORBIDDEN_OPERATION` for the forbidden operation, then
HTTP 423 / `STOP_LATCHED` for an allowed dry run after STOP. No mutation started;
STOP was explicitly cleared. These command-level checks do not establish the
timing of the complete five-minute presentation.

The final integration suite passed **670 tests**, with **3 skipped**.

The hands branch retained six bundles exercising real checkpoint/response code
with fake executors, fake telemetry and virtual 180-second windows. Confidence
0.90 is fixture input; no model runs. These are not live accuracy or latency data.

| Bundle | Fixture choice | Result |
| --- | --- | --- |
| [mock-payment-approved](../reports/mock-payment-approved/report.json) | toggle_flag, yes | fixed |
| [mock-payment-rejected](../reports/mock-payment-rejected/report.json) | reject | needs_human |
| [mock-recommendation-restart](../reports/mock-recommendation-restart/report.json) | restart_service, yes | fixed |
| [mock-homepage-throttle](../reports/mock-homepage-throttle/report.json) | throttle_load, y | fixed |
| [mock-stop-mid-run](../reports/mock-stop-mid-run/report.json) | STOP after execution | aborted |
| [mock-non-recovery](../reports/mock-non-recovery/report.json) | persistent failing samples | rolled_back |

## Coverage, calibration and remaining work

The other practice families (`cart-intermittent`, `catalog-one-product`,
`recommendation-leak`, `ad-high-cpu`, `homepage-flood`, network latency and CPU
starvation), optional variants, held-out combinations and no-fault run have not
been measured in the retained diagnosis set. The offline utility
`python -m eval.calibration --results <explicit-manifest.json>` supports
case-based scoring, Brier scores and Wilson intervals with source/model grouping.
No aggregate calibration number is asserted from synthetic data or this narrow,
repeated tuning set. Complete the held-out fold after freezing tuning changes.
The complete five-minute presentation has not been timed live. Its script
explicitly places injection and diagnosis before the presentation clock and
retains their measured latency; the verification window is never shortened.

Known limits: no Compose scaling or network/resource repair, irreversible restart
side effects, finite telemetry retention, same-user localhost trust, and no
reviewer-model invocation. Independent multi-service causes escalate at tier 3.
Historical source snapshots do not prove live recovery. A successful real action
on a tuning case does not guarantee the same behavior on an unseen incident.
