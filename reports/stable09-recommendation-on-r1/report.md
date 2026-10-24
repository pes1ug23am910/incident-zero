# Incident: stable09-recommendation-on-r1

**diagnosed** · recommendation · confidence 80%

recommendation container exited; callers encounter DNS/connection failures to recommendation, inflating frontend and proxy latency

Run: `runs/20261024T023315.758052Z-0903788b` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-24T02:33:14.002506+00:00 |
| Diagnosed | 2026-10-24T02:34:01.200785+00:00 |
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
| frontend | investigation_context | Failure observed in evidence collected after the initial health overview. | metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792809195.808=575.0000000000049, trace:e50c7a53683338a227d600fc4f6b49cc |
| frontend-proxy | investigation_context | Failure observed in evidence collected after the initial health overview. | trace:e50c7a53683338a227d600fc4f6b49cc, span:e50c7a53683338a227d600fc4f6b49cc/83a5bd19abe3c374 |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| recommendation | recommendation container exited; callers encounter DNS/connection failures to recommendation, inflating frontend and proxy latency | 80% | 90% | 80% | frontend, frontend-proxy, recommendation | container:recommendation:Status=exited, span:d15f24d1ca3262f8ea03b72ae69ae5b7/3a6656f2cd733c98, span:d15f24d1ca3262f8ea03b72ae69ae5b7/f5123f34bc5a5d47, metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792809195.808=575.0000000000049, metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792809195.808=404.99999999999613 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 3 symptom entries. |
| 2 | get_logs | Corroborate that the exited recommendation container is impacting callers by checking fresh frontend connection errors to recommendation within the last 120s. | [] |
| 3 | get_traces | Inspect frontend error traces in the last 600s to corroborate caller connection failures to the exited recommendation container and strengthen the container_down hypothesis. | [{"trace_id": "e50c7a53683338a227d600fc4f6b49cc", "duration_ms": 8359068.031, "started_at": "2026-10-24T00:05:16.735073+00:00", "ended_at": "2026-10-24T02:24:35.803104+00:00", "root_span": {"span_id": "2d4f7279014313a4", "service": "frontend-proxy", "operation": "ingress", "duration_ms": 26.331, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "52aed96295de7ff3", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 0.776, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.chargeServiceHandler [as charge] (/usr/src/app/index.js:21:22)", "exception.type": "Error"}}, "origin_error_spans": [{"span_id": "52aed96295de7ff3", "service": "payment", "operation": "grpc.oteldemo.PaymentService/Charge", "duration_ms": 0.776, "status_message": "", "exception": {"exception.message": "Payment request failed. Invalid token. app.loyalty.level=gold", "exception.stacktrace": "Error: Payment request failed. Invalid token. app.loyalty.level=gold\n    at module.exports.charge (/usr/src/app/charge.js:37:13)\n    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)\n    at async Object.charge |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:recommendation:Status=exited | docker | {"name": "recommendation", "field": "Status", "value": "exited"} | python -m tools.resolve 'container:recommendation:Status=exited' --run-dir 'runs/20261024T023315.758052Z-0903788b' |
| metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792809195.808=575.0000000000049 | prometheus | {"metric": {"service_name": "frontend"}, "timestamp": 1792809195.808, "value": 575.0000000000049, "query": "named:p95_latency_by_service"} | python -m tools.resolve 'metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792809195.808=575.0000000000049' --run-dir 'runs/20261024T023315.758052Z-0903788b' |
| metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792809195.808=404.99999999999613 | prometheus | {"metric": {"service_name": "frontend-proxy"}, "timestamp": 1792809195.808, "value": 404.99999999999613, "query": "named:p95_latency_by_service"} | python -m tools.resolve 'metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792809195.808=404.99999999999613' --run-dir 'runs/20261024T023315.758052Z-0903788b' |
| span:d15f24d1ca3262f8ea03b72ae69ae5b7/3a6656f2cd733c98 | jaeger | {"traceID": "d15f24d1ca3262f8ea03b72ae69ae5b7", "spanID": "3a6656f2cd733c98", "operationName": "dns.lookup", "references": [], "startTime": 1792809192691000, "duration": 5007258, "tags": [{"key": "dns.error_message", "type": "string", "value": "getaddrinfo EAI_AGAIN recommendation"}, {"key": "dns.error_name", "type": "string", "value": "Error"}, {"key": "error", "type": "bool", "value": true}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-dns"}, {"key": "otel.scope.version", "type": "string", "value": "0.43.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "otel.status_description", "type": "string", "value": "getaddrinfo EAI_AGAIN recommendation"}, {"key": "span.kind", "type": "string", "value": "client"}], "logs": [], "processID": "p1", "warnings": ["invalid parent span IDs=be69158ef83b3989; skipping clock skew adjustm | python -m tools.resolve 'span:d15f24d1ca3262f8ea03b72ae69ae5b7/3a6656f2cd733c98' --run-dir 'runs/20261024T023315.758052Z-0903788b' |
| span:d15f24d1ca3262f8ea03b72ae69ae5b7/f5123f34bc5a5d47 | jaeger | {"traceID": "d15f24d1ca3262f8ea03b72ae69ae5b7", "spanID": "f5123f34bc5a5d47", "operationName": "router frontend egress", "references": [{"refType": "CHILD_OF", "traceID": "d15f24d1ca3262f8ea03b72ae69ae5b7", "spanID": "be79550eeb5e4f16"}], "startTime": 1792809192688446, "duration": 14998172, "tags": [{"key": "canceled", "type": "string", "value": "true"}, {"key": "component", "type": "string", "value": "proxy"}, {"key": "error", "type": "string", "value": "true"}, {"key": "http.protocol", "type": "string", "value": "HTTP/1.1"}, {"key": "http.status_code", "type": "string", "value": "0"}, {"key": "peer.address", "type": "string", "value": "172.23.0.14:8080"}, {"key": "response_flags", "type": "string", "value": "-"}, {"key": "span.kind", "type": "string", "value": "client"}, {"key": "upstream_address", "type": "string", "value": "172.23.0.14:8080"}, {"key": "upstream_cluster", "type": "str | python -m tools.resolve 'span:d15f24d1ca3262f8ea03b72ae69ae5b7/f5123f34bc5a5d47' --run-dir 'runs/20261024T023315.758052Z-0903788b' |
| span:e50c7a53683338a227d600fc4f6b49cc/83a5bd19abe3c374 | jaeger | {"traceID": "e50c7a53683338a227d600fc4f6b49cc", "spanID": "83a5bd19abe3c374", "operationName": "POST", "references": [{"refType": "CHILD_OF", "traceID": "e50c7a53683338a227d600fc4f6b49cc", "spanID": "afba4302e13cf497"}], "startTime": 1792808675776000, "duration": 26384, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "http.flavor", "type": "string", "value": "1.1"}, {"key": "http.host", "type": "string", "value": "frontend-proxy:8080"}, {"key": "http.method", "type": "string", "value": "POST"}, {"key": "http.request_content_length_uncompressed", "type": "int64", "value": 372}, {"key": "http.scheme", "type": "string", "value": "http"}, {"key": "http.status_code", "type": "int64", "value": 500}, {"key": "http.status_text", "type": "string", "value": "INTERNAL SERVER ERROR"}, {"key": "http.target", "type": "string", "value": "/api/checkout"}, {"key": "http.url", "type": "s | python -m tools.resolve 'span:e50c7a53683338a227d600fc4f6b49cc/83a5bd19abe3c374' --run-dir 'runs/20261024T023315.758052Z-0903788b' |
| trace:e50c7a53683338a227d600fc4f6b49cc | jaeger | {"traceID": "e50c7a53683338a227d600fc4f6b49cc", "warnings": null, "spans": [{"traceID": "e50c7a53683338a227d600fc4f6b49cc", "spanID": "839837bd1db9dc98", "operationName": "oteldemo.ShippingService/GetQuote", "references": [{"refType": "CHILD_OF", "traceID": "e50c7a53683338a227d600fc4f6b49cc", "spanID": "22af64c39b366ae7"}], "startTime": 1792808675794082, "duration": 2110, "tags": [{"key": "net.sock.peer.addr", "type": "string", "value": "172.23.0.3"}, {"key": "net.sock.peer.port", "type": "int64", "value": 50050}, {"key": "otel.scope.name", "type": "string", "value": "go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"}, {"key": "otel.scope.version", "type": "string", "value": "0.60.0"}, {"key": "rpc.grpc.status_code", "type": "int64", "value": 0}, {"key": "rpc.method", "type": "string", "value": "GetQuote"}, {"key": "rpc.service", "type": "string", "value": "ote | python -m tools.resolve 'trace:e50c7a53683338a227d600fc4f6b49cc' --run-dir 'runs/20261024T023315.758052Z-0903788b' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261024T023315.758052Z-0903788b'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

## Impact

| Field | Assessment |
| --- | --- |
| Approval tier | T2 |
| Score | 51.0/100 |
| Business criticality | auxiliary |
| Journeys affected | recommendations |
| Estimated users affected | Not measured: telemetry counts spans and requests, not distinct users. |
| Blast radius | single_service |
| Reversibility | self_healing |
| Data risk | none |
| Confidence | 80% |
| Rationale | A critical service or process restart requires the full evidence table, a reviewer or the independent-source check, and explicit typed yes. |
| Decision | REQUIRE_HUMAN |
| Reason codes | RESTART_REQUIRES_HUMAN |
| Uncertainty | 0.09999999999999998 |
| Observability gap | 0.2 |

## Proposed action

**1. restart_service** → recommendation

Reason: Restore the diagnosed unavailable component recommendation. Runbook: kb:container-down#remediation; validated against the action allowlist.

Risk: Restart may interrupt in-flight work; review state and evidence before approval.

Parameters: `{"service": "recommendation"}`

Dry run performed: no. Start a fresh recommendation process and restore its availability to callers.


## What the agent consulted

Retrieval: bm25. Runbooks and memories are hints, not evidence.

### kb:recommendation#investigation

Score: 2.905; source: `knowledge/runbooks/recommendation.md`; version: 1; SHA-256: `cfbb47d7764d7321e723577341825c90f9164d6c98ab5f009555f24798a056a0`.

> # Recommendation availability and memory growth  ## What to check first Read `get_container_health(names=["recommendation", "product-catalog"])`, `get_metrics(promql="container_memory", lookback_s=900)` and `get_metrics(promql="p95_latency_by_service", lookback_s=900)`. Use `get_traces(service="recommendation", errors_only=False, lookback_s=300)` for internal work and product-list counts, and `get_logs(service="recommendation", severity_min="INFO", lookback_s=300)` for cache hit/miss and startup patterns.

### kb:resource-starvation#investigation

Score: 2.049; source: `knowledge/runbooks/resource-starvation.md`; version: 1; SHA-256: `c74f25b5b7d7d12be267422856c8740a8fa42d9832bfad3ffb68d77eab39500c`.

> # CPU or memory starvation  ## What to check first Use `get_container_health(names=[<suspect>])` for NanoCpus, Memory, RestartCount and current usage. Read `get_metrics(promql="container_cpu", lookback_s=600)`, `get_metrics(promql="container_memory", lookback_s=600)` and `get_metrics(promql="p95_latency_by_service", lookback_s=600)`. Compare `get_traces(service=<suspect>, errors_only=False, lookback_s=300)` with startup/error logs.

### kb:restart-loop#investigation

Score: 2.006; source: `knowledge/runbooks/restart-loop.md`; version: 1; SHA-256: `4f248e1c1c4826036a86f8cd3de65c8ba060fd3c86c738bc28a93b79def9d00f`.

> # Repeated container restarts  ## What to check first Compare repeated `get_container_health(names=[<suspect>])` observations. Use `get_logs(service=<suspect>, severity_min="INFO", lookback_s=600)` for startup and failure messages, `get_metrics(promql="container_memory", lookback_s=600)` for memory shape, and `get_deploy_history(lookback_s=3600)` for recent starts. Check caller failures with `get_traces(service=<caller>, errors_only=True, lookback_s=600)`.

### kb:container-down#remediation

Score: 4.854; source: `knowledge/runbooks/container-down.md`; version: 1; SHA-256: `6c4dbbadd9b843bbdfeb0cbec97ac3c8ff9b641dcb78f5758f442a129e7bc2e2`.

> # A service container is down  ## Allowed remediation Propose Action API `restart_service` with `service=<down component>`, after the policy checks target and risk. Obtain a dry run and human approval. Stateful dependencies need review of persistence and interruption risk before any restart is approved.

### kb:telemetry-outage#remediation

Score: 1.308; source: `knowledge/runbooks/telemetry-outage.md`; version: 1; SHA-256: `fffb4093dd1d073babd03b58220dfa053bb6c64e53f369f0d833c706d91b4bc7`.

> # Telemetry is missing or stale  ## Allowed remediation Escalate the observability gap and preserve partial evidence. Do not propose an application fix from missing data. If an independent diagnosis later establishes a stopped, allowlisted telemetry component, apply the container-down runbook with its own risk review and approval.

### kb:recommendation#remediation

Score: 0.583; source: `knowledge/runbooks/recommendation.md`; version: 1; SHA-256: `cfbb47d7764d7321e723577341825c90f9164d6c98ab5f009555f24798a056a0`.

> # Recommendation availability and memory growth  ## Allowed remediation For an evidenced local application workload fault, propose Action API `toggle_flag` with `service=recommendation`. For a stopped component, propose `restart_service` after checking dependencies. Resource-limit repair is outside the allowlist and escalates. Every proposal requires policy validation, dry run and human approval.

### kb:service-recommendation#overview

Score: 1.707; source: `knowledge/services.yaml`; version: 1; SHA-256: `b22ecaa530ca5eeaaf9c804a6946892266afebe1168a63c8ec075c4a51f37416`.

> {"criticality":"auxiliary","dependencies":["otel-collector","product-catalog"],"purpose":"Recommends related products using catalogue data.","runbooks":["recommendation","container-down","restart-loop","dependency-unavailable"],"service":"recommendation","telemetry_hints":["get_container_health for lifecycle and resource limits","error_rate_by_service, p95_latency_by_service and rps_by_service","Use fresh traces and logs when the service emits them; missing data is unknown"],"typical_operations":["ListRecommendations","get_product_list"]}


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

- dependency_unavailable: recommendation
- network: transient DNS
- application_flag: frontend

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 3 tool calls; 56.54 s; stopped because confident.
