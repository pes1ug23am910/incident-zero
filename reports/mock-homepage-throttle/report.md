# Incident: mock-homepage-throttle

**fixed** · load-generator · confidence 90%

Synthetic load-generator failure fixture.

Run: `runs/mock-homepage-throttle` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T11:13:46.339139+00:00 |
| Diagnosed | 2026-10-23T11:13:46.347652+00:00 |
| Approval requested | 2026-10-23T11:13:46.485395+00:00 |
| Approved | 2026-10-23T11:13:46.485395+00:00 |
| Action started | 2026-10-23T11:13:46.515404+00:00 |
| Action finished | 2026-10-23T11:13:46.528407+00:00 |
| Verified | 2026-10-23T11:13:46.551931+00:00 |
| Resolved | 2026-10-23T11:13:46.568052+00:00 |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| load-generator | error_rate | Synthetic error rate .9 | container:load-generator:Status=running, trace:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| load-generator | Synthetic load-generator failure fixture. | 90% | 90% | 90% | load-generator | container:load-generator:Status=running, trace:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | get_container_health | Synthetic fixture | Synthetic observation |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:load-generator:Status=running | docker | Synthetic load-generator evidence; not measured live. | offline fixture |
| trace:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | jaeger | Synthetic load-generator evidence; not measured live. | offline fixture |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/mock-homepage-throttle'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

## Impact

| Field | Assessment |
| --- | --- |
| Approval tier | T1 |
| Score | 17.0/100 |
| Business criticality | auxiliary |
| Journeys affected | generated shopping traffic |
| Estimated users affected | Not measured: telemetry counts spans and requests, not distinct users. |
| Blast radius | single_service |
| Reversibility | instant |
| Data risk | none |
| Confidence | 90% |
| Rationale | One auxiliary or core service, reversible change and confidence at least 0.75; show action, target and predicted effect and require a human yes. |
| Decision | REQUIRE_HUMAN |
| Reason codes | HUMAN_APPROVAL_REQUIRED |
| Uncertainty | 0.09999999999999998 |
| Observability gap | 0.0 |

## Proposed action

**1. throttle_load** → load-generator

Reason: Reduce generated request volume to relieve the observed overload.

Risk: Reduces test traffic; record the current traffic level before an approved change.

Parameters: `{"spawn_rate": 1, "users": 1}`

Dry run performed: yes. Reduce the load generator to 1 concurrent user(s).

Quick approval: throttle_load on load-generator; predicted effect: Reduce the load generator to 1 concurrent user(s).. A human yes is required.


## Approval record

| Field | Value |
| --- | --- |
| Required | yes |
| Approved | yes |
| Approved by | Mock operator |
| Approved at | 2026-10-23T11:13:46.485395+00:00 |
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
