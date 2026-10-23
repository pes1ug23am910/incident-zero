# Incident: payment-failure-r6

**diagnosed** · payment · confidence 90%

Local payment handler fails grpc.oteldemo.PaymentService/Charge with: "Payment request failed. Invalid token. app.loyalty.level=gold"; propagates as checkout PlaceOrder errors and frontend 13 INTERNAL.

Run: `runs/20261023T114143.041886Z-68a917d4` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T11:41:41.738934+00:00 |
| Diagnosed | 2026-10-23T11:42:40.879192+00:00 |
| Approval requested | — |
| Approved | — |
| Action started | — |
| Action finished | — |
| Verified | — |
| Resolved | — |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| checkout | error_rate | 0.08988764044943821 | metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792755703.06=0.08988764044943821 |
| frontend-proxy | error_rate | 0.05517241379310344 | metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792755703.06=0.05517241379310344 |
| load-generator | error_rate | 0.05063291139240506 | metric:query{__query__="named:error_rate_by_service",service_name="load-generator"}@1792755703.06=0.05063291139240506 |
| payment | error_rate | 0.2352941176470588 | metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792755703.06=0.2352941176470588 |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| payment | Local payment handler fails grpc.oteldemo.PaymentService/Charge with: "Payment request failed. Invalid token. app.loyalty.level=gold"; propagates as checkout PlaceOrder errors and frontend 13 INTERNAL. | 90% | 95% | 90% | checkout, frontend-proxy, load-generator, payment | span:8b306c3c608065647aca9d4022faf156/4383d7dd6b4d084a, span:711434e5402f16cfdfa23008ac393316/3507d2206f16f4ba, span:6b7c11caf2040cba63f62fc9120a3b06/4055522950396716, dlog:payment:e2e7702e669331ff55c3a2f07d53f595c27b440d97e3f37e57d7d2fff7814494, dlog:payment:29b0d51611873d7e1cfa3cb6ce67bb28f0f501a56ca727a3f2208680bf2f56dc, dlog:payment:72d2b715bf2cebd7916c8cc884f83870f6ebdc3567c647b6eb4d717d88a1102a, dlog:payment:2990bf0b4bc170f746d17e853cd56bb4182c62105ec5a75433c855d3d3c7b5f7, metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792755703.06=0.2352941176470588 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 4 symptom entries. |
| 2 | get_traces | Identify the failing operation and dependency involved in checkout errors to distinguish a local checkout exception from downstream payment issues that could explain upstream errors. | [{"trace_id": "8b306c3c608065647aca9d4022faf156", "duration_ms": 880.933, "root_span": {"span_id": "c9b6dccad0ed85da", "service": "load-generator", "operation": "POST", "duration_ms": 13.848, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "4383d7dd6b4d084a", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 0.588, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.chargeServiceHandler [as charge] (/usr/src/app/index.js:21:22)", "exception.type": "Error"}}, "origin_error_spans": [{"span_id": "4383d7dd6b4d084a", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 0.588, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.chargeServiceHandler [as charge] (/usr/src/app/index.js:21:22)", "exception.type": "Error"}}, {"span_id": "f2db |
| 3 | get_logs | Corroborate the payment application error seen in traces by finding matching WARN/ERROR logs with the same failure text, to confirm the root cause behind checkout and frontend errors. | [{"timestamp": "2026-10-23T11:41:46.692669703Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "42b10ff487671599622665fd7e11fde0", "evidence_id": "dlog:payment:e2e7702e669331ff55c3a2f07d53f595c27b440d97e3f37e57d7d2fff7814494"}, {"timestamp": "2026-10-23T11:41:38.193177381Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "ff3f48ee7dde0c239f7dd5266ecf6caa", "evidence_id": "dlog:payment:29b0d51611873d7e1cfa3cb6ce67bb28f0f501a56ca727a3f2208680bf2f56dc"}, {"timestamp": "2026-10-23T11:41:29.371908736Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "6b7c11caf2040cba63f62fc9120a3b06", "evidence_id": "dlog:payment:72d2b715bf2cebd7916c8cc884f83870f6ebdc3567c647b6eb4d717d88a1102a"}, {"timestamp": "2026-10-23T11:41:15.060012052Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "9eee2b91f894cd74424f8ce5839c809e", "evidence_id": "dlog:payment:2990bf0b4bc170f746d17e853cd56bb4182c62105ec5a75433c855d3d3c7b5f7"}, {"timestamp": "2026-10-23T11:41:02.472352244Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "8b306c3c608065647aca9d4022faf156", "evidence_id": "dlog:payment:b2dbdf95fc5999bd5bea4c202b61ec04c88f57897af5b1033a9754e0e0acbfbd"}, {"timestamp": "2026-10-23T11:41:00.589471706Z", "severity": "WARN", " |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| dlog:payment:2990bf0b4bc170f746d17e853cd56bb4182c62105ec5a75433c855d3d3c7b5f7 | docker | {"timestamp": "2026-10-23T11:41:15.060012052Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "9eee2b91f894cd74424f8ce5839c809e", "evidence_id": "dlog:payment:2990bf0b4bc170f746d17e853cd56bb4182c62105ec5a75433c855d3d3c7b5f7", "original_line": "2026-10-23T11:41:15.060012052Z {\"level\":\"warn\",\"time\":1792755675059,\"pid\":16,\"hostname\":\"c4595978b15c\",\"trace_id\":\"9eee2b91f894cd74424f8ce5839c809e\",\"span_id\":\"df273456574d38c5\",\"trace_flags\":\"01\",\"service.name\":\"payment\",\"err\":{\"type\":\"Error\",\"message\":\"Payment request failed. Invalid token. app.loyalty.level=gold\",\"stack\":\"Error: Payment request failed. Invalid token. app.loyalty.level=gold\\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\\n    at asyn | python -m tools.resolve 'dlog:payment:2990bf0b4bc170f746d17e853cd56bb4182c62105ec5a75433c855d3d3c7b5f7' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| dlog:payment:29b0d51611873d7e1cfa3cb6ce67bb28f0f501a56ca727a3f2208680bf2f56dc | docker | {"timestamp": "2026-10-23T11:41:38.193177381Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "ff3f48ee7dde0c239f7dd5266ecf6caa", "evidence_id": "dlog:payment:29b0d51611873d7e1cfa3cb6ce67bb28f0f501a56ca727a3f2208680bf2f56dc", "original_line": "2026-10-23T11:41:38.193177381Z {\"level\":\"warn\",\"time\":1792755698191,\"pid\":16,\"hostname\":\"c4595978b15c\",\"trace_id\":\"ff3f48ee7dde0c239f7dd5266ecf6caa\",\"span_id\":\"a593b9fb93c46540\",\"trace_flags\":\"01\",\"service.name\":\"payment\",\"err\":{\"type\":\"Error\",\"message\":\"Payment request failed. Invalid token. app.loyalty.level=gold\",\"stack\":\"Error: Payment request failed. Invalid token. app.loyalty.level=gold\\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\\n    at asyn | python -m tools.resolve 'dlog:payment:29b0d51611873d7e1cfa3cb6ce67bb28f0f501a56ca727a3f2208680bf2f56dc' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| dlog:payment:72d2b715bf2cebd7916c8cc884f83870f6ebdc3567c647b6eb4d717d88a1102a | docker | {"timestamp": "2026-10-23T11:41:29.371908736Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "6b7c11caf2040cba63f62fc9120a3b06", "evidence_id": "dlog:payment:72d2b715bf2cebd7916c8cc884f83870f6ebdc3567c647b6eb4d717d88a1102a", "original_line": "2026-10-23T11:41:29.371908736Z {\"level\":\"warn\",\"time\":1792755689371,\"pid\":16,\"hostname\":\"c4595978b15c\",\"trace_id\":\"6b7c11caf2040cba63f62fc9120a3b06\",\"span_id\":\"4055522950396716\",\"trace_flags\":\"01\",\"service.name\":\"payment\",\"err\":{\"type\":\"Error\",\"message\":\"Payment request failed. Invalid token. app.loyalty.level=gold\",\"stack\":\"Error: Payment request failed. Invalid token. app.loyalty.level=gold\\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\\n    at asyn | python -m tools.resolve 'dlog:payment:72d2b715bf2cebd7916c8cc884f83870f6ebdc3567c647b6eb4d717d88a1102a' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| dlog:payment:e2e7702e669331ff55c3a2f07d53f595c27b440d97e3f37e57d7d2fff7814494 | docker | {"timestamp": "2026-10-23T11:41:46.692669703Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "42b10ff487671599622665fd7e11fde0", "evidence_id": "dlog:payment:e2e7702e669331ff55c3a2f07d53f595c27b440d97e3f37e57d7d2fff7814494", "original_line": "2026-10-23T11:41:46.692669703Z {\"level\":\"warn\",\"time\":1792755706691,\"pid\":16,\"hostname\":\"c4595978b15c\",\"trace_id\":\"42b10ff487671599622665fd7e11fde0\",\"span_id\":\"91da871e02726a08\",\"trace_flags\":\"01\",\"service.name\":\"payment\",\"err\":{\"type\":\"Error\",\"message\":\"Payment request failed. Invalid token. app.loyalty.level=gold\",\"stack\":\"Error: Payment request failed. Invalid token. app.loyalty.level=gold\\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\\n    at asyn | python -m tools.resolve 'dlog:payment:e2e7702e669331ff55c3a2f07d53f595c27b440d97e3f37e57d7d2fff7814494' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792755703.06=0.08988764044943821 | prometheus | {"metric": {"service_name": "checkout"}, "timestamp": 1792755703.06, "value": 0.08988764044943821, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792755703.06=0.08988764044943821' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792755703.06=0.05517241379310344 | prometheus | {"metric": {"service_name": "frontend-proxy"}, "timestamp": 1792755703.06, "value": 0.05517241379310344, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792755703.06=0.05517241379310344' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| metric:query{__query__="named:error_rate_by_service",service_name="load-generator"}@1792755703.06=0.05063291139240506 | prometheus | {"metric": {"service_name": "load-generator"}, "timestamp": 1792755703.06, "value": 0.05063291139240506, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="load-generator"}@1792755703.06=0.05063291139240506' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792755703.06=0.2352941176470588 | prometheus | {"metric": {"service_name": "payment"}, "timestamp": 1792755703.06, "value": 0.2352941176470588, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792755703.06=0.2352941176470588' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| span:6b7c11caf2040cba63f62fc9120a3b06/4055522950396716 | jaeger | {"traceID": "6b7c11caf2040cba63f62fc9120a3b06", "spanID": "4055522950396716", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "6b7c11caf2040cba63f62fc9120a3b06", "spanID": "aef17eb9ab56e7ea"}], "startTime": 1792755689370000, "duration": 840, "tags": [{"key": "app.payment.amount", "type": "string", "value": "2111.25"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge"}, | python -m tools.resolve 'span:6b7c11caf2040cba63f62fc9120a3b06/4055522950396716' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| span:711434e5402f16cfdfa23008ac393316/3507d2206f16f4ba | jaeger | {"traceID": "711434e5402f16cfdfa23008ac393316", "spanID": "3507d2206f16f4ba", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "711434e5402f16cfdfa23008ac393316", "spanID": "ad6e6272dc4ab993"}], "startTime": 1792755660584000, "duration": 4963, "tags": [{"key": "app.payment.amount", "type": "string", "value": "18296.50"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge" | python -m tools.resolve 'span:711434e5402f16cfdfa23008ac393316/3507d2206f16f4ba' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |
| span:8b306c3c608065647aca9d4022faf156/4383d7dd6b4d084a | jaeger | {"traceID": "8b306c3c608065647aca9d4022faf156", "spanID": "4383d7dd6b4d084a", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "8b306c3c608065647aca9d4022faf156", "spanID": "1a19809816e08270"}], "startTime": 1792755662471000, "duration": 588, "tags": [{"key": "app.payment.amount", "type": "string", "value": "1137.50"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge"}, | python -m tools.resolve 'span:8b306c3c608065647aca9d4022faf156/4383d7dd6b4d084a' --run-dir 'runs/20261023T114143.041886Z-68a917d4' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261023T114143.041886Z-68a917d4'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

## Impact

| Field | Assessment |
| --- | --- |
| Approval tier | T2 |
| Score | 60/100 |
| Business criticality | critical |
| Journeys affected | checkout, payment |
| Estimated users affected | Not measured: telemetry counts spans and requests, not distinct users. |
| Blast radius | single_service |
| Reversibility | instant |
| Data risk | none |
| Confidence | 90% |
| Rationale | A critical service or process restart requires the full evidence table, a reviewer or the independent-source check, and explicit typed yes. |
| Decision | — |
| Reason codes |  |
| Uncertainty | — |
| Observability gap | — |

## Proposed action

**1. toggle_flag** → payment

Reason: disable the failure switch for payment

Risk: Configuration change requires human approval and a recorded rollback value.

Parameters: `{"service": "payment"}`

Dry run performed: no. Restore normal application behavior in payment; confirm with fresh telemetry.


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
| error_rate | — | — | — | no |

Outcome: —; requests observed: —.

## Alternatives and escalation

- Checkout client-side validation failing before calling payment
- Network/transient gRPC failures between checkout and payment
- Payment container resource limits causing sporadic errors

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 3 tool calls; 57.83 s; stopped because confident.
