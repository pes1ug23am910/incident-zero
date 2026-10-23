# Incident: payment-failure-r5

**diagnosed** · payment · confidence 90%

Local application exception during grpc.oteldemo.PaymentService/Charge with error "Payment request failed. Invalid token. app.loyalty.level=gold" propagating to checkout and callers.

Run: `runs/20261023T113346.104216Z-514905da` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T11:33:45.026533+00:00 |
| Diagnosed | 2026-10-23T11:34:44.482769+00:00 |
| Approval requested | — |
| Approved | — |
| Action started | — |
| Action finished | — |
| Verified | — |
| Resolved | — |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| checkout | error_rate | 0.10526315789473685 | metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792755226.124=0.10526315789473685 |
| payment | error_rate | 0.2 | metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792755226.124=0.2 |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| payment | Local application exception during grpc.oteldemo.PaymentService/Charge with error "Payment request failed. Invalid token. app.loyalty.level=gold" propagating to checkout and callers. | 90% | 95% | 90% | checkout, payment | span:9aa98be4d38becccbec4c03a9f937336/b16fb018fb635c3b, span:6dbec879ef0402d09d8b6d57318561ad/616710e9363c0763, dlog:payment:3094a9920ab0dec31e7abbf87c2ba0fef437920e112813e7f4d7061505fb40fb, metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792755226.124=0.2 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 2 symptom entries. |
| 2 | get_traces | Identify the failing operation in checkout and see if errors originate from a downstream call (e.g., payment) or a local checkout exception. | [{"trace_id": "9aa98be4d38becccbec4c03a9f937336", "duration_ms": 853.67, "root_span": {"span_id": "9a8f2e5d5b2e3a9a", "service": "load-generator", "operation": "POST", "duration_ms": 19.279, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "b16fb018fb635c3b", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 1.023, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.chargeServiceHandler [as charge] (/usr/src/app/index.js:21:22)", "exception.type": "Error"}}, "origin_error_spans": [{"span_id": "b16fb018fb635c3b", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 1.023, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.chargeServiceHandler [as charge] (/usr/src/app/index.js:21:22)", "exception.type": "Error"}}, {"span_id": "4843b |
| 3 | get_logs | Corroborate the payment application exception seen in error traces and rule out dependency or container issues by checking fresh WARN/ERROR logs for the same failing operation and error text. | [{"timestamp": "2026-10-23T11:33:56.303299012Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "da8752ba6b99e167dfdcc2498029380f", "evidence_id": "dlog:payment:9a6cf3f3ff7d76cafed2d9ece63f441427018335e2bc014ebe79e1d1b66d6c4b"}, {"timestamp": "2026-10-23T11:33:43.032247917Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "b79093fe9d1cdb099f962604bfd08147", "evidence_id": "dlog:payment:a047448acf9f98e9f5be787f44d350d534381194b074c1216c693241e75d912c"}, {"timestamp": "2026-10-23T11:33:33.841814397Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "9aa98be4d38becccbec4c03a9f937336", "evidence_id": "dlog:payment:3094a9920ab0dec31e7abbf87c2ba0fef437920e112813e7f4d7061505fb40fb"}, {"timestamp": "2026-10-23T11:33:16.299586145Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "6dbec879ef0402d09d8b6d57318561ad", "evidence_id": "dlog:payment:70efaa46f703efcadda66b6744f4f58136649e946d7bc299261358d1646d27ef"}] |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| dlog:payment:3094a9920ab0dec31e7abbf87c2ba0fef437920e112813e7f4d7061505fb40fb | docker | {"timestamp": "2026-10-23T11:33:33.841814397Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "9aa98be4d38becccbec4c03a9f937336", "evidence_id": "dlog:payment:3094a9920ab0dec31e7abbf87c2ba0fef437920e112813e7f4d7061505fb40fb", "original_line": "2026-10-23T11:33:33.841814397Z {\"level\":\"warn\",\"time\":1792755213840,\"pid\":16,\"hostname\":\"c4595978b15c\",\"trace_id\":\"9aa98be4d38becccbec4c03a9f937336\",\"span_id\":\"b16fb018fb635c3b\",\"trace_flags\":\"01\",\"service.name\":\"payment\",\"err\":{\"type\":\"Error\",\"message\":\"Payment request failed. Invalid token. app.loyalty.level=gold\",\"stack\":\"Error: Payment request failed. Invalid token. app.loyalty.level=gold\\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\\n    at asyn | python -m tools.resolve 'dlog:payment:3094a9920ab0dec31e7abbf87c2ba0fef437920e112813e7f4d7061505fb40fb' --run-dir 'runs/20261023T113346.104216Z-514905da' |
| metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792755226.124=0.10526315789473685 | prometheus | {"metric": {"service_name": "checkout"}, "timestamp": 1792755226.124, "value": 0.10526315789473685, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792755226.124=0.10526315789473685' --run-dir 'runs/20261023T113346.104216Z-514905da' |
| metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792755226.124=0.2 | prometheus | {"metric": {"service_name": "payment"}, "timestamp": 1792755226.124, "value": 0.2, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792755226.124=0.2' --run-dir 'runs/20261023T113346.104216Z-514905da' |
| span:6dbec879ef0402d09d8b6d57318561ad/616710e9363c0763 | jaeger | {"traceID": "6dbec879ef0402d09d8b6d57318561ad", "spanID": "616710e9363c0763", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "6dbec879ef0402d09d8b6d57318561ad", "spanID": "ae6f827e6f23bb1b"}], "startTime": 1792755196291000, "duration": 8266, "tags": [{"key": "app.payment.amount", "type": "string", "value": "97.69"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge"},  | python -m tools.resolve 'span:6dbec879ef0402d09d8b6d57318561ad/616710e9363c0763' --run-dir 'runs/20261023T113346.104216Z-514905da' |
| span:9aa98be4d38becccbec4c03a9f937336/b16fb018fb635c3b | jaeger | {"traceID": "9aa98be4d38becccbec4c03a9f937336", "spanID": "b16fb018fb635c3b", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "9aa98be4d38becccbec4c03a9f937336", "spanID": "dc60ef2c3ff3449d"}], "startTime": 1792755213840000, "duration": 1023, "tags": [{"key": "app.payment.amount", "type": "string", "value": "19600.43"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge" | python -m tools.resolve 'span:9aa98be4d38becccbec4c03a9f937336/b16fb018fb635c3b' --run-dir 'runs/20261023T113346.104216Z-514905da' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261023T113346.104216Z-514905da'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

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

- Checkout mishandling payment errors
- Downstream dependency of payment failing
- Intermittent network timeouts

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 3 tool calls; 58.38 s; stopped because confident.
