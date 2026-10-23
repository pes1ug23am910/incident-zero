# Incident: mock-non-recovery

**rolled_back** · payment · confidence 90%

Synthetic payment failure fixture.

Run: `runs/mock-non-recovery` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T11:13:47.025835+00:00 |
| Diagnosed | 2026-10-23T11:13:47.032842+00:00 |
| Approval requested | 2026-10-23T11:13:47.166603+00:00 |
| Approved | 2026-10-23T11:13:47.166603+00:00 |
| Action started | 2026-10-23T11:13:47.195864+00:00 |
| Action finished | 2026-10-23T11:13:47.206004+00:00 |
| Verified | 2026-10-23T11:13:47.236840+00:00 |
| Resolved | — |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| payment | error_rate | Synthetic error rate .9 | container:payment:Status=running, trace:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| payment | Synthetic payment failure fixture. | 90% | 90% | 90% | payment | container:payment:Status=running, trace:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | get_container_health | Synthetic fixture | Synthetic observation |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:payment:Status=running | docker | Synthetic payment evidence; not measured live. | offline fixture |
| trace:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | jaeger | Synthetic payment evidence; not measured live. | offline fixture |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/mock-non-recovery'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

## Impact

| Field | Assessment |
| --- | --- |
| Approval tier | T2 |
| Score | 62.0/100 |
| Business criticality | critical |
| Journeys affected | checkout, payment |
| Estimated users affected | Not measured: telemetry counts spans and requests, not distinct users. |
| Blast radius | single_service |
| Reversibility | instant |
| Data risk | none |
| Confidence | 90% |
| Rationale | A critical service or process restart requires the full evidence table, a reviewer or the independent-source check, and explicit typed yes. |
| Decision | REQUIRE_HUMAN |
| Reason codes | CRITICAL_SERVICE |
| Uncertainty | 0.09999999999999998 |
| Observability gap | 0.0 |

## Proposed action

**1. toggle_flag** → payment

Reason: disable the failure switch for payment

Risk: Configuration change requires human approval and a recorded rollback value.

Parameters: `{"service": "payment"}`

Dry run performed: yes. Restore normal application behavior in payment; confirm with fresh telemetry.


## Approval record

Approved in TEST mode by the test harness (not a human)

| Field | Value |
| --- | --- |
| Required | yes |
| Approved | yes |
| Recorded actor | test harness |
| Surface | test |
| Mode | test |
| Requested at | 2026-10-23T11:13:47.166603+00:00 |
| Approved at | 2026-10-23T11:13:47.166603+00:00 |
| Token id | sha256:f4868f6ccc1859d2c9c932e312e081e18c13146f1d07fb127400c38c42da9812 |
| Token | present (redacted) |
| Executed | yes |
| Action log | action_log:5 |

## Verification

| Signal | Before | After | Recovered | Rolled back |
| --- | --- | --- | --- | --- |
| error_rate | 0.9 | 0.8 | no | yes |

Outcome: unresolved; requests observed: 40.

## Action history

| Index | Decision | Executed | Outcome | Blocked |
| --- | --- | --- | --- | --- |
| 0 | approve | yes | unresolved |  |

## Alternatives and escalation

- Synthetic dependency failure.

Operator review required: rejected, blocked, unverified or rolled back remediation. Inspect action history and all alert signals before a new attempt.

## Prevention

—

## Limitations

- SYNTHETIC MOCK ACCEPTANCE: no incident was injected; no model or live stack was used.
- Recovery verifies observed signals and request counts; interrupted requests cannot be restored.
- Historical approval provenance was corrected from the retained action log; the original audit entries and evidence snapshots are unchanged. Prompt-shown time was not recorded, so requested_at retains its original value.

## Investigation budget

Model: none (mock fixtures); 0 tool calls; 0.00 s; stopped because confident.
