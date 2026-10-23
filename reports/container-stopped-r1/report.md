# Incident: container-stopped-r1

**diagnosed** · recommendation · confidence 85%

Recommendation service container is exited; frontend calls fail on DNS lookup to recommendation.

Run: `runs/20261023T114929.814263Z-8fd5a8fd` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T11:49:28.923237+00:00 |
| Diagnosed | 2026-10-23T11:50:26.781110+00:00 |
| Approval requested | — |
| Approved | — |
| Action started | — |
| Action finished | — |
| Verified | — |
| Resolved | — |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| recommendation | container_status | exited | container:recommendation:Status=exited |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| recommendation | Recommendation service container is exited; frontend calls fail on DNS lookup to recommendation. | 85% | 90% | 85% | recommendation | container:recommendation:Status=exited, trace:b9e462e662e2dd7a9bcd62b4b15deca2, span:b9e462e662e2dd7a9bcd62b4b15deca2/23e1a57d17ee0b08 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 1 symptom entries. |
| 2 | get_traces | Identify caller error spans to the exited recommendation service to corroborate container_down with request-level failures or fallbacks. | [{"trace_id": "b9e462e662e2dd7a9bcd62b4b15deca2", "duration_ms": 3971.351, "root_span": {"span_id": "23e1a57d17ee0b08", "service": "frontend", "operation": "dns.lookup", "duration_ms": 3971.351, "status_message": "getaddrinfo ENOTFOUND recommendation", "exception": {}}, "first_error_span": {"span_id": "23e1a57d17ee0b08", "service": "frontend", "operation": "dns.lookup", "duration_ms": 3971.351, "status_message": "getaddrinfo ENOTFOUND recommendation", "exception": {}}, "origin_error_spans": [{"span_id": "23e1a57d17ee0b08", "service": "frontend", "operation": "dns.lookup", "duration_ms": 3971.351, "status_message": "getaddrinfo ENOTFOUND recommendation", "exception": {}}], "error_spans": [{"span_id": "23e1a57d17ee0b08", "service": "frontend", "operation": "dns.lookup", "duration_ms": 3971.351, "status_message": "getaddrinfo ENOTFOUND recommendation", "exception": {}}], "services": ["frontend"]}] |
| 3 | get_logs | Corroborate the exited recommendation container with caller-side error logs indicating failed lookups/calls to recommendation. | [] |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:recommendation:Status=exited | docker | {"name": "recommendation", "field": "Status", "value": "exited"} | python -m tools.resolve 'container:recommendation:Status=exited' --run-dir 'runs/20261023T114929.814263Z-8fd5a8fd' |
| span:b9e462e662e2dd7a9bcd62b4b15deca2/23e1a57d17ee0b08 | jaeger | {"traceID": "b9e462e662e2dd7a9bcd62b4b15deca2", "spanID": "23e1a57d17ee0b08", "operationName": "dns.lookup", "references": [], "startTime": 1792756171213000, "duration": 3971351, "tags": [{"key": "dns.error_message", "type": "string", "value": "getaddrinfo ENOTFOUND recommendation"}, {"key": "dns.error_name", "type": "string", "value": "Error"}, {"key": "error", "type": "bool", "value": true}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-dns"}, {"key": "otel.scope.version", "type": "string", "value": "0.43.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "otel.status_description", "type": "string", "value": "getaddrinfo ENOTFOUND recommendation"}, {"key": "span.kind", "type": "string", "value": "client"}], "logs": [], "processID": "p1", "warnings": ["invalid parent span IDs=6d5fbc352d1d9b21; skipping clock skew adjustm | python -m tools.resolve 'span:b9e462e662e2dd7a9bcd62b4b15deca2/23e1a57d17ee0b08' --run-dir 'runs/20261023T114929.814263Z-8fd5a8fd' |
| trace:b9e462e662e2dd7a9bcd62b4b15deca2 | jaeger | {"traceID": "b9e462e662e2dd7a9bcd62b4b15deca2", "warnings": null, "spans": [{"traceID": "b9e462e662e2dd7a9bcd62b4b15deca2", "spanID": "23e1a57d17ee0b08", "operationName": "dns.lookup", "references": [], "startTime": 1792756171213000, "duration": 3971351, "tags": [{"key": "dns.error_message", "type": "string", "value": "getaddrinfo ENOTFOUND recommendation"}, {"key": "dns.error_name", "type": "string", "value": "Error"}, {"key": "error", "type": "bool", "value": true}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-dns"}, {"key": "otel.scope.version", "type": "string", "value": "0.43.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "otel.status_description", "type": "string", "value": "getaddrinfo ENOTFOUND recommendation"}, {"key": "span.kind", "type": "string", "value": "client"}], "logs": [], "processID": "p1", "warnin | python -m tools.resolve 'trace:b9e462e662e2dd7a9bcd62b4b15deca2' --run-dir 'runs/20261023T114929.814263Z-8fd5a8fd' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261023T114929.814263Z-8fd5a8fd'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

## Impact

| Field | Assessment |
| --- | --- |
| Approval tier | T2 |
| Score | 45/100 |
| Business criticality | auxiliary |
| Journeys affected | recommendations |
| Estimated users affected | Not measured: telemetry counts spans and requests, not distinct users. |
| Blast radius | single_service |
| Reversibility | self_healing |
| Data risk | none |
| Confidence | 85% |
| Rationale | A critical service or process restart requires the full evidence table, a reviewer or the independent-source check, and explicit typed yes. |

## Proposed action

**1. restart_service** → recommendation

Reason: Restore the diagnosed unavailable component recommendation.

Risk: Restart may interrupt in-flight work; review state and evidence before approval.

Parameters: `{"service": "recommendation"}`

Dry run performed: no. Start a fresh recommendation process and restore its availability to callers.


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

- Transient DNS resolution failure in frontend unrelated to container exit
- Caller-side fallback hiding user-visible errors despite dependency outage

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 3 tool calls; 56.97 s; stopped because confident.
