# Incident: example-unconfirmed-payment

**needs_human** · payment · confidence 30%

The available container state is insufficient to identify an application failure.

Run: `runs/example-offline` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T13:00:00+05:30 |
| Diagnosed | 2026-10-23T13:00:02+05:30 |
| Approval requested | — |
| Approved | — |
| Action started | — |
| Action finished | — |
| Verified | — |
| Resolved | — |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| payment | container_status | The example payment container is running; this alone does not establish application health. | container:payment:Status=running |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | get_container_health | Check whether the suspected service has stopped. | The illustrative fixture reports payment running; application telemetry is still required. |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:payment:Status=running | docker | The illustrative offline fixture reports payment with Status=running. | python -m tools.resolve 'container:payment:Status=running' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/example-offline'`; the resolver reports whether it used the live source or a recorded snapshot.

## Proposed action

No action proposed.

## Approval record

| Field | Value |
| --- | --- |
| Required | yes |
| Approved | — |
| Approved by | — |
| Approved at | — |
| Token | absent |
| Executed | no |
| Action log | — |

## Verification

| Signal | Before | After | Recovered | Rolled back |
| --- | --- | --- | --- | --- |
| container_health | — | — | — | no |

## Alternatives and escalation

- The payment application may be healthy.
- An application or dependency error can occur while the process remains running.

The payment process appears running in the example fixture. Application health and root cause remain uncertain. A human should inspect recent error traces and payment logs before proposing a change.

## Prevention

—

## Limitations

- ILLUSTRATIVE OFFLINE EXAMPLE: this report is hand-authored, uses an explicit evidence fixture, and is not a measured incident investigation.
- No system action or recovery was performed.

## Investigation budget

Model: none (hand-authored example); 1 tool calls; 2.00 s; stopped because budget.
