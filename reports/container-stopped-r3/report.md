# Incident: container-stopped-r3

**diagnosed** · recommendation · confidence 90%

Container is exited; frontend calls to RecommendationService fail with UNAVAILABLE and EHOSTUNREACH to 172.23.0.12:9001.

Run: `runs/20261023T120358.826377Z-c84200c3` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T12:03:57.412289+00:00 |
| Diagnosed | 2026-10-23T12:05:32.326168+00:00 |
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
| recommendation | Container is exited; frontend calls to RecommendationService fail with UNAVAILABLE and EHOSTUNREACH to 172.23.0.12:9001. | 90% | 90% | 90% | recommendation | container:recommendation:Status=exited, span:a1f004f6d9ecaade2545e46eefba7094/f6b3d49cc7d06d9e, span:dd14e584d5cc70026e8d260b6c22ae3a/b677348ccd238fb0, dlog:frontend:73042247b8bc9efeeeed1dd829ee86fc5381f3ce63d0b1a7036354d03a7d2aaa |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 1 symptom entries. |
| 2 | get_traces | Recommendation container is exited; check if frontend requests show dependency connection errors to confirm a container_down impact versus a harmless idle path. | [{"trace_id": "a1f004f6d9ecaade2545e46eefba7094", "duration_ms": 5.773, "root_span": {"span_id": "d0ae11ca6686a806", "service": "load-generator", "operation": "GET", "duration_ms": 5.773, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "f6b3d49cc7d06d9e", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 0.544, "status_message": "14", "exception": {}}, "origin_error_spans": [{"span_id": "f6b3d49cc7d06d9e", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 0.544, "status_message": "14", "exception": {}}, {"span_id": "6addc5ea9826742d", "service": "frontend", "operation": "GET", "duration_ms": 3.356, "status_message": "", "exception": {}}], "error_spans": [{"span_id": "f6b3d49cc7d06d9e", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 0.544, "status_message": "14", "exception": {}}, {"span_id": "46a6f800fe34c12a", "service": "frontend", "operation": "executing api route (pages) /api/recommendations", "duration_ms": 2.281, "status_message": "", "exception": {"exception.message": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:04.173Z)", "exception.stacktrace": "Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:04.173Z)\n    at callErrorFromStatus  |
| 3 | get_logs | Corroborate frontend caller errors to the stopped recommendation service with concrete log lines (EHOSTUNREACH/UNAVAILABLE) as a second, independent evidence source for container_down. | [{"timestamp": "2026-10-23T12:04:39.369498800Z", "severity": "ERROR", "body": "  details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:31.945Z)',", "trace_id": null, "evidence_id": "dlog:frontend:8b873ddcc13d3052c248472cd230be33a3b83ad6a803667b4d9b7f8048c8acc0"}, {"timestamp": "2026-10-23T12:04:39.369436787Z", "severity": "ERROR", "body": " ⨯ Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:31.945Z)", "trace_id": null, "evidence_id": "dlog:frontend:48e0d8f6d1bb75a6ba63c3c1e9b5c427f8eb67b0679d1c036a927e27616e46da"}, {"timestamp": "2026-10-23T12:04:39.369292116Z", "severity": "ERROR", "body": "  details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:31.945Z)',", "trace_id": null, "evidence_id": "dlog:frontend:61ff3fb5af13f32b2000e16991428fe925f97d7a406384705e929e9ebb06e184"}, {"timestamp": "2026-10-23T12:04:39.369217632Z", "severity": "ERROR", "body": "Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:31.945Z)", "trace_id": null, "evidence_id": "dlog:frontend:73042247b8bc9efeeeed1dd829ee86fc5381f3ce63d0b1a7036354d03a7d2aaa"}, {"timestamp": "2026-10-23T12:04:33.431608155Z", "severity": "ERROR", "body": "  details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:31.945Z)',", "trace_id": null, "evide |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:recommendation:Status=exited | docker | {"name": "recommendation", "field": "Status", "value": "exited"} | python -m tools.resolve 'container:recommendation:Status=exited' --run-dir 'runs/20261023T120358.826377Z-c84200c3' |
| dlog:frontend:73042247b8bc9efeeeed1dd829ee86fc5381f3ce63d0b1a7036354d03a7d2aaa | docker | {"timestamp": "2026-10-23T12:04:39.369217632Z", "severity": "ERROR", "body": "Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:31.945Z)", "trace_id": null, "evidence_id": "dlog:frontend:73042247b8bc9efeeeed1dd829ee86fc5381f3ce63d0b1a7036354d03a7d2aaa", "original_line": "2026-10-23T12:04:39.369217632Z Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:31.945Z)"} | python -m tools.resolve 'dlog:frontend:73042247b8bc9efeeeed1dd829ee86fc5381f3ce63d0b1a7036354d03a7d2aaa' --run-dir 'runs/20261023T120358.826377Z-c84200c3' |
| span:a1f004f6d9ecaade2545e46eefba7094/f6b3d49cc7d06d9e | jaeger | {"traceID": "a1f004f6d9ecaade2545e46eefba7094", "spanID": "f6b3d49cc7d06d9e", "operationName": "grpc.oteldemo.RecommendationService/ListRecommendations", "references": [{"refType": "CHILD_OF", "traceID": "a1f004f6d9ecaade2545e46eefba7094", "spanID": "46a6f800fe34c12a"}], "startTime": 1792757046008000, "duration": 544, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T12:04:04.173Z)"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "net.peer.name", "type": "string", "value": "recommendation"}, {"key": "net.peer.port", "type": "int64", "value": 9001}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value | python -m tools.resolve 'span:a1f004f6d9ecaade2545e46eefba7094/f6b3d49cc7d06d9e' --run-dir 'runs/20261023T120358.826377Z-c84200c3' |
| span:dd14e584d5cc70026e8d260b6c22ae3a/b677348ccd238fb0 | jaeger | {"traceID": "dd14e584d5cc70026e8d260b6c22ae3a", "spanID": "b677348ccd238fb0", "operationName": "tcp.connect", "references": [{"refType": "CHILD_OF", "traceID": "dd14e584d5cc70026e8d260b6c22ae3a", "spanID": "51271fa7608eccb0"}], "startTime": 1792757041117000, "duration": 3055872, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "net.peer.name", "type": "string", "value": "172.23.0.12"}, {"key": "net.peer.port", "type": "int64", "value": 9001}, {"key": "net.transport", "type": "string", "value": "ip_tcp"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-net"}, {"key": "otel.scope.version", "type": "string", "value": "0.43.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "otel.status_description", "type": "string", "value": "connect EHOSTUNREACH 172.23.0.12:9001"}, {"key": "span.kind", "type": "string", "val | python -m tools.resolve 'span:dd14e584d5cc70026e8d260b6c22ae3a/b677348ccd238fb0' --run-dir 'runs/20261023T120358.826377Z-c84200c3' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261023T120358.826377Z-c84200c3'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

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
| Confidence | 90% |
| Rationale | A critical service or process restart requires the full evidence table, a reviewer or the independent-source check, and explicit typed yes. |
| Decision | — |
| Reason codes |  |
| Uncertainty | — |
| Observability gap | — |

## Proposed action

**1. restart_service** → recommendation

Reason: Restore the diagnosed unavailable component recommendation.

Risk: Restart may interrupt in-flight work; review state and evidence before approval.

Parameters: `{"service": "recommendation"}`

Dry run performed: no. Start a fresh recommendation process and restore its availability to callers.


## Approval record

No approval recorded

| Field | Value |
| --- | --- |
| Required | yes |
| Approved | — |
| Recorded actor | — |
| Surface | — |
| Mode | — |
| Requested at | — |
| Approved at | — |
| Token id | absent |
| Token | absent |
| Executed | no |
| Action log | — |

## Verification

| Signal | Before | After | Recovered | Rolled back |
| --- | --- | --- | --- | --- |
| container_health | — | — | — | no |

Outcome: —; requests observed: —.

## Alternatives and escalation

- Transient DNS or network issue to recommendation without container exit

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 3 tool calls; 93.50 s; stopped because confident.
