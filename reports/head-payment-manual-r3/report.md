# Incident: head-payment-manual-r3

**diagnosed** · payment · confidence 80%

Payment Charge returns application error: "Payment request failed. Invalid token"

Run: `runs/20261024T051407.384676Z-43429953` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-24T05:14:05.872259+00:00 |
| Diagnosed | 2026-10-24T05:14:38.308823+00:00 |
| Approval requested | — |
| Approved | — |
| Action started | — |
| Action finished | — |
| Verified | — |
| Resolved | — |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| checkout | error_rate | 0.05555555555555555 | metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792818847.414=0.05555555555555555, metric:query{__query__="named:p95_latency_by_service",service_name="checkout"}@1792818847.414=1040.0000000000005 |
| payment | error_rate | 0.14285714285714285 | metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792818847.414=0.14285714285714285 |
| frontend | investigation_context | Failure observed in evidence collected after the initial health overview. | metric:query{__query__="named:error_rate_by_service",service_name="frontend"}@1792818847.414=0.011235955056179777, metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792818847.414=866.2500000000005 |
| frontend-proxy | investigation_context | Failure observed in evidence collected after the initial health overview. | metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792818847.414=0.015151515151515154, metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792818847.414=869.9999999999993 |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| payment | Payment Charge returns application error: "Payment request failed. Invalid token" | 80% | 95% | 80% | checkout, frontend, frontend-proxy, payment | span:60fe138af54d3714adc2bdedea7f4e9a/d5c17d2ca09c13ef, dlog:payment:9261cb3e939831163927c08cf3aa0310a64148af2a2192e92d3f588358eb5023, metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792818847.414=0.14285714285714285 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 4 symptom entries. |
| 2 | get_traces | Inspect checkout error traces to identify the failing operation and whether errors stem from the payment dependency. | [{"trace_id": "60fe138af54d3714adc2bdedea7f4e9a", "duration_ms": 8669327.211, "started_at": "2026-10-24T02:49:12.967127+00:00", "ended_at": "2026-10-24T05:13:42.294338+00:00", "root_span": {"span_id": "54c48c1b4ee1c7e4", "service": "frontend-proxy", "operation": "ingress", "duration_ms": 45.007, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "d5c17d2ca09c13ef", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 21.626, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.chargeServiceHandler [as charge] (/usr/src/app/index.js:21:22)", "exception.type": "Error"}}, "origin_error_spans": [{"span_id": "d5c17d2ca09c13ef", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 21.626, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.char |
| 3 | get_logs | Corroborate the payment application error seen in traces and confirm it’s a local failure, not a dependency outage. | [{"timestamp": "2026-10-24T05:14:13.023085413Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "46c18a9ddeec4b6bf1a3557feb7d25b1", "evidence_id": "dlog:payment:4f481e799c37521eb9be95d3b738d29d5857bec8b0600fdfdbb2c3762a1b1719"}, {"timestamp": "2026-10-24T05:13:42.282556071Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "60fe138af54d3714adc2bdedea7f4e9a", "evidence_id": "dlog:payment:9261cb3e939831163927c08cf3aa0310a64148af2a2192e92d3f588358eb5023"}] |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| dlog:payment:9261cb3e939831163927c08cf3aa0310a64148af2a2192e92d3f588358eb5023 | docker | {"timestamp": "2026-10-24T05:13:42.282556071Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "60fe138af54d3714adc2bdedea7f4e9a", "evidence_id": "dlog:payment:9261cb3e939831163927c08cf3aa0310a64148af2a2192e92d3f588358eb5023", "original_line": "2026-10-24T05:13:42.282556071Z {\"level\":\"warn\",\"time\":1792818822279,\"pid\":16,\"hostname\":\"c4595978b15c\",\"trace_id\":\"60fe138af54d3714adc2bdedea7f4e9a\",\"span_id\":\"d5c17d2ca09c13ef\",\"trace_flags\":\"01\",\"service.name\":\"payment\",\"err\":{\"type\":\"Error\",\"message\":\"Payment request failed. Invalid token. app.loyalty.level=gold\",\"stack\":\"Error: Payment request failed. Invalid token. app.loyalty.level=gold\\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\\n    at asyn | python -m tools.resolve 'dlog:payment:9261cb3e939831163927c08cf3aa0310a64148af2a2192e92d3f588358eb5023' --run-dir 'runs/20261024T051407.384676Z-43429953' |
| metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792818847.414=0.05555555555555555 | prometheus | {"metric": {"service_name": "checkout"}, "timestamp": 1792818847.414, "value": 0.05555555555555555, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792818847.414=0.05555555555555555' --run-dir 'runs/20261024T051407.384676Z-43429953' |
| metric:query{__query__="named:error_rate_by_service",service_name="frontend"}@1792818847.414=0.011235955056179777 | prometheus | {"metric": {"service_name": "frontend"}, "timestamp": 1792818847.414, "value": 0.011235955056179777, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="frontend"}@1792818847.414=0.011235955056179777' --run-dir 'runs/20261024T051407.384676Z-43429953' |
| metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792818847.414=0.015151515151515154 | prometheus | {"metric": {"service_name": "frontend-proxy"}, "timestamp": 1792818847.414, "value": 0.015151515151515154, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792818847.414=0.015151515151515154' --run-dir 'runs/20261024T051407.384676Z-43429953' |
| metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792818847.414=0.14285714285714285 | prometheus | {"metric": {"service_name": "payment"}, "timestamp": 1792818847.414, "value": 0.14285714285714285, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792818847.414=0.14285714285714285' --run-dir 'runs/20261024T051407.384676Z-43429953' |
| metric:query{__query__="named:p95_latency_by_service",service_name="checkout"}@1792818847.414=1040.0000000000005 | prometheus | {"metric": {"service_name": "checkout"}, "timestamp": 1792818847.414, "value": 1040.0000000000005, "query": "named:p95_latency_by_service"} | python -m tools.resolve 'metric:query{__query__="named:p95_latency_by_service",service_name="checkout"}@1792818847.414=1040.0000000000005' --run-dir 'runs/20261024T051407.384676Z-43429953' |
| metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792818847.414=866.2500000000005 | prometheus | {"metric": {"service_name": "frontend"}, "timestamp": 1792818847.414, "value": 866.2500000000005, "query": "named:p95_latency_by_service"} | python -m tools.resolve 'metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792818847.414=866.2500000000005' --run-dir 'runs/20261024T051407.384676Z-43429953' |
| metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792818847.414=869.9999999999993 | prometheus | {"metric": {"service_name": "frontend-proxy"}, "timestamp": 1792818847.414, "value": 869.9999999999993, "query": "named:p95_latency_by_service"} | python -m tools.resolve 'metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792818847.414=869.9999999999993' --run-dir 'runs/20261024T051407.384676Z-43429953' |
| span:60fe138af54d3714adc2bdedea7f4e9a/d5c17d2ca09c13ef | jaeger | {"traceID": "60fe138af54d3714adc2bdedea7f4e9a", "spanID": "d5c17d2ca09c13ef", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "60fe138af54d3714adc2bdedea7f4e9a", "spanID": "b0a5940d0cd3c45f"}], "startTime": 1792818822262000, "duration": 21626, "tags": [{"key": "app.payment.amount", "type": "string", "value": "11127.34"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge | python -m tools.resolve 'span:60fe138af54d3714adc2bdedea7f4e9a/d5c17d2ca09c13ef' --run-dir 'runs/20261024T051407.384676Z-43429953' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261024T051407.384676Z-43429953'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

## Impact

| Field | Assessment |
| --- | --- |
| Approval tier | T2 |
| Score | 61.0/100 |
| Business criticality | critical |
| Journeys affected | checkout, payment |
| Estimated users affected | Not measured: telemetry counts spans and requests, not distinct users. |
| Blast radius | single_service |
| Reversibility | instant |
| Data risk | none |
| Confidence | 80% |
| Rationale | A critical service or process restart requires the full evidence table, a reviewer or the independent-source check, and explicit typed yes. |
| Decision | REQUIRE_HUMAN |
| Reason codes | CRITICAL_SERVICE |
| Uncertainty | 0.050000000000000044 |
| Observability gap | 0.0 |

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

- payment dependency_unavailable
- checkout application error

—

## Prevention

Proposed safeguards; validate timeout, capacity and probe settings against the service SLO before rollout. Alert snippets use the flat numeric format in `detect/thresholds.yaml`.

- payment: Gate canary promotion on error-rate regression and add a contract test for the failing operation. Alert settings: `error_rate: 0.05`, `rate_window_s: 120`, `debounce_s: 180`. Evidence: `span:60fe138af54d3714adc2bdedea7f4e9a/d5c17d2ca09c13ef`, `dlog:payment:9261cb3e939831163927c08cf3aa0310a64148af2a2192e92d3f588358eb5023`, `metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792818847.414=0.14285714285714285`.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 3 tool calls; 30.92 s; stopped because confident.
