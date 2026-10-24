# Incident: stable09-recommendation-on-r2

**diagnosed** · recommendation · confidence 90%

Container exited; frontend calls to RecommendationService fail with 14 UNAVAILABLE and EHOSTUNREACH

Run: `runs/20261024T024152.039733Z-dc7d26df` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-24T02:41:51.011326+00:00 |
| Diagnosed | 2026-10-24T02:44:29.975749+00:00 |
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
| frontend | investigation_context | Failure observed in evidence collected after the initial health overview. | metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792809697.071=860.0000000000032, dlog:frontend:3e6006802b76bf49b1123fe2c6a2efc408a10de2b70abe7832701572ffe94aea |
| frontend-proxy | investigation_context | Failure observed in evidence collected after the initial health overview. | metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792809697.071=874.9999999999933, trace:c6fcdf7dceb5b4d2c9edcf92172ba3aa |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| recommendation | Container exited; frontend calls to RecommendationService fail with 14 UNAVAILABLE and EHOSTUNREACH | 90% | 90% | 90% | frontend, frontend-proxy, recommendation | container:recommendation:Status=exited, dlog:frontend:32126efb0b28920bfb2368c16057f62780b3299cd51c3209ed2f405e289bebd2, span:c6fcdf7dceb5b4d2c9edcf92172ba3aa/faed1a9a8ebf2559 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 3 symptom entries. |
| 2 | get_traces | Find failing frontend calls to recommendation after its container exited, to corroborate container_down with caller error spans and error text. | [{"trace_id": "4aeaaef617689b4bea701e0f9ed7a61a", "duration_ms": 8359000.973, "started_at": "2026-10-24T00:22:38.864148+00:00", "ended_at": "2026-10-24T02:41:57.865121+00:00", "root_span": {"span_id": "f2f187294e69bd85", "service": "frontend-proxy", "operation": "ingress", "duration_ms": 48.956, "status_message": "", "exception": {}}, "first_error_span": null, "origin_error_spans": [], "error_spans": [], "services": ["cart", "checkout", "currency", "email", "frontend", "frontend-proxy", "payment", "product-catalog", "quote", "shipping"]}, {"trace_id": "ea64ffe05558759b450e12411f32383c", "duration_ms": 6.314, "started_at": "2026-10-24T02:41:58.218055+00:00", "ended_at": "2026-10-24T02:41:58.224369+00:00", "root_span": {"span_id": "51bdc2f0fc954a11", "service": "frontend-proxy", "operation": "ingress", "duration_ms": 6.314, "status_message": "", "exception": {}}, "first_error_span": null, "origin_error_spans": [], "error_spans": [], "services": ["frontend", "frontend-proxy", "product-catalog"]}, {"trace_id": "ad096090c12e97e688ee8f6a0f9a730a", "duration_ms": 7.463, "started_at": "2026-10-24T02:41:58.521214+00:00", "ended_at": "2026-10-24T02:41:58.528677+00:00", "root_span": {"span_id": "98adcd5d07efc4ab", "service": "frontend-proxy", "operation": "ingress", "duration_ms": 7.463, "status_message": "", "exception": {}}, "first_error_span": null, "origin_error_spans": [], "error_spans": [], "services": ["frontend", "frontend-proxy", "product-catalog"]}, {"trace_id": "7d312d8f4bacc |
| 3 | get_logs | Corroborate the exited recommendation container by finding fresh frontend INFO/WARN messages about failing to call the recommendation backend (connection refused/timeouts). | [] |
| 4 | get_logs | Broaden search to catch frontend connection failures/timeouts to the exited recommendation backend and explain elevated frontend latency. | [{"timestamp": "2026-10-24T02:34:21.736331834Z", "severity": "UNKNOWN", "body": "}", "trace_id": null, "evidence_id": "dlog:frontend:7756a5664d2486984eb929db54e90def29ecdd1d478dc21df3c336692f085345"}, {"timestamp": "2026-10-24T02:34:21.736330546Z", "severity": "UNKNOWN", "body": "  metadata: [Metadata]", "trace_id": null, "evidence_id": "dlog:frontend:84a3b7a1eaa4cb7662d6876608a5492b57ae8f6ec1d3a8135e4c83a0a68b1850"}, {"timestamp": "2026-10-24T02:34:21.736329064Z", "severity": "ERROR", "body": "  details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T02:34:11.551Z)',", "trace_id": null, "evidence_id": "dlog:frontend:3e6006802b76bf49b1123fe2c6a2efc408a10de2b70abe7832701572ffe94aea"}, {"timestamp": "2026-10-24T02:34:21.736327862Z", "severity": "UNKNOWN", "body": "  code: 14,", "trace_id": null, "evidence_id": "dlog:frontend:05f2d79d4eb3c70a2ee7b731dfeb872152958676d911652c1cdb57115cc6c322"}, {"timestamp": "2026-10-24T02:34:21.736326306Z", "severity": "UNKNOWN", "body": "    at new Promise (<anonymous>) {", "trace_id": null, "evidence_id": "dlog:frontend:8e3302fa510fcaa2185d1085338616317ea525381c63a152e9e75c46332c45a0"}, {"timestamp": "2026-10-24T02:34:21.736324292Z", "severity": "UNKNOWN", "body": "    at <unknown> (.next/server/pages/api/recommendations.js:1:321)", "trace_id": null, "evidence_id": "dlog:frontend:fad3b9d988cd5a123820d431caa63328bbc72bbe077e5cccd83930421551da99"}, {"timestamp": "2026-10-24T02:34:21.736296283Z", "severit |
| 5 | get_logs | Corroborate that recommendation is down by finding its own startup/exit errors around 02:34, adding an independent source to the container status and frontend UNAVAILABLE/EHOSTUNREACH logs. | [{"timestamp": "2026-10-24T02:41:43.682626048Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['LS4PSXUNUM', '66VCHSJNUP', 'L9ECAV7KIM', '9SIQT8TOJO', '1YMWWN1N4O']", "logger_scope": "main", "trace_id": "8852095d37b2d433e138873d7d604979", "evidence_id": "log:otel/fgbJa6EBzXeOHxa7KZWV"}, {"timestamp": "2026-10-24T02:41:39.992268032Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['HQTGWGPNH4', '9SIQT8TOJO', '2ZYFJ3GM2N', 'LS4PSXUNUM', '6E92ZMYYFZ']", "logger_scope": "main", "trace_id": "c8c252b2d3f485c1a822fcbe7241e820", "evidence_id": "log:otel/UgbJa6EBzXeOHxa7FZW-"}, {"timestamp": "2026-10-24T02:41:36.923548928Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['0PUK6V6EV0', 'LS4PSXUNUM', '6E92ZMYYFZ', '2ZYFJ3GM2N', '9SIQT8TOJO']", "logger_scope": "main", "trace_id": "bbfd031704e833b9e801ad068b502a36", "evidence_id": "log:otel/NQbJa6EBzXeOHxa7ApUr"}, {"timestamp": "2026-10-24T02:41:32.593846784Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['OLJCESPC7Z', 'L9ECAV7KIM', '6E92ZMYYFZ', 'HQTGWGPNH4', 'LS4PSXUNUM']", "logger_scope": "main", "trace_id": "168a68a16b4a57006715d2e9f5884fd8", "evidence_id": "log:otel/FgbIa6EBzXeOHxa77pWa"}, {"timestamp": "2026-10-24T02:41:25.15257344Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['66VCHSJNUP', 'L9ECAV7KIM', 'HQTGWGPNH4', 'LS4PSXUNUM', '0PUK6V6EV0']", "logger_scope": "main", "trace_id": "c27e2f7ef |
| 6 | get_traces | Find fresh frontend error spans to recommendation around the reported exit (~02:41:51Z) to corroborate container_down with caller failures and error text, versus network or a healthy backend. | [{"trace_id": "c6fcdf7dceb5b4d2c9edcf92172ba3aa", "duration_ms": 6.427, "started_at": "2026-10-24T02:43:24.502860+00:00", "ended_at": "2026-10-24T02:43:24.509287+00:00", "root_span": {"span_id": "68e65c378214b911", "service": "frontend-proxy", "operation": "ingress", "duration_ms": 6.416, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "faed1a9a8ebf2559", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 1.005, "status_message": "14", "exception": {}}, "origin_error_spans": [{"span_id": "faed1a9a8ebf2559", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 1.005, "status_message": "14", "exception": {}}, {"span_id": "90ff835c46b40158", "service": "frontend", "operation": "GET", "duration_ms": 5.809, "status_message": "", "exception": {}}], "error_spans": [{"span_id": "faed1a9a8ebf2559", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 1.005, "status_message": "14", "exception": {}}, {"span_id": "6f2997b0d8b43f72", "service": "frontend", "operation": "executing api route (pages) /api/recommendations", "duration_ms": 3.287, "status_message": "", "exception": {"exception.message": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T02:43:16.376Z)", "exception.stacktrace": "Error: 14 UNAVAILABLE: No connection established. Las |
| 7 | get_container_health | Verify recommendation is actually stopped now, check restart/oom and limits to corroborate container_down versus a transient dependency/network issue causing frontend UNAVAILABLE errors. | [{"name": "recommendation", "Status": "exited", "RestartCount": 0, "OOMKilled": false, "StartedAt": "2026-10-24T02:34:21.13518642Z", "Created": "2026-10-24T02:34:20.783273993Z", "NanoCpus": 0, "Memory": 52428800, "health": null, "cpu_percent": 0.0, "memory_mb": 0.0}] |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:recommendation:Status=exited | docker | {"name": "recommendation", "field": "Status", "value": "exited"} | python -m tools.resolve 'container:recommendation:Status=exited' --run-dir 'runs/20261024T024152.039733Z-dc7d26df' |
| dlog:frontend:32126efb0b28920bfb2368c16057f62780b3299cd51c3209ed2f405e289bebd2 | docker | {"timestamp": "2026-10-24T02:34:21.735658232Z", "severity": "ERROR", "body": "Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T02:34:11.551Z)", "trace_id": null, "evidence_id": "dlog:frontend:32126efb0b28920bfb2368c16057f62780b3299cd51c3209ed2f405e289bebd2", "original_line": "2026-10-24T02:34:21.735658232Z Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T02:34:11.551Z)"} | python -m tools.resolve 'dlog:frontend:32126efb0b28920bfb2368c16057f62780b3299cd51c3209ed2f405e289bebd2' --run-dir 'runs/20261024T024152.039733Z-dc7d26df' |
| dlog:frontend:3e6006802b76bf49b1123fe2c6a2efc408a10de2b70abe7832701572ffe94aea | docker | {"timestamp": "2026-10-24T02:34:21.736329064Z", "severity": "ERROR", "body": "  details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T02:34:11.551Z)',", "trace_id": null, "evidence_id": "dlog:frontend:3e6006802b76bf49b1123fe2c6a2efc408a10de2b70abe7832701572ffe94aea", "original_line": "2026-10-24T02:34:21.736329064Z   details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T02:34:11.551Z)',"} | python -m tools.resolve 'dlog:frontend:3e6006802b76bf49b1123fe2c6a2efc408a10de2b70abe7832701572ffe94aea' --run-dir 'runs/20261024T024152.039733Z-dc7d26df' |
| log:otel/fgbJa6EBzXeOHxa7KZWV | opensearch | {"attributes": {"code.filepath": "/usr/src/app/recommendation_server.py", "code.function": "ListRecommendations", "code.lineno": 47, "data_stream": {"dataset": "default", "namespace": "namespace", "type": "record"}, "otelServiceName": "recommendation", "otelSpanID": "3d92f3600de966be", "otelTraceID": "8852095d37b2d433e138873d7d604979", "otelTraceSampled": true}, "body": "Receive ListRecommendations for product ids:['LS4PSXUNUM', '66VCHSJNUP', 'L9ECAV7KIM', '9SIQT8TOJO', '1YMWWN1N4O']", "instrumentationScope": {"name": "main"}, "observedTimestamp": "2026-10-24T02:41:47.92411681Z", "resource": {"service.name": "recommendation", "service.namespace": "opentelemetry-demo", "service.version": "2.0.2", "telemetry.sdk.language": "python", "telemetry.sdk.name": "opentelemetry", "telemetry.sdk.version": "1.30.0"}, "severity": {"text": "INFO", "number": 9}, "spanId": "3d92f3600de966be", "@timestamp | python -m tools.resolve 'log:otel/fgbJa6EBzXeOHxa7KZWV' --run-dir 'runs/20261024T024152.039733Z-dc7d26df' |
| metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792809697.071=860.0000000000032 | prometheus | {"metric": {"service_name": "frontend"}, "timestamp": 1792809697.071, "value": 860.0000000000032, "query": "named:p95_latency_by_service"} | python -m tools.resolve 'metric:query{__query__="named:p95_latency_by_service",service_name="frontend"}@1792809697.071=860.0000000000032' --run-dir 'runs/20261024T024152.039733Z-dc7d26df' |
| metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792809697.071=874.9999999999933 | prometheus | {"metric": {"service_name": "frontend-proxy"}, "timestamp": 1792809697.071, "value": 874.9999999999933, "query": "named:p95_latency_by_service"} | python -m tools.resolve 'metric:query{__query__="named:p95_latency_by_service",service_name="frontend-proxy"}@1792809697.071=874.9999999999933' --run-dir 'runs/20261024T024152.039733Z-dc7d26df' |
| span:c6fcdf7dceb5b4d2c9edcf92172ba3aa/faed1a9a8ebf2559 | jaeger | {"traceID": "c6fcdf7dceb5b4d2c9edcf92172ba3aa", "spanID": "faed1a9a8ebf2559", "operationName": "grpc.oteldemo.RecommendationService/ListRecommendations", "references": [{"refType": "CHILD_OF", "traceID": "c6fcdf7dceb5b4d2c9edcf92172ba3aa", "spanID": "6f2997b0d8b43f72"}], "startTime": 1792809804506000, "duration": 1005, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T02:43:16.376Z)"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "net.peer.name", "type": "string", "value": "recommendation"}, {"key": "net.peer.port", "type": "int64", "value": 9001}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "valu | python -m tools.resolve 'span:c6fcdf7dceb5b4d2c9edcf92172ba3aa/faed1a9a8ebf2559' --run-dir 'runs/20261024T024152.039733Z-dc7d26df' |
| trace:4aeaaef617689b4bea701e0f9ed7a61a | jaeger | {"traceID": "4aeaaef617689b4bea701e0f9ed7a61a", "warnings": null, "spans": [{"traceID": "4aeaaef617689b4bea701e0f9ed7a61a", "spanID": "0d3156f08207d76a", "operationName": "Currency/Convert", "references": [{"refType": "CHILD_OF", "traceID": "4aeaaef617689b4bea701e0f9ed7a61a", "spanID": "914c09c2c3514630"}], "startTime": 1792809717846726, "duration": 758, "tags": [{"key": "app.currency.conversion.from", "type": "string", "value": "USD"}, {"key": "app.currency.conversion.to", "type": "string", "value": "USD"}, {"key": "otel.scope.name", "type": "string", "value": "currency"}, {"key": "otel.status_code", "type": "string", "value": "OK"}, {"key": "rpc.grpc.status_code", "type": "int64", "value": 0}, {"key": "rpc.method", "type": "string", "value": "Convert"}, {"key": "rpc.service", "type": "string", "value": "oteldemo.CurrencyService"}, {"key": "rpc.system", "type": "string", "value": "grpc" | python -m tools.resolve 'trace:4aeaaef617689b4bea701e0f9ed7a61a' --run-dir 'runs/20261024T024152.039733Z-dc7d26df' |
| trace:c6fcdf7dceb5b4d2c9edcf92172ba3aa | jaeger | {"traceID": "c6fcdf7dceb5b4d2c9edcf92172ba3aa", "warnings": null, "spans": [{"traceID": "c6fcdf7dceb5b4d2c9edcf92172ba3aa", "spanID": "faed1a9a8ebf2559", "operationName": "grpc.oteldemo.RecommendationService/ListRecommendations", "references": [{"refType": "CHILD_OF", "traceID": "c6fcdf7dceb5b4d2c9edcf92172ba3aa", "spanID": "6f2997b0d8b43f72"}], "startTime": 1792809804506000, "duration": 1005, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T02:43:16.376Z)"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "net.peer.name", "type": "string", "value": "recommendation"}, {"key": "net.peer.port", "type": "int64", "value": 9001}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/i | python -m tools.resolve 'trace:c6fcdf7dceb5b4d2c9edcf92172ba3aa' --run-dir 'runs/20261024T024152.039733Z-dc7d26df' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261024T024152.039733Z-dc7d26df'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

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
| Confidence | 90% |
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

- dependency_unavailable without container stop
- network issue between frontend and a healthy recommendation

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 7 tool calls; 172.79 s; stopped because confident.
