# Incident: payment-failure-r3

**diagnosed** · payment · confidence 90%

PaymentService Charge returns an application error: "Payment request failed. Invalid token. app.loyalty.level=gold", causing CheckoutService/PlaceOrder to fail and errors to propagate to frontend and proxy.

Run: `runs/20261023T111643.077037Z-9461e0c3` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T11:16:41.602954+00:00 |
| Diagnosed | 2026-10-23T11:18:11.101903+00:00 |
| Approval requested | — |
| Approved | — |
| Action started | — |
| Action finished | — |
| Verified | — |
| Resolved | — |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| checkout | error_rate | 0.15873015873015872 | metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792754203.098=0.15873015873015872 |
| frontend-proxy | error_rate | 0.065359477124183 | metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792754203.098=0.065359477124183 |
| load-generator | error_rate | 0.061728395061728385 | metric:query{__query__="named:error_rate_by_service",service_name="load-generator"}@1792754203.098=0.061728395061728385 |
| payment | error_rate | 0.39999999999999997 | metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792754203.098=0.39999999999999997 |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| payment | PaymentService Charge returns an application error: "Payment request failed. Invalid token. app.loyalty.level=gold", causing CheckoutService/PlaceOrder to fail and errors to propagate to frontend and proxy. | 90% | 95% | 90% | checkout, frontend-proxy, load-generator, payment | span:42e982087215cd4bdbe21223e53a5023/0f521ba8cd7485ed, span:5b4a94bec3a8e9f7509c2e2365c8371a/c7eacc0baf249948, span:4d629da60b35aaff5b10e3baccc0771a/bb5cd8d9b30decfe, dlog:payment:229178e9feab2ca67d3289866e95bc36cebb4b23135537ec09598ef696ca3a66, dlog:payment:00b1127d14ee5d9842f9cc6f316ffda8364ba14e3655ab2e1b063ae0c660858e, metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792754203.098=0.39999999999999997 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 4 symptom entries. |
| 2 | get_traces | Checkout shows elevated error rate; inspect recent error traces to identify the failing operation and whether a downstream dependency (e.g., payment) is causing the errors. | [{"trace_id": "42e982087215cd4bdbe21223e53a5023", "duration_ms": 778.774, "root_span": {"span_id": "5119d106ac1bc1ea", "service": "load-generator", "operation": "POST", "duration_ms": 15.558, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "0f521ba8cd7485ed", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 0.997, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.chargeServiceHandler [as charge] (/usr/src/app/index.js:21:22)", "exception.type": "Error"}}, "origin_error_spans": [{"span_id": "0f521ba8cd7485ed", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 0.997, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.chargeServiceHandler [as charge] (/usr/src/app/index.js:21:22)", "exception.type": "Error"}}, {"span_id": "ab83 |
| 3 | get_logs | Confirm that payment errors in traces are reflected in service logs to support an application_flag in payment as the root cause of checkout and propagated frontend errors. | [{"timestamp": "2026-10-23T11:16:55.692408340Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "b05a0ede1cd8655b66528b0a72f0de46", "evidence_id": "dlog:payment:a232e0f8a3b1f2da9890310365a3221f1a3b9a5aef377eb2b3ac8b221b3d2173"}, {"timestamp": "2026-10-23T11:16:35.394899057Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "1f7ea43a59634d4c0fe2c159a00db7d0", "evidence_id": "dlog:payment:8b3218727569fedbc47e5282978400e32a6205a7c5339df7e2ecef8ccb56e506"}, {"timestamp": "2026-10-23T11:16:30.837706248Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "5ebd00e12f0cf713cefa0a28cf3d5d03", "evidence_id": "dlog:payment:67fa2b8e57d2ecba61bbc2c7bfac0d885cb2c9a2ea3c96e4ec2008319e3896c5"}, {"timestamp": "2026-10-23T11:16:06.572620327Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "4d629da60b35aaff5b10e3baccc0771a", "evidence_id": "dlog:payment:6ece9901e1bb2d8b4663f9d010c4bac3a2291edc8a191de202a9ddc95c1ca6f3"}, {"timestamp": "2026-10-23T11:16:02.241402528Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "5b4a94bec3a8e9f7509c2e2365c8371a", "evidence_id": "dlog:payment:00b1127d14ee5d9842f9cc6f316ffda8364ba14e3655ab2e1b063ae0c660858e"}, {"timestamp": "2026-10-23T11:15:50.061060531Z", "severity": "WARN", " |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| dlog:payment:00b1127d14ee5d9842f9cc6f316ffda8364ba14e3655ab2e1b063ae0c660858e | docker | {"timestamp": "2026-10-23T11:16:02.241402528Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "5b4a94bec3a8e9f7509c2e2365c8371a", "evidence_id": "dlog:payment:00b1127d14ee5d9842f9cc6f316ffda8364ba14e3655ab2e1b063ae0c660858e", "original_line": "2026-10-23T11:16:02.241402528Z {\"level\":\"warn\",\"time\":1792754162240,\"pid\":16,\"hostname\":\"c4595978b15c\",\"trace_id\":\"5b4a94bec3a8e9f7509c2e2365c8371a\",\"span_id\":\"c7eacc0baf249948\",\"trace_flags\":\"01\",\"service.name\":\"payment\",\"err\":{\"type\":\"Error\",\"message\":\"Payment request failed. Invalid token. app.loyalty.level=gold\",\"stack\":\"Error: Payment request failed. Invalid token. app.loyalty.level=gold\\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\\n    at asyn | python -m tools.resolve 'dlog:payment:00b1127d14ee5d9842f9cc6f316ffda8364ba14e3655ab2e1b063ae0c660858e' --run-dir 'runs/20261023T111643.077037Z-9461e0c3' |
| dlog:payment:229178e9feab2ca67d3289866e95bc36cebb4b23135537ec09598ef696ca3a66 | docker | {"timestamp": "2026-10-23T11:15:50.061060531Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "42e982087215cd4bdbe21223e53a5023", "evidence_id": "dlog:payment:229178e9feab2ca67d3289866e95bc36cebb4b23135537ec09598ef696ca3a66", "original_line": "2026-10-23T11:15:50.061060531Z {\"level\":\"warn\",\"time\":1792754150060,\"pid\":16,\"hostname\":\"c4595978b15c\",\"trace_id\":\"42e982087215cd4bdbe21223e53a5023\",\"span_id\":\"0f521ba8cd7485ed\",\"trace_flags\":\"01\",\"service.name\":\"payment\",\"err\":{\"type\":\"Error\",\"message\":\"Payment request failed. Invalid token. app.loyalty.level=gold\",\"stack\":\"Error: Payment request failed. Invalid token. app.loyalty.level=gold\\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\\n    at asyn | python -m tools.resolve 'dlog:payment:229178e9feab2ca67d3289866e95bc36cebb4b23135537ec09598ef696ca3a66' --run-dir 'runs/20261023T111643.077037Z-9461e0c3' |
| metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792754203.098=0.15873015873015872 | prometheus | {"metric": {"service_name": "checkout"}, "timestamp": 1792754203.098, "value": 0.15873015873015872, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792754203.098=0.15873015873015872' --run-dir 'runs/20261023T111643.077037Z-9461e0c3' |
| metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792754203.098=0.065359477124183 | prometheus | {"metric": {"service_name": "frontend-proxy"}, "timestamp": 1792754203.098, "value": 0.065359477124183, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792754203.098=0.065359477124183' --run-dir 'runs/20261023T111643.077037Z-9461e0c3' |
| metric:query{__query__="named:error_rate_by_service",service_name="load-generator"}@1792754203.098=0.061728395061728385 | prometheus | {"metric": {"service_name": "load-generator"}, "timestamp": 1792754203.098, "value": 0.061728395061728385, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="load-generator"}@1792754203.098=0.061728395061728385' --run-dir 'runs/20261023T111643.077037Z-9461e0c3' |
| metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792754203.098=0.39999999999999997 | prometheus | {"metric": {"service_name": "payment"}, "timestamp": 1792754203.098, "value": 0.39999999999999997, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792754203.098=0.39999999999999997' --run-dir 'runs/20261023T111643.077037Z-9461e0c3' |
| span:42e982087215cd4bdbe21223e53a5023/0f521ba8cd7485ed | jaeger | {"traceID": "42e982087215cd4bdbe21223e53a5023", "spanID": "0f521ba8cd7485ed", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "42e982087215cd4bdbe21223e53a5023", "spanID": "59279057aa5ab0cc"}], "startTime": 1792754150059000, "duration": 997, "tags": [{"key": "app.payment.amount", "type": "string", "value": "719.60"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge"},  | python -m tools.resolve 'span:42e982087215cd4bdbe21223e53a5023/0f521ba8cd7485ed' --run-dir 'runs/20261023T111643.077037Z-9461e0c3' |
| span:4d629da60b35aaff5b10e3baccc0771a/bb5cd8d9b30decfe | jaeger | {"traceID": "4d629da60b35aaff5b10e3baccc0771a", "spanID": "bb5cd8d9b30decfe", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "4d629da60b35aaff5b10e3baccc0771a", "spanID": "cf0817904efd5bb3"}], "startTime": 1792754166571000, "duration": 864, "tags": [{"key": "app.payment.amount", "type": "string", "value": "17745.50"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge"} | python -m tools.resolve 'span:4d629da60b35aaff5b10e3baccc0771a/bb5cd8d9b30decfe' --run-dir 'runs/20261023T111643.077037Z-9461e0c3' |
| span:5b4a94bec3a8e9f7509c2e2365c8371a/c7eacc0baf249948 | jaeger | {"traceID": "5b4a94bec3a8e9f7509c2e2365c8371a", "spanID": "c7eacc0baf249948", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "5b4a94bec3a8e9f7509c2e2365c8371a", "spanID": "dea236c5ef6a8b83"}], "startTime": 1792754162239000, "duration": 907, "tags": [{"key": "app.payment.amount", "type": "string", "value": "534.96"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge"},  | python -m tools.resolve 'span:5b4a94bec3a8e9f7509c2e2365c8371a/c7eacc0baf249948' --run-dir 'runs/20261023T111643.077037Z-9461e0c3' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261023T111643.077037Z-9461e0c3'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

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

- dependency_unavailable
- container_down
- network

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 3 tool calls; 88.02 s; stopped because confident.
