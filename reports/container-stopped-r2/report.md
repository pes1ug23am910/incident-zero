# Incident: container-stopped-r2

**diagnosed** · recommendation · confidence 90%

Container exited; frontend calls to RecommendationService fail with DNS ENOTFOUND and connect EHOSTUNREACH to recommendation:9001, returning gRPC UNAVAILABLE.

Run: `runs/20261023T115651.341545Z-14d550d5` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T11:56:50.443923+00:00 |
| Diagnosed | 2026-10-23T11:57:34.079479+00:00 |
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
| recommendation | Container exited; frontend calls to RecommendationService fail with DNS ENOTFOUND and connect EHOSTUNREACH to recommendation:9001, returning gRPC UNAVAILABLE. | 90% | 90% | 90% | recommendation | container:recommendation:Status=exited, span:83e373888cd0014cb66867722fa762d0/86f811004070ec67, span:83e373888cd0014cb66867722fa762d0/2c5c73f4f8ef1531, span:88b1a528a60cfaf2e383c505b27ec5e7/5dfa7d9da3ef3018, span:69be6608d6cd33374e187f8267da0a08/334c699bc35bb259 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 1 symptom entries. |
| 2 | get_traces | Recommendation container is exited (container:recommendation:Status=exited); check frontend error traces for failed calls to it to confirm container_down via propagated errors. | [{"trace_id": "83e373888cd0014cb66867722fa762d0", "duration_ms": 12284.051, "root_span": {"span_id": "a25aaff00bbc2310", "service": "load-generator", "operation": "GET", "duration_ms": 3077.297, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "86f811004070ec67", "service": "frontend", "operation": "dns.lookup", "duration_ms": 3979.358, "status_message": "getaddrinfo ENOTFOUND recommendation", "exception": {}}, "origin_error_spans": [{"span_id": "86f811004070ec67", "service": "frontend", "operation": "dns.lookup", "duration_ms": 3979.358, "status_message": "getaddrinfo ENOTFOUND recommendation", "exception": {}}, {"span_id": "2c5c73f4f8ef1531", "service": "frontend", "operation": "tcp.connect", "duration_ms": 3063.99, "status_message": "connect EHOSTUNREACH 172.23.0.12:9001", "exception": {}}, {"span_id": "be105aaf8bf2cba3", "service": "frontend", "operation": "tcp.connect", "duration_ms": 3067.724, "status_message": "connect EHOSTUNREACH 172.23.0.12:9001", "exception": {}}, {"span_id": "ec9c8457189561e7", "service": "frontend", "operation": "tcp.connect", "duration_ms": 3069.899, "status_message": "connect EHOSTUNREACH 172.23.0.12:9001", "exception": {}}, {"span_id": "1a5da464a5c3c468", "service": "frontend", "operation": "dns.lookup", "duration_ms": 3876.949, "status_message": "getaddrinfo ENOTFOUND recommendation", "exception": {}}, {"span_id": "2190f3736fd15414", "service": "frontend", "operation": "tcp.connect", "duration_ms": 3072.756, "status_mes |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:recommendation:Status=exited | docker | {"name": "recommendation", "field": "Status", "value": "exited"} | python -m tools.resolve 'container:recommendation:Status=exited' --run-dir 'runs/20261023T115651.341545Z-14d550d5' |
| span:69be6608d6cd33374e187f8267da0a08/334c699bc35bb259 | jaeger | {"traceID": "69be6608d6cd33374e187f8267da0a08", "spanID": "334c699bc35bb259", "operationName": "grpc.oteldemo.RecommendationService/ListRecommendations", "references": [{"refType": "CHILD_OF", "traceID": "69be6608d6cd33374e187f8267da0a08", "spanID": "22687b8fdce8d2fd"}], "startTime": 1792756624942000, "duration": 787, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T11:57:04.434Z)"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "net.peer.name", "type": "string", "value": "recommendation"}, {"key": "net.peer.port", "type": "int64", "value": 9001}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value | python -m tools.resolve 'span:69be6608d6cd33374e187f8267da0a08/334c699bc35bb259' --run-dir 'runs/20261023T115651.341545Z-14d550d5' |
| span:83e373888cd0014cb66867722fa762d0/2c5c73f4f8ef1531 | jaeger | {"traceID": "83e373888cd0014cb66867722fa762d0", "spanID": "2c5c73f4f8ef1531", "operationName": "tcp.connect", "references": [{"refType": "CHILD_OF", "traceID": "83e373888cd0014cb66867722fa762d0", "spanID": "dd395149d00c2bab"}], "startTime": 1792756615228000, "duration": 3063990, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "net.peer.name", "type": "string", "value": "172.23.0.12"}, {"key": "net.peer.port", "type": "int64", "value": 9001}, {"key": "net.transport", "type": "string", "value": "ip_tcp"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-net"}, {"key": "otel.scope.version", "type": "string", "value": "0.43.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "otel.status_description", "type": "string", "value": "connect EHOSTUNREACH 172.23.0.12:9001"}, {"key": "span.kind", "type": "string", "val | python -m tools.resolve 'span:83e373888cd0014cb66867722fa762d0/2c5c73f4f8ef1531' --run-dir 'runs/20261023T115651.341545Z-14d550d5' |
| span:83e373888cd0014cb66867722fa762d0/86f811004070ec67 | jaeger | {"traceID": "83e373888cd0014cb66867722fa762d0", "spanID": "86f811004070ec67", "operationName": "dns.lookup", "references": [{"refType": "CHILD_OF", "traceID": "83e373888cd0014cb66867722fa762d0", "spanID": "dd395149d00c2bab"}], "startTime": 1792756615227000, "duration": 3979358, "tags": [{"key": "dns.error_message", "type": "string", "value": "getaddrinfo ENOTFOUND recommendation"}, {"key": "dns.error_name", "type": "string", "value": "Error"}, {"key": "error", "type": "bool", "value": true}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-dns"}, {"key": "otel.scope.version", "type": "string", "value": "0.43.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "otel.status_description", "type": "string", "value": "getaddrinfo ENOTFOUND recommendation"}, {"key": "span.kind", "type": "string", "value": "client"}], "logs": [], "p | python -m tools.resolve 'span:83e373888cd0014cb66867722fa762d0/86f811004070ec67' --run-dir 'runs/20261023T115651.341545Z-14d550d5' |
| span:88b1a528a60cfaf2e383c505b27ec5e7/5dfa7d9da3ef3018 | jaeger | {"traceID": "88b1a528a60cfaf2e383c505b27ec5e7", "spanID": "5dfa7d9da3ef3018", "operationName": "grpc.oteldemo.RecommendationService/ListRecommendations", "references": [{"refType": "CHILD_OF", "traceID": "88b1a528a60cfaf2e383c505b27ec5e7", "spanID": "6143a5eef26b9666"}], "startTime": 1792756621395000, "duration": 1051, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T11:57:01.362Z)"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "net.peer.name", "type": "string", "value": "recommendation"}, {"key": "net.peer.port", "type": "int64", "value": 9001}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "valu | python -m tools.resolve 'span:88b1a528a60cfaf2e383c505b27ec5e7/5dfa7d9da3ef3018' --run-dir 'runs/20261023T115651.341545Z-14d550d5' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261023T115651.341545Z-14d550d5'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

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

- network
- application_flag in frontend

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 2 tool calls; 42.73 s; stopped because confident.
