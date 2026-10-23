# Incident: mock-recommendation-restart

**fixed** · recommendation · confidence 90%

Synthetic recommendation failure fixture.

Run: `runs/mock-recommendation-restart` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T11:13:45.983583+00:00 |
| Diagnosed | 2026-10-23T11:13:45.990585+00:00 |
| Approval requested | 2026-10-23T11:13:46.120413+00:00 |
| Approved | 2026-10-23T11:13:46.120413+00:00 |
| Action started | 2026-10-23T11:13:46.147645+00:00 |
| Action finished | 2026-10-23T11:13:46.158651+00:00 |
| Verified | 2026-10-23T11:13:46.183353+00:00 |
| Resolved | 2026-10-23T11:13:46.199469+00:00 |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| recommendation | error_rate | Synthetic error rate .9 | container:recommendation:Status=running, trace:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| recommendation | Synthetic recommendation failure fixture. | 90% | 90% | 90% | recommendation | container:recommendation:Status=running, trace:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | get_container_health | Synthetic fixture | Synthetic observation |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:recommendation:Status=running | docker | Synthetic recommendation evidence; not measured live. | offline fixture |
| trace:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | jaeger | Synthetic recommendation evidence; not measured live. | offline fixture |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/mock-recommendation-restart'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

## Impact

| Field | Assessment |
| --- | --- |
| Approval tier | T2 |
| Score | 47.0/100 |
| Business criticality | auxiliary |
| Journeys affected | recommendations |
| Estimated users affected | Not measured: telemetry counts spans and requests, not distinct users. |
| Blast radius | single_service |
| Reversibility | self_healing |
| Data risk | none |
| Confidence | 90% |
| Rationale | A critical service or process restart requires the full evidence table, a reviewer or the independent-source check, and explicit typed yes. |
| Decision | REQUIRE_HUMAN |
| Reason codes | RESTART_REQUIRES_HUMAN |
| Uncertainty | 0.09999999999999998 |
| Observability gap | 0.0 |

## Proposed action

**1. restart_service** → recommendation

Reason: Restore the diagnosed unavailable component recommendation.

Risk: Restart may interrupt in-flight work; review state and evidence before approval.

Parameters: `{"service": "recommendation"}`

Dry run performed: yes. Start a fresh recommendation process and restore its availability to callers.


## Approval record

| Field | Value |
| --- | --- |
| Required | yes |
| Approved | yes |
| Approved by | Mock operator |
| Approved at | 2026-10-23T11:13:46.120413+00:00 |
| Token | present (redacted) |
| Executed | yes |
| Action log | action_log:5 |

## Verification

| Signal | Before | After | Recovered | Rolled back |
| --- | --- | --- | --- | --- |
| error_rate | 0.9 | 0.0 | yes | no |

Outcome: recovered; requests observed: 40.

## Action history

| Index | Decision | Executed | Outcome | Blocked |
| --- | --- | --- | --- | --- |
| 0 | approve | yes | recovered |  |

## Alternatives and escalation

- Synthetic dependency failure.

—

## Prevention

—

## Limitations

- SYNTHETIC MOCK ACCEPTANCE: no incident was injected; no model or live stack was used.
- Recovery verifies observed signals and request counts; interrupted requests cannot be restored.

## Investigation budget

Model: none (mock fixtures); 0 tool calls; 0.00 s; stopped because confident.
