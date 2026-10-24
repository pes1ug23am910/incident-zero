# Incident: head-payment-cp3-r1

**fixed** · payment · confidence 85%

Application exception on charge requests: "Payment request failed. Invalid token. app.loyalty.level=gold" causing checkout failures that propagate to frontend and proxy.

Run: `runs/20261024T052911.098886Z-5c0b2462` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-24T05:29:10.009874+00:00 |
| Diagnosed | 2026-10-24T05:29:59.843065+00:00 |
| Approval requested | 2026-10-24T05:30:10.073475+00:00 |
| Approved | 2026-10-24T05:30:17.077372+00:00 |
| Action started | 2026-10-24T05:30:21.146047+00:00 |
| Action finished | 2026-10-24T05:30:21.365084+00:00 |
| Verified | 2026-10-24T05:33:25.963411+00:00 |
| Resolved | 2026-10-24T05:33:25.978761+00:00 |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| checkout | error_rate | 0.13740458015267176 | metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792819751.123=0.13740458015267176 |
| payment | error_rate | 0.31999999999999995 | metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792819751.123=0.31999999999999995 |
| frontend | investigation_context | Failure observed in evidence collected after the initial health overview. | metric:query{__query__="named:error_rate_by_service",service_name="frontend"}@1792819751.123=0.02276559865092749, metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792819751.124=517.4999999999993 |
| frontend-proxy | investigation_context | Failure observed in evidence collected after the initial health overview. | metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792819751.123=0.03339517625231911, metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792819751.124=652.4999999999975 |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| payment | Application exception on charge requests: "Payment request failed. Invalid token. app.loyalty.level=gold" causing checkout failures that propagate to frontend and proxy. | 85% | 95% | 85% | checkout, frontend, frontend-proxy, payment | span:2a6dedcc058dec03d1670e1393fbb069/02cd61f858545561, dlog:payment:99af6c693022455fdd9b396df1cc7d99e5f299e4ff8fa18f8cd67b6112cb2cf8, metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792819751.123=0.31999999999999995 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 4 symptom entries. |
| 2 | get_traces | Identify the concrete failing operation in checkout and see if errors coincide with calls to payment or another dependency. | [{"trace_id": "2a6dedcc058dec03d1670e1393fbb069", "duration_ms": 8669229.984, "started_at": "2026-10-24T03:04:11.508413+00:00", "ended_at": "2026-10-24T05:28:40.738397+00:00", "root_span": {"span_id": "17892cb27c7ce013", "service": "frontend-proxy", "operation": "ingress", "duration_ms": 19.219, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "02cd61f858545561", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 1.424, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.chargeServiceHandler [as charge] (/usr/src/app/index.js:21:22)", "exception.type": "Error"}}, "origin_error_spans": [{"span_id": "02cd61f858545561", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 1.424, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.charge |
| 3 | get_logs | Corroborate payment application errors seen in traces and rule out dependency/container issues by checking fresh WARN/ERROR logs from payment. | [{"timestamp": "2026-10-24T05:29:27.977151149Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "bfa4369a168acdf4e2aff360ac61ee01", "evidence_id": "dlog:payment:052b8ef4ed0b4bb73823c05a5e4d4e8e621c761028fbd67be419abeb1701200f"}, {"timestamp": "2026-10-24T05:29:27.226839119Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "940eeba06f1246e1bc4fe4dbe423597c", "evidence_id": "dlog:payment:df3d2f437a5a894f14f0a4d6440827c408d7bc6cbce119f3536243d32b582683"}, {"timestamp": "2026-10-24T05:29:24.112171487Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "61eef3bdb442face80ff3e00d2e358fb", "evidence_id": "dlog:payment:f0f00167966188d528233357445b3223fb67696edcb8f77bd04514c116cb5269"}, {"timestamp": "2026-10-24T05:29:23.675063621Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "8c4e9d5528f133be04defe055298f3f8", "evidence_id": "dlog:payment:8ad74f777306f3a343a5b1a66aff4dbd9962e4dd4225dc1147545b514f4de080"}, {"timestamp": "2026-10-24T05:29:19.562831161Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "1b42504e9b66939a12fc9255d7121609", "evidence_id": "dlog:payment:e3fd2fee4f16f76b7a990617e36cef88e60b81042bf194c148a9ba26942e3c99"}, {"timestamp": "2026-10-24T05:29:16.977991804Z", "severity": "WARN", " |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| dlog:payment:99af6c693022455fdd9b396df1cc7d99e5f299e4ff8fa18f8cd67b6112cb2cf8 | docker | {"timestamp": "2026-10-24T05:28:40.736246869Z", "severity": "WARN", "body": "Payment request failed. Invalid token. app.loyalty.level=gold", "trace_id": "2a6dedcc058dec03d1670e1393fbb069", "evidence_id": "dlog:payment:99af6c693022455fdd9b396df1cc7d99e5f299e4ff8fa18f8cd67b6112cb2cf8", "original_line": "2026-10-24T05:28:40.736246869Z {\"level\":\"warn\",\"time\":1792819720735,\"pid\":16,\"hostname\":\"c4595978b15c\",\"trace_id\":\"2a6dedcc058dec03d1670e1393fbb069\",\"span_id\":\"02cd61f858545561\",\"trace_flags\":\"01\",\"service.name\":\"payment\",\"err\":{\"type\":\"Error\",\"message\":\"Payment request failed. Invalid token. app.loyalty.level=gold\",\"stack\":\"Error: Payment request failed. Invalid token. app.loyalty.level=gold\\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\\n    at asyn | python -m tools.resolve 'dlog:payment:99af6c693022455fdd9b396df1cc7d99e5f299e4ff8fa18f8cd67b6112cb2cf8' --run-dir 'runs/20261024T052911.098886Z-5c0b2462' |
| metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792819751.123=0.13740458015267176 | prometheus | {"metric": {"service_name": "checkout"}, "timestamp": 1792819751.123, "value": 0.13740458015267176, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="checkout"}@1792819751.123=0.13740458015267176' --run-dir 'runs/20261024T052911.098886Z-5c0b2462' |
| metric:query{__query__="named:error_rate_by_service",service_name="frontend"}@1792819751.123=0.02276559865092749 | prometheus | {"metric": {"service_name": "frontend"}, "timestamp": 1792819751.123, "value": 0.02276559865092749, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="frontend"}@1792819751.123=0.02276559865092749' --run-dir 'runs/20261024T052911.098886Z-5c0b2462' |
| metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792819751.123=0.03339517625231911 | prometheus | {"metric": {"service_name": "frontend-proxy"}, "timestamp": 1792819751.123, "value": 0.03339517625231911, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="frontend-proxy"}@1792819751.123=0.03339517625231911' --run-dir 'runs/20261024T052911.098886Z-5c0b2462' |
| metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792819751.123=0.31999999999999995 | prometheus | {"metric": {"service_name": "payment"}, "timestamp": 1792819751.123, "value": 0.31999999999999995, "query": "named:error_rate_by_service"} | python -m tools.resolve 'metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792819751.123=0.31999999999999995' --run-dir 'runs/20261024T052911.098886Z-5c0b2462' |
| metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792819751.124=517.4999999999993 | prometheus | {"metric": {"service_name": "frontend"}, "timestamp": 1792819751.124, "value": 517.4999999999993, "query": "named:p95_latency_by_service"} | python -m tools.resolve 'metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792819751.124=517.4999999999993' --run-dir 'runs/20261024T052911.098886Z-5c0b2462' |
| metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792819751.124=652.4999999999975 | prometheus | {"metric": {"service_name": "frontend-proxy"}, "timestamp": 1792819751.124, "value": 652.4999999999975, "query": "named:p95_latency_by_service"} | python -m tools.resolve 'metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792819751.124=652.4999999999975' --run-dir 'runs/20261024T052911.098886Z-5c0b2462' |
| span:2a6dedcc058dec03d1670e1393fbb069/02cd61f858545561 | jaeger | {"traceID": "2a6dedcc058dec03d1670e1393fbb069", "spanID": "02cd61f858545561", "operationName": "grpc.oteldemo.PaymentService/Charge", "references": [{"refType": "CHILD_OF", "traceID": "2a6dedcc058dec03d1670e1393fbb069", "spanID": "5a4f3eabfa2bb3ce"}], "startTime": 1792819720734000, "duration": 1424, "tags": [{"key": "app.payment.amount", "type": "string", "value": "261.75"}, {"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "Payment request failed. Invalid token. app.loyalty.level=gold"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.57.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "rpc.method", "type": "string", "value": "Charge"}, | python -m tools.resolve 'span:2a6dedcc058dec03d1670e1393fbb069/02cd61f858545561' --run-dir 'runs/20261024T052911.098886Z-5c0b2462' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261024T052911.098886Z-5c0b2462'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

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
| Confidence | 85% |
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

Dry run performed: yes. Restore normal application behavior in payment; confirm with fresh telemetry.


## Approval record

Approved by Yash Verma

| Field | Value |
| --- | --- |
| Required | yes |
| Approved | yes |
| Recorded actor | Yash Verma |
| Surface | cli |
| Mode | live |
| Requested at | 2026-10-24T05:30:10.073475+00:00 |
| Approved at | 2026-10-24T05:30:17.077372+00:00 |
| Token id | sha256:aac7927f3caf40aed78e89d3963b2f5392948b470cff12326b319700602bec70 |
| Token | present (redacted) |
| Executed | yes |
| Action log | action_log:37 |

## Verification

| Signal | Before | After | Recovered | Rolled back |
| --- | --- | --- | --- | --- |
| error_rate | 0.13740458015267176 | 0.0 | yes | no |

Outcome: recovered; requests observed: 868.0578705247017.

## Action history

| Index | Decision | Executed | Outcome | Blocked |
| --- | --- | --- | --- | --- |
| 0 | approve | yes | recovered |  |

## Alternatives and escalation

- payment dependency_unavailable
- payment container_down

—

## Prevention

Proposed safeguards; validate timeout, capacity and probe settings against the service SLO before rollout. Alert snippets use the flat numeric format in `detect/thresholds.yaml`.

- payment: Gate canary promotion on error-rate regression and add a contract test for the failing operation. Alert settings: `error_rate: 0.05`, `rate_window_s: 120`, `debounce_s: 180`. Evidence: `span:2a6dedcc058dec03d1670e1393fbb069/02cd61f858545561`, `dlog:payment:99af6c693022455fdd9b396df1cc7d99e5f299e4ff8fa18f8cd67b6112cb2cf8`, `metric:query{__query__="named:error_rate_by_service",service_name="payment"}@1792819751.123=0.31999999999999995`.

## Limitations

- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.
- Recovery verifies observed signals and request counts; interrupted requests cannot be restored.

## Investigation budget

Model: openai/gpt-5; 3 tool calls; 48.74 s; stopped because confident.
