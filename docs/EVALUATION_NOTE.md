# Evaluation note: retained evidence, not hidden-test accuracy

The historical inventory came from the docsport snapshot. Current demo-stable
repetitions are recorded separately in [BUILD_09](../BUILD_09.md). Tuning cases,
live writes with automated approval, and synthetic fixtures remain separate.
A schema-valid report is not automatically a correct diagnosis or recovery claim.

## Demo-stable, 24 October: current readiness

Latest preflight: **FAIL 23/26** at 08:24 IST: RAM 0.91 GiB and checkout latency.
Earlier fresh preflights passed 26/26. Final reset/clean observation passed in
182.547 s; 21 containers, pristine flags, no STOP, original five-user load.
This does not override the latest readiness failures.

| Bundle | Knowledge | Component / category | Confidence | Agent s | Wrapper s | Status | Approval | Cleanup |
|---|---|---|---|---|---|---|---|---|
| [stable09-payment-on-r1](../reports/stable09-payment-on-r1/checkpoint2.json) | ON | Not measured | — | — | 385.541 | Runner failed before diagnosis | None | Verified |
| [stable09-payment-on-r2](../reports/stable09-payment-on-r2/report.json) | ON | payment / application_flag | 0.90 | 56.851 | 540.461 | diagnosed | None | Verified |
| [stable09-payment-on-r3](../reports/stable09-payment-on-r3/checkpoint2.json) | ON | Not measured | — | — | 383.041 | Preparation refused: frontend:rps | None | Verified |
| [stable09-payment-on-r4](../reports/stable09-payment-on-r4/report.json) | ON | payment / application_flag | 0.95 | 38.891 | 488.305 | diagnosed | None | Verified |
| [stable09-recommendation-on-r1](../reports/stable09-recommendation-on-r1/report.json) | ON | recommendation / container_down | 0.80 | 56.537 | 457.257 | diagnosed | None | Verified |
| [stable09-recommendation-on-r2](../reports/stable09-recommendation-on-r2/report.json) | ON | recommendation / container_down | 0.90 | 172.794 | 571.972 | diagnosed; FAIL time limit | None | Verified |
| Cache repetition 1 | Planned ON | Not measured | — | — | — | Not run within time budget | None | No injection |
| Payment Checkpoint 3 1 | Not selected | Not measured | — | — | — | Not run within time budget | None | No injection |
| [BLOCK](../reports/stable09-block/block.json) | N/A | delete_database refused | — | — | — | HTTP 403 / FORBIDDEN_OPERATION | None | No mutation |

Source/demo command default remains knowledge **OFF** (`INCIDENT_ZERO_KNOWLEDGE=0`), **provisional**. All fresh diagnosis runs used ON; no fresh OFF comparison was completed, so the retained OFF default is not a live-certified selection. These practice cases do not establish retrieval improvement or hidden-test accuracy. Sequential knowledge-ON runs can consult memory from earlier runs.

Agent seconds are `report.agent.elapsed_s`; wrapper seconds include preflight, reset, the clean windows, alert wait and validation. Acceptance requires the expected component/category, confidence >=0.75, `diagnosed`, and agent <120 s. Cache reliability is assessed separately.

Preparation is intermittent near the RAM floor. The 150s/90s wrapper mismatch was corrected; a deliberate load increase also caused a temporary `frontend:rps` baseline refusal. Neither preparation failure is evidence against the model or knowledge mode. Recommendation repetition 2 exceeded the 120-second agent limit despite a correct diagnosis; its required retry and conditional knowledge-OFF comparison were not completed. Cache was not rerun, so its current reliability is unmeasured. Overall live acceptance is **partial**, not a full pass.

Affected wrapper/checkpoint/hands checks: **73 passed**. The previously recorded full suite remains 770 passed, 3 skipped, 9 xfailed; it was not repeated for these live runs. Linux portability remains unverified.

| Fresh bundle | Diagnosis run ID | Result |
|---|---|---|
| [stable09-payment-on-r2](../reports/stable09-payment-on-r2/report.json) | `runs/20261024T020607.182583Z-3fd181d4` | diagnosed; 0.90; 56.851 s agent |
| [stable09-payment-on-r4](../reports/stable09-payment-on-r4/report.json) | `runs/20261024T022402.665842Z-6bf15653` | diagnosed; 0.95; 38.891 s agent |
| [stable09-recommendation-on-r1](../reports/stable09-recommendation-on-r1/report.json) | `runs/20261024T023315.758052Z-0903788b` | diagnosed; 0.80; 56.537 s agent |
| [stable09-recommendation-on-r2](../reports/stable09-recommendation-on-r2/report.json) | `runs/20261024T024152.039733Z-dc7d26df` | diagnosed; 0.90; 172.794 s agent |

## Calibration (measured)

Reproduce with `python -m eval.calibration reports/`. Only retained `report.json` files are read; no stack access or injection is performed.

Bundles: 29; labelled: 19; unlabelled: 10; cause-confidence samples: 18; labelled abstentions/clean reports excluded: 1. Brier score (labelled cause-confidence samples): 0.0372.

| Stated confidence | Labelled count | Hits | Hit rate | Wilson 95% | Unlabelled | Excluded |
|---|---:|---:|---:|---|---:|---:|
| below 0.60 | 2 | 2 | 1.0000 | 0.3424–1.0000 | 0 | 1 |
| 0.60–0.74 | 1 | 1 | 1.0000 | 0.2065–1.0000 | 0 | 0 |
| 0.75–0.89 | 2 | 2 | 1.0000 | 0.3424–1.0000 | 1 | 0 |
| 0.90–1.00 | 13 | 13 | 1.0000 | 0.7719–1.0000 | 9 | 0 |

Labels use exact cause-set `correct` from the evaluator against `eval/cases.jsonl`, not recovery status. IDs match exact case IDs or unique single-injection IDs, with optional `-rN` / `-loop-rN` repetition suffixes. No label is inferred from the predicted component, directory name or a successful action. Injection journals are not verified by this command.

Small-sample caveat: these are retained practice bundles, with repeated cases and different models/prompts pooled descriptively. Wilson intervals assume independent Bernoulli trials; correlated repetitions and selective retention limit that interpretation. This is not evidence of calibrated probabilities, held-out accuracy, or the current prompt's accuracy. Unlabelled bundles are excluded from hit rates and Brier, never counted as incorrect. Unknown-only abstentions and clean no-fault reports have no asserted cause probability; false-positive causes on no-fault cases remain eligible.

| Bundle | Matched case | Correct | Confidence | Included in calibration |
|---|---|---|---:|---|
| cache-unavailable-r1/report.json | cache-unavailable | yes | 0.5500 | yes |
| cache-unavailable-r2/report.json | cache-unavailable | yes | 0.5500 | yes |
| container-stopped-loop-r1/report.json | container-stopped-recommendation | yes | 0.9000 | yes |
| container-stopped-r1/report.json | container-stopped-recommendation | yes | 0.8500 | yes |
| container-stopped-r2/report.json | container-stopped-recommendation | yes | 0.9000 | yes |
| container-stopped-r3/report.json | container-stopped-recommendation | yes | 0.9000 | yes |
| mock-homepage-throttle/report.json | unlabelled | unlabelled | 0.9000 | no |
| mock-non-recovery/report.json | unlabelled | unlabelled | 0.9000 | no |
| mock-payment-approved/report.json | unlabelled | unlabelled | 0.9000 | no |
| mock-payment-rejected/report.json | unlabelled | unlabelled | 0.9000 | no |
| mock-recommendation-restart/report.json | unlabelled | unlabelled | 0.9000 | no |
| mock-stop-mid-run/report.json | unlabelled | unlabelled | 0.9000 | no |
| payment-failure-loop-r3/report.json | payment-failure | yes | 0.9000 | yes |
| payment-failure-loop-r4/report.json | payment-failure | yes | 0.9000 | yes |
| payment-failure-loop-r5/report.json | payment-failure | yes | 0.9000 | yes |
| payment-failure-loop-r6/report.json | payment-failure | yes | 0.8500 | yes |
| payment-failure-loop-r7/report.json | payment-failure | yes | 0.9000 | yes |
| payment-failure-loop-r8/report.json | payment-failure | yes | 0.9000 | yes |
| payment-failure-loop-r9/report.json | payment-failure | yes | 0.9000 | yes |
| payment-failure-r1/report.json | payment-failure | no | 0.3000 | no |
| payment-failure-r2/report.json | payment-failure | yes | 0.7000 | yes |
| payment-failure-r3/report.json | payment-failure | yes | 0.9000 | yes |
| payment-failure-r4/report.json | payment-failure | yes | 0.9000 | yes |
| payment-failure-r5/report.json | payment-failure | yes | 0.9000 | yes |
| payment-failure-r6/report.json | payment-failure | yes | 0.9000 | yes |
| stable09-payment-on-r2/report.json | unlabelled | unlabelled | 0.9000 | no |
| stable09-payment-on-r4/report.json | unlabelled | unlabelled | 0.9500 | no |
| stable09-recommendation-on-r1/report.json | unlabelled | unlabelled | 0.8000 | no |
| stable09-recommendation-on-r2/report.json | unlabelled | unlabelled | 0.9000 | no |

## Historical diagnosis runs

Seconds are `report.agent.elapsed_s` (investigation), not alert latency, total
rehearsal duration or time to recovery. Full run IDs and prompt hashes below are
from each report. Do not pool different prompt hashes into a final-prompt score.
No row establishes the fold's current prompt accuracy.

| Bundle | Component / category | Confidence | Tools | Investigation s | Status | Interpretation |
|---|---|---|---|---|---|---|
| [cache-unavailable-r1](../reports/cache-unavailable-r1/report.json) | valkey-cart / container_down | 0.55 | 12 | 512.984 | needs_human | Correct component, confidence 0.55; budget exhausted. |
| [cache-unavailable-r2](../reports/cache-unavailable-r2/report.json) | valkey-cart / container_down | 0.55 | 6 | 208.219 | needs_human | Correct component, confidence 0.55; model routes failed. |
| [container-stopped-r1](../reports/container-stopped-r1/report.json) | recommendation / container_down | 0.85 | 3 | 56.969 | diagnosed | Historical diagnosed case; see checkpoint2 record for cleanup. |
| [container-stopped-r2](../reports/container-stopped-r2/report.json) | recommendation / container_down | 0.9 | 2 | 42.734 | diagnosed | Historical diagnosed case; see checkpoint2 record for cleanup. |
| [container-stopped-r3](../reports/container-stopped-r3/report.json) | recommendation / container_down | 0.9 | 3 | 93.5 | diagnosed | Correct component; investigation exceeds 90s target. |
| [payment-failure-r1](../reports/payment-failure-r1/report.json) | ad / unknown | 0.3 | 1 | 2.453 | needs_human | Provider unavailable; ad is an alert-owner placeholder, not a diagnosis. |
| [payment-failure-r2](../reports/payment-failure-r2/report.json) | payment / application_flag | 0.7 | 4 | 115.187 | needs_human | Payment named; escalated, not an action acceptance pass. |
| [payment-failure-r3](../reports/payment-failure-r3/report.json) | payment / application_flag | 0.9 | 3 | 88.016 | diagnosed | Historical diagnosed case; see checkpoint2 record for cleanup. |
| [payment-failure-r4](../reports/payment-failure-r4/report.json) | payment / application_flag | 0.9 | 3 | 57.015 | diagnosed | Historical diagnosed case; see checkpoint2 record for cleanup. |
| [payment-failure-r5](../reports/payment-failure-r5/report.json) | payment / application_flag | 0.9 | 3 | 58.375 | diagnosed | Historical diagnosed case; see checkpoint2 record for cleanup. |
| [payment-failure-r6](../reports/payment-failure-r6/report.json) | payment / application_flag | 0.9 | 3 | 57.828 | diagnosed | Historical diagnosed case; see checkpoint2 record for cleanup. |

## Run identity and prompt provenance

| Bundle | Run ID | Prompt SHA-256 |
|---|---|---|
| [cache-unavailable-r1](../reports/cache-unavailable-r1/report.json) | runs/20261023T121227.303255Z-dc304b61 | 1b8ed98156c66f6775f94a4ae31d85efee45b7f1a0d5edcd12d846184d207652 |
| [cache-unavailable-r2](../reports/cache-unavailable-r2/report.json) | runs/20261023T122840.338357Z-47ea815f | 6c96b89c3282029cac84559cd310d3ffb7765ef87f04d5567b9f0df5cc7091ae |
| [container-stopped-loop-r1](../reports/container-stopped-loop-r1/report.json) | runs/20261023T160004.705486Z-ad2f6cb4 | 359def83037dd7284ffe3d937fb51f938dfcec9ff5d1698445cff54bdc8e1c7f |
| [container-stopped-r1](../reports/container-stopped-r1/report.json) | runs/20261023T114929.814263Z-8fd5a8fd | 1b8ed98156c66f6775f94a4ae31d85efee45b7f1a0d5edcd12d846184d207652 |
| [container-stopped-r2](../reports/container-stopped-r2/report.json) | runs/20261023T115651.341545Z-14d550d5 | 1b8ed98156c66f6775f94a4ae31d85efee45b7f1a0d5edcd12d846184d207652 |
| [container-stopped-r3](../reports/container-stopped-r3/report.json) | runs/20261023T120358.826377Z-c84200c3 | 1b8ed98156c66f6775f94a4ae31d85efee45b7f1a0d5edcd12d846184d207652 |
| [payment-failure-loop-r3](../reports/payment-failure-loop-r3/report.json) | runs/20261023T153512.976354Z-13778fd2 | 359def83037dd7284ffe3d937fb51f938dfcec9ff5d1698445cff54bdc8e1c7f |
| [payment-failure-loop-r4](../reports/payment-failure-loop-r4/report.json) | runs/20261023T154711.305759Z-b5f7c99e | 359def83037dd7284ffe3d937fb51f938dfcec9ff5d1698445cff54bdc8e1c7f |
| [payment-failure-loop-r5](../reports/payment-failure-loop-r5/report.json) | runs/20261023T161808.661278Z-149073c4 | 359def83037dd7284ffe3d937fb51f938dfcec9ff5d1698445cff54bdc8e1c7f |
| [payment-failure-loop-r6](../reports/payment-failure-loop-r6/report.json) | runs/20261023T162708.899517Z-3196e5c8 | 359def83037dd7284ffe3d937fb51f938dfcec9ff5d1698445cff54bdc8e1c7f |
| [payment-failure-loop-r7](../reports/payment-failure-loop-r7/report.json) | runs/20261023T164609.601361Z-807c1a76 | 359def83037dd7284ffe3d937fb51f938dfcec9ff5d1698445cff54bdc8e1c7f |
| [payment-failure-loop-r8](../reports/payment-failure-loop-r8/report.json) | runs/20261023T165913.243864Z-df3099ba | 359def83037dd7284ffe3d937fb51f938dfcec9ff5d1698445cff54bdc8e1c7f |
| [payment-failure-loop-r9](../reports/payment-failure-loop-r9/report.json) | runs/20261023T171108.246095Z-f4afce0d | 359def83037dd7284ffe3d937fb51f938dfcec9ff5d1698445cff54bdc8e1c7f |
| [payment-failure-r1](../reports/payment-failure-r1/report.json) | runs/20261023T102943.979795Z-a1fcd705 | 74c22694854de3d5fd3bce99f542cb70724515ed47e14680e6ea4a9872a53038 |
| [payment-failure-r2](../reports/payment-failure-r2/report.json) | runs/20261023T110643.477884Z-ff5ddc4c | acacd3544320bc8ce7ff7266ec8a5b64ad1d976a806737389454bd801d67d6ed |
| [payment-failure-r3](../reports/payment-failure-r3/report.json) | runs/20261023T111643.077037Z-9461e0c3 | 1b8ed98156c66f6775f94a4ae31d85efee45b7f1a0d5edcd12d846184d207652 |
| [payment-failure-r4](../reports/payment-failure-r4/report.json) | runs/20261023T112549.360906Z-ac1d2bef | 1b8ed98156c66f6775f94a4ae31d85efee45b7f1a0d5edcd12d846184d207652 |
| [payment-failure-r5](../reports/payment-failure-r5/report.json) | runs/20261023T113346.104216Z-514905da | 1b8ed98156c66f6775f94a4ae31d85efee45b7f1a0d5edcd12d846184d207652 |
| [payment-failure-r6](../reports/payment-failure-r6/report.json) | runs/20261023T114143.041886Z-68a917d4 | 1b8ed98156c66f6775f94a4ae31d85efee45b7f1a0d5edcd12d846184d207652 |

Successful historical model calls identify `openai/gpt-5`. Cache r2 explicitly
records failed OpenRouter primary/fallback routes. These are the model IDs in
the bundles, not inferred from today's environment. Temperature zero does not
guarantee repeatable model output.

## Full-loop and failed-preparation records

The approval surface below is reconstructed from `hands-rehearsal.json`, the
action log and the recorded browser acceptance in BUILD_06. Older report approval
fields originally omitted mode/surface and could misleadingly say a person
approved. The approval-provenance cherry-pick corrected these retained reports
and their rendering on demo-stable. Browser r9 had a real
endpoint but an automated operator decision, and is not human-approval evidence.
Elapsed time is `timings.inject_to_finished_s`; a dash means unrecorded, not zero.

| Bundle | Saved status | Approval surface / provenance | Runner result | Injection to finish s | Qualification |
|---|---|---|---|---|---|
| [container-stopped-loop-r1](../reports/container-stopped-loop-r1/hands-rehearsal.json) | fixed | test / test auto on LIVE stack | passed historical runner | 609.922 | Real restart/recovery with test approval; investigation 394.157s. |
| [payment-failure-loop-r1](../reports/payment-failure-loop-r1/hands-rehearsal.json) | no report | test / test auto on LIVE stack | FAIL | - | No alert in 90s; no report/recovery. |
| [payment-failure-loop-r2](../reports/payment-failure-loop-r2/hands-rehearsal.json) | no report | test / test auto on LIVE stack | FAIL | - | Baseline anomaly; injection refused; no report. |
| [payment-failure-loop-r3](../reports/payment-failure-loop-r3/hands-rehearsal.json) | fixed | test / test auto on LIVE stack | passed historical runner | 346.016 | Real toggle, recovered in stored verification; test approval. |
| [payment-failure-loop-r4](../reports/payment-failure-loop-r4/hands-rehearsal.json) | needs_human | cli / --reject flag | passed historical runner | 145.453 | CLI --reject; unchanged world hashes; no execution. |
| [payment-failure-loop-r5](../reports/payment-failure-loop-r5/hands-rehearsal.json) | aborted | test / test auto on LIVE stack | passed historical runner | 137.438 | Toggle completed, STOP aborted verification; no recovery claim. |
| [payment-failure-loop-r6](../reports/payment-failure-loop-r6/hands-rehearsal.json) | fixed | test / test auto on LIVE stack | FAIL | - | Runner failed; report says fixed. Sparse traffic/stop timeout invalidates intended acceptance. |
| [payment-failure-loop-r7](../reports/payment-failure-loop-r7/hands-rehearsal.json) | rolled_back | test / test auto on LIVE stack | FAIL | - | Rollback happened; runner failed zero-user confirmation. |
| [payment-failure-loop-r8](../reports/payment-failure-loop-r8/hands-rehearsal.json) | rolled_back | test / test auto on LIVE stack | passed historical runner | 322.844 | Runner passed historical rollback path, but unknown-traffic rollback violates new H3 policy. |
| [payment-failure-loop-r9](../reports/payment-failure-loop-r9/hands-rehearsal.json) | fixed | browser / automated acceptance | passed historical runner | 313.078 | Browser automation joined terminal checkpoint; not a human-approved run. |

Human-typed CLI approval and a human browser approval with one-time operator
code: **not verified**. The 09:30 rehearsal must provide both. Runtime test-mode
approvals must be prohibited from live executors in the fold.

## Synthetic evidence, explicitly not live recovery

| Bundle | Fixture component/category | Stored result |
|---|---|---|
| [mock-homepage-throttle](../reports/mock-homepage-throttle/report.json) | load-generator / load | fixed |
| [mock-non-recovery](../reports/mock-non-recovery/report.json) | payment / application_flag | rolled_back |
| [mock-payment-approved](../reports/mock-payment-approved/report.json) | payment / application_flag | fixed |
| [mock-payment-rejected](../reports/mock-payment-rejected/report.json) | payment / application_flag | needs_human |
| [mock-recommendation-restart](../reports/mock-recommendation-restart/report.json) | recommendation / container_down | fixed |
| [mock-stop-mid-run](../reports/mock-stop-mid-run/report.json) | payment / application_flag | aborted |

These six bundles use fake executors, synthetic telemetry, virtual verification
time and no model invocation. Confidence 0.90 is fixture input, not calibration.
The separate [safety probe](../reports/safety-loop-r1/acceptance.json) records
403/FORBIDDEN_OPERATION and 423/STOP_LATCHED. The
[restoration record](../reports/integration-final-state/final-state.json) records
21 running containers and measured operator cleanup; neither is an accuracy run.

## Pre-registered live retrieval ablation (not run here)

Freeze the code revision, exact prompt hash, model IDs, corpus/index hash, traffic
settings and detector thresholds before starting. Run three cases in three modes:
off, runbooks only, runbooks plus memory. Use isolated indexes per case/mode and
exclude every record of the evaluated incident family from the memory arm. Keep
the same initial stack/clean-window procedure and preserve every failure. Record
the following fields from fresh investigations, not from replayed decisions.

The mode-selector CLI for runbooks-only versus memory is not verified in this
snapshot; confirm the folded knowledge interface before execution. This table
supersedes the older six-run on/off instructions. Empty means **not verified**.

| Incident | Mode | Bundle / run ID | Prompt hash | Component | Category | Correct? | Confidence | Tool calls | Seconds |
|---|---|---|---|---|---|---|---|---|---|
| payment-failure | off |  |  |  |  |  |  |  |  |
| payment-failure | runbooks |  |  |  |  |  |  |  |  |
| payment-failure | runbooks + memory (leave family out) |  |  |  |  |  |  |  |  |
| container-stopped (recommendation) | off |  |  |  |  |  |  |  |  |
| container-stopped (recommendation) | runbooks |  |  |  |  |  |  |  |  |
| container-stopped (recommendation) | runbooks + memory (leave family out) |  |  |  |  |  |  |  |  |
| cache-unavailable | off |  |  |  |  |  |  |  |  |
| cache-unavailable | runbooks |  |  |  |  |  |  |  |  |
| cache-unavailable | runbooks + memory (leave family out) |  |  |  |  |  |  |  |  |

Do not infer percentage improvement from nine runs. Report ties, regressions,
timeouts and missing hints. Repeated-incident memory reuse is a separate labelled
experiment and cannot establish unseen-family benefit. Wrong-hint and poisoned
memory live safety rehearsals are also not verified. No weight updates occur.

## What does not work, and what was not tested

- **Cache confidence and visibility:** cache r1/r2 both escalated at 0.55. The
  original family/support scoring missed caller corroboration and own-symptom
  coverage. Cart operations against stopped valkey can hang for about 137-256s;
  a 120s trace lookback can return empty because spans have not completed yet.
  Empty reads are not health. See the retained `llm.jsonl`/trace observations and
  [CHECKPOINT2_BRIEF](CHECKPOINT2_BRIEF.md). Current scoring reruns are not verified.
- **Correlated evidence and leakage:** spanmetrics are derived from spans, logs
  can name an unrelated service, and ordinary positive CPU is not abnormality.
  Family, emitter attribution, baseline strength and delimiter-breakout hardening
  are fold requirements. The final corrected confidence is not backfilled here.
- **Report completeness / concurrency:** tool limits alone do not guarantee a
  terminal report, an end-to-end deadline, fresh evidence epochs, or one active
  investigation. Duplicate alerts and the 150s watcher budget have strict xfails.
- **Telemetry/traffic:** dedicated outage alerts, stopped-load-generator state,
  SERVER-only latency and baseline-relative thresholds are not verified in this
  snapshot. One idle recording passed; it does not invalidate the other laptop's
  roughly four-second synthetic-client false alarm.
- **Approval honesty:** test-auto and automated browser decisions do not prove a
  human said yes. CLI rejection flags do not prove a person typed no. Report-mode
  propagation is included on demo-stable; browser one-time codes and
  live-test-bypass removal remain deferred fold work.
- **Verification/rollback:** r6's fixed report accompanied failed acceptance and
  only 56/70 estimated frontend requests in final samples. R7/r8 rolled back on
  stopped traffic, re-enabling failure settings: H3 must replace this with unknown
  verification escalation. Already-clear alerts cannot earn fixed credit; actual
  sample age and >=30% affected-service baseline traffic must qualify recovery.
- **Operator readiness:** bounded audit locks, cached previews, crash-safe attempt
  check/resolve, typo re-prompts and stable world hashes are required before the
  broader hardened release. Demo-stable checks stuck attempts and cooldowns by
  reading the existing database when the fold-only state CLI is unavailable;
  the final measured preflight is recorded in BUILD_09.
- **Coverage:** cart-intermittent, catalog-one-product, recommendation leak, ad CPU,
  homepage flood, generic network/resource diagnosis and all six held-out combined
  rehearsals have no accepted fresh bundle in this snapshot. Their operator
  injection tests do not establish diagnosis accuracy. Confidence calibration,
  organiser schema/interface and hidden-test score are not verified.
- **Scope:** Compose has no scaling action; network/resource/external-loop repairs
  are not allowlisted. Restarts cannot restore previous process state. Combined
  supported causes currently lose proposals; the fold requires per-action risk.
- **Timing:** recommendation investigations exceeded the target; the complete
  five-minute presentation, fresh second-laptop setup and corrected merged live
  knowledge behavior have not been measured here.

## Reproducible checks for this documentation snapshot

`scripts/preflight.ps1 -StackRoot D:/incident-zero` and its Git Bash twin recorded
21/25 PASS on the shared idle stack, with no injection/reset. The captured health
and detector inputs are `tests/fixtures/clean_stack_oct23.json`. New offline
regressions initially returned 34 passed, 10 strict xfails. Linux gate results,
including failures, are in `.build/portability/`; the final session handoff in
RELEASE_CHECKLIST records the final executed result. None of these is a live
diagnosis rerun or hidden-test benchmark.
