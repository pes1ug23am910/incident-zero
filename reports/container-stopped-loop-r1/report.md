# Incident: container-stopped-loop-r1

**fixed** · recommendation · confidence 90%

Container is stopped; frontend calls to grpc.oteldemo.RecommendationService/ListRecommendations fail with DNS EAI_AGAIN and gRPC UNAVAILABLE/EHOSTUNREACH when connecting to recommendation.

Run: `runs/20261023T160004.705486Z-ad2f6cb4` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-23T16:00:03.792958+00:00 |
| Diagnosed | 2026-10-23T16:06:38.858723+00:00 |
| Approval requested | 2026-10-23T16:06:51.851424+00:00 |
| Approved | 2026-10-23T16:06:51.851424+00:00 |
| Action started | 2026-10-23T16:06:55.709761+00:00 |
| Action finished | 2026-10-23T16:06:56.254231+00:00 |
| Verified | 2026-10-23T16:10:00.490344+00:00 |
| Resolved | 2026-10-23T16:10:00.511558+00:00 |

## Symptoms

| Service | Signal | Observed | Evidence |
| --- | --- | --- | --- |
| recommendation | container_status | exited | container:recommendation:Status=exited |
| frontend | investigation_context | Failure observed in evidence collected after the initial health overview. | trace:cb9a79ce9211ccbde2b97c60260316eb, span:cb9a79ce9211ccbde2b97c60260316eb/855cc0f051627032 |
| frontend-proxy | investigation_context | Failure observed in evidence collected after the initial health overview. | trace:cb9a79ce9211ccbde2b97c60260316eb, trace:f05113e3077e2bd0ca26cff93c4e7822 |
| load-generator | investigation_context | Failure observed in evidence collected after the initial health overview. | trace:cb9a79ce9211ccbde2b97c60260316eb, trace:f05113e3077e2bd0ca26cff93c4e7822 |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| recommendation | Container is stopped; frontend calls to grpc.oteldemo.RecommendationService/ListRecommendations fail with DNS EAI_AGAIN and gRPC UNAVAILABLE/EHOSTUNREACH when connecting to recommendation. | 90% | 90% | 90% | frontend, frontend-proxy, load-generator, recommendation | container:recommendation:Status=exited, span:cb9a79ce9211ccbde2b97c60260316eb/855cc0f051627032, span:f05113e3077e2bd0ca26cff93c4e7822/4c1139be7780ce3f |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 4 symptom entries. |
| 2 | get_traces | Recommendation container is exited; check if frontend requests show failed calls to recommendation and capture the failing operation and error text to corroborate impact on callers. | [{"trace_id": "cb9a79ce9211ccbde2b97c60260316eb", "duration_ms": 14999.871, "started_at": "2026-10-23T16:00:01.625418+00:00", "ended_at": "2026-10-23T16:00:16.625289+00:00", "root_span": {"span_id": "658a377c8b85bc70", "service": "load-generator", "operation": "GET", "duration_ms": 14999.327, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "86f8d163ad3b61bd", "service": "frontend-proxy", "operation": "router frontend egress", "duration_ms": 14996.04, "status_message": "", "exception": {}}, "origin_error_spans": [{"span_id": "86f8d163ad3b61bd", "service": "frontend-proxy", "operation": "router frontend egress", "duration_ms": 14996.04, "status_message": "", "exception": {}}, {"span_id": "855cc0f051627032", "service": "frontend", "operation": "dns.lookup", "duration_ms": 5008.64, "status_message": "getaddrinfo EAI_AGAIN recommendation", "exception": {}}], "error_spans": [{"span_id": "86f8d163ad3b61bd", "service": "frontend-proxy", "operation": "router frontend egress", "duration_ms": 14996.04, "status_message": "", "exception": {}}, {"span_id": "de85f41183a285da", "service": "frontend-proxy", "operation": "ingress", "duration_ms": 14997.339, "status_message": "", "exception": {}}, {"span_id": "658a377c8b85bc70", "service": "load-generator", "operation": "GET", "duration_ms": 14999.327, "status_message": "", "exception": {}}, {"span_id": "855cc0f051627032", "service": "frontend", "operation": "dns.lookup", "duration_ms": 5008.64, "status_message": "getadd |
| 3 | get_logs | Corroborate that recommendation is down by checking frontend WARN/ERROR logs for connection/name-resolution failures when calling recommendation, strengthening container_down vs a frontend-local error. | [] |
| 4 | get_logs | Broaden to INFO logs on the caller to corroborate that frontend requests are failing due to recommendation being unavailable, strengthening the container_down diagnosis with independent log evidence of DNS/connection errors. | [] |
| 5 | get_container_health | Confirm recommendation is actually stopped now and not flapping or OOMing; this validates container_down versus application_flag/resource_starvation and corroborates the frontend trace failures. | [{"name": "recommendation", "Status": "exited", "RestartCount": 0, "OOMKilled": false, "StartedAt": "2026-10-23T12:05:36.283275407Z", "Created": "2026-10-23T12:05:35.920657266Z", "NanoCpus": 0, "Memory": 52428800, "health": null, "cpu_percent": 0.0, "memory_mb": 0.0}] |
| 6 | get_logs | Explain why recommendation exited by inspecting its own recent logs; this corroborates container_down with service-local evidence and adds details of the failing operation, while strengthening confidence beyond caller traces and container state. | [{"timestamp": "2026-10-23T15:59:58.599072Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['L9ECAV7KIM', '2ZYFJ3GM2N', 'LS4PSXUNUM', 'OLJCESPC7Z', '9SIQT8TOJO']", "logger_scope": "main", "trace_id": "16de1620d558dbe2f849dac526c5612a", "evidence_id": "log:otel/g1t9aaEBUZiyFLbylC54"}, {"timestamp": "2026-10-23T15:59:56.370376704Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['2ZYFJ3GM2N', '1YMWWN1N4O', 'L9ECAV7KIM', '66VCHSJNUP', '0PUK6V6EV0']", "logger_scope": "main", "trace_id": "bf18a92e5eb1fe01b175f7dbe99ee127", "evidence_id": "log:otel/glt9aaEBUZiyFLbylC54"}, {"timestamp": "2026-10-23T15:59:51.880523776Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['2ZYFJ3GM2N', '0PUK6V6EV0', 'OLJCESPC7Z', '6E92ZMYYFZ', 'L9ECAV7KIM']", "logger_scope": "main", "trace_id": "39ff10197453c9ded55e9c7e2ae1aab3", "evidence_id": "log:otel/SFt9aaEBUZiyFLbygC7L"}, {"timestamp": "2026-10-23T15:59:51.837865984Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['66VCHSJNUP', '9SIQT8TOJO', '0PUK6V6EV0', 'L9ECAV7KIM', 'HQTGWGPNH4']", "logger_scope": "main", "trace_id": "4d3f7e0f073f0ed60781433bea8d96c3", "evidence_id": "log:otel/R1t9aaEBUZiyFLbygC7L"}, {"timestamp": "2026-10-23T15:59:41.126809344Z", "severity": "INFO", "body": "Receive ListRecommendations for product ids:['L9ECAV7KIM', '66VCHSJNUP', 'HQTGWGPNH4', '6E92ZMYYFZ', '9SIQT8TOJO']", "logger_scope": "main", "trace_id": "7d9e6970a22 |
| 7 | get_deploy_history | Recommendation is exited and causing caller DNS errors; inspect recent lifecycle events to explain why recommendation stopped and corroborate container_down for the recommendation service itself. | [{"timestamp": "2026-10-23T15:48:46.563709+00:00", "kind": "action", "record": {"ts": "2026-10-23T15:48:46.563709+00:00", "event": "approval_rejected", "report_id": "runs/20261023T154711.305759Z-b5f7c99e", "actor": "Yash Verma"}, "evidence_id": "action_log:29"}, {"timestamp": "2026-10-23T15:48:41.654460+00:00", "kind": "action", "record": {"ts": "2026-10-23T15:48:41.654460+00:00", "event": "dry_run", "report_id": "runs/20261023T154711.305759Z-b5f7c99e", "action": "toggle_flag", "target": "payment", "parameters": {"service": "payment"}, "result": "preview_only"}, "evidence_id": "action_log:28"}, {"timestamp": "2026-10-23T15:39:32.850124+00:00", "kind": "action", "record": {"ts": "2026-10-23T15:39:32.850124+00:00", "event": "verification", "report_id": "runs/20261023T153512.976354Z-13778fd2", "result": {"checked_at": "2026-10-23T15:39:32.841121+00:00", "signal": "error_rate", "before": 0.1978021978021978, "after": 0.0, "recovered": true, "rolled_back": false, "outcome": "recovered", "requests_observed": 984.0492024601231, "samples": [{"available": true, "values": [0.22471910112359553, 0.07194244604316546, 0.06338028169014084, 0.5], "requests_observed": 1094.0911742645221, "load_running": true, "evidence_ids": ["metric:query{__query__=\"named:error_rate_by_service\",service_name=\"ad\"}@1792769790.489=0.0", "metric:query{__query__=\"named:error_rate_by_service\",service_name=\"cart\"}@1792769790.489=0.0", "metric:query{__query__=\"named:error_rate_by_service\",service_name=\"che |
| 8 | get_traces | Widen the search window to confirm repeated frontend failures when calling recommendation, strengthening the container_down diagnosis for recommendation with multiple error traces. | [{"trace_id": "f05113e3077e2bd0ca26cff93c4e7822", "duration_ms": 7.022, "started_at": "2026-10-23T16:04:55.527025+00:00", "ended_at": "2026-10-23T16:04:55.534047+00:00", "root_span": {"span_id": "068726b548b4cce4", "service": "load-generator", "operation": "GET", "duration_ms": 7.022, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "4c1139be7780ce3f", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 0.608, "status_message": "14", "exception": {}}, "origin_error_spans": [{"span_id": "4c1139be7780ce3f", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 0.608, "status_message": "14", "exception": {}}, {"span_id": "829350229d2eef5f", "service": "frontend", "operation": "GET", "duration_ms": 3.94, "status_message": "", "exception": {}}], "error_spans": [{"span_id": "4c1139be7780ce3f", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 0.608, "status_message": "14", "exception": {}}, {"span_id": "b76e49052475963c", "service": "frontend", "operation": "executing api route (pages) /api/recommendations", "duration_ms": 2.289, "status_message": "", "exception": {"exception.message": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T16:04:03.970Z)", "exception.stacktrace": "Error: 14 UNAVAILABLE: No connection established. Last err |
| 9 | get_traces | Recommendation container is exited; inspect its own recent error traces to see if it emitted a failing operation or exception before stopping, clarifying container_down vs application_flag and explaining the recommendation symptom itself. | [] |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| action_log:29 | action_log | {"ts": "2026-10-23T15:48:46.563709+00:00", "event": "approval_rejected", "report_id": "runs/20261023T154711.305759Z-b5f7c99e", "actor": "Yash Verma"} | python -m tools.resolve 'action_log:29' --run-dir 'runs/20261023T160004.705486Z-ad2f6cb4' |
| container:recommendation:Status=exited | docker | {"name": "recommendation", "field": "Status", "value": "exited"} | python -m tools.resolve 'container:recommendation:Status=exited' --run-dir 'runs/20261023T160004.705486Z-ad2f6cb4' |
| log:otel/g1t9aaEBUZiyFLbylC54 | opensearch | {"attributes": {"code.filepath": "/usr/src/app/recommendation_server.py", "code.function": "ListRecommendations", "code.lineno": 47, "data_stream": {"dataset": "default", "namespace": "namespace", "type": "record"}, "otelServiceName": "recommendation", "otelSpanID": "2c71f8b46ced9cea", "otelTraceID": "16de1620d558dbe2f849dac526c5612a", "otelTraceSampled": true}, "body": "Receive ListRecommendations for product ids:['L9ECAV7KIM', '2ZYFJ3GM2N', 'LS4PSXUNUM', 'OLJCESPC7Z', '9SIQT8TOJO']", "instrumentationScope": {"name": "main"}, "observedTimestamp": "2026-10-23T16:00:00.118675976Z", "resource": {"service.name": "recommendation", "service.namespace": "opentelemetry-demo", "service.version": "2.0.2", "telemetry.sdk.language": "python", "telemetry.sdk.name": "opentelemetry", "telemetry.sdk.version": "1.30.0"}, "severity": {"text": "INFO", "number": 9}, "spanId": "2c71f8b46ced9cea", "@timestam | python -m tools.resolve 'log:otel/g1t9aaEBUZiyFLbylC54' --run-dir 'runs/20261023T160004.705486Z-ad2f6cb4' |
| span:cb9a79ce9211ccbde2b97c60260316eb/855cc0f051627032 | jaeger | {"traceID": "cb9a79ce9211ccbde2b97c60260316eb", "spanID": "855cc0f051627032", "operationName": "dns.lookup", "references": [], "startTime": 1792771201630000, "duration": 5008640, "tags": [{"key": "dns.error_message", "type": "string", "value": "getaddrinfo EAI_AGAIN recommendation"}, {"key": "dns.error_name", "type": "string", "value": "Error"}, {"key": "error", "type": "bool", "value": true}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-dns"}, {"key": "otel.scope.version", "type": "string", "value": "0.43.1"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "otel.status_description", "type": "string", "value": "getaddrinfo EAI_AGAIN recommendation"}, {"key": "span.kind", "type": "string", "value": "client"}], "logs": [], "processID": "p2", "warnings": ["invalid parent span IDs=f22c1c6a307b91a8; skipping clock skew adjustm | python -m tools.resolve 'span:cb9a79ce9211ccbde2b97c60260316eb/855cc0f051627032' --run-dir 'runs/20261023T160004.705486Z-ad2f6cb4' |
| span:f05113e3077e2bd0ca26cff93c4e7822/4c1139be7780ce3f | jaeger | {"traceID": "f05113e3077e2bd0ca26cff93c4e7822", "spanID": "4c1139be7780ce3f", "operationName": "grpc.oteldemo.RecommendationService/ListRecommendations", "references": [{"refType": "CHILD_OF", "traceID": "f05113e3077e2bd0ca26cff93c4e7822", "spanID": "b76e49052475963c"}], "startTime": 1792771495530000, "duration": 608, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-23T16:04:03.970Z)"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "net.peer.name", "type": "string", "value": "recommendation"}, {"key": "net.peer.port", "type": "int64", "value": 9001}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value | python -m tools.resolve 'span:f05113e3077e2bd0ca26cff93c4e7822/4c1139be7780ce3f' --run-dir 'runs/20261023T160004.705486Z-ad2f6cb4' |
| trace:cb9a79ce9211ccbde2b97c60260316eb | jaeger | {"traceID": "cb9a79ce9211ccbde2b97c60260316eb", "warnings": null, "spans": [{"traceID": "cb9a79ce9211ccbde2b97c60260316eb", "spanID": "de85f41183a285da", "operationName": "ingress", "references": [{"refType": "CHILD_OF", "traceID": "cb9a79ce9211ccbde2b97c60260316eb", "spanID": "658a377c8b85bc70"}], "startTime": 1792771201626149, "duration": 14997339, "tags": [{"key": "component", "type": "string", "value": "proxy"}, {"key": "downstream_cluster", "type": "string", "value": "-"}, {"key": "error", "type": "string", "value": "true"}, {"key": "error", "type": "bool", "value": true}, {"key": "guid:x-request-id", "type": "string", "value": "4bb26799-1e3e-97a7-993d-da639d719f03"}, {"key": "http.method", "type": "string", "value": "GET"}, {"key": "http.protocol", "type": "string", "value": "HTTP/1.1"}, {"key": "http.status_code", "type": "string", "value": "504"}, {"key": "http.url", "type": "str | python -m tools.resolve 'trace:cb9a79ce9211ccbde2b97c60260316eb' --run-dir 'runs/20261023T160004.705486Z-ad2f6cb4' |
| trace:f05113e3077e2bd0ca26cff93c4e7822 | jaeger | {"traceID": "f05113e3077e2bd0ca26cff93c4e7822", "warnings": null, "spans": [{"traceID": "f05113e3077e2bd0ca26cff93c4e7822", "spanID": "068726b548b4cce4", "operationName": "GET", "references": [], "startTime": 1792771495527025, "duration": 7022, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "http.method", "type": "string", "value": "GET"}, {"key": "http.status_code", "type": "int64", "value": 500}, {"key": "http.url", "type": "string", "value": "http://frontend-proxy:8080/api/recommendations?productIds=6E92ZMYYFZ"}, {"key": "otel.scope.name", "type": "string", "value": "opentelemetry.instrumentation.requests"}, {"key": "otel.scope.version", "type": "string", "value": "0.51b0"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "span.kind", "type": "string", "value": "client"}], "logs": [], "processID": "p1", "warnings": null}, {"traceID": "f05113 | python -m tools.resolve 'trace:f05113e3077e2bd0ca26cff93c4e7822' --run-dir 'runs/20261023T160004.705486Z-ad2f6cb4' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261023T160004.705486Z-ad2f6cb4'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

## Impact

| Field | Assessment |
| --- | --- |
| Approval tier | T2 |
| Score | 55.0/100 |
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
| Observability gap | 0.4 |

## Proposed action

**1. restart_service** → recommendation

Reason: Restore the diagnosed unavailable component recommendation.

Risk: Restart may interrupt in-flight work; review state and evidence before approval.

Parameters: `{"service": "recommendation"}`

Dry run performed: yes. Start a fresh recommendation process and restore its availability to callers.


## Approval record

Approved in TEST mode by the test harness (not a human)

| Field | Value |
| --- | --- |
| Required | yes |
| Approved | yes |
| Recorded actor | test harness |
| Surface | test |
| Mode | test |
| Requested at | 2026-10-23T16:06:51.851424+00:00 |
| Approved at | 2026-10-23T16:06:51.851424+00:00 |
| Token id | sha256:e2ac4e8f6223ea9ac8768148b9d0b2cb29065622dbd7ebad0d0dbbbe8da1ea73 |
| Token | present (redacted) |
| Executed | yes |
| Action log | action_log:34 |

## Verification

| Signal | Before | After | Recovered | Rolled back |
| --- | --- | --- | --- | --- |
| container_health | 1 | 0 | yes | no |

Outcome: recovered; requests observed: 1220.081338755917.

## Action history

| Index | Decision | Executed | Outcome | Blocked |
| --- | --- | --- | --- | --- |
| 0 | approve | yes | recovered |  |

## Alternatives and escalation

- application_flag
- restart_loop
- network

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.
- Recovery verifies observed signals and request counts; interrupted requests cannot be restored.
- Historical approval provenance was corrected from the retained action log; the original audit entries and evidence snapshots are unchanged. Prompt-shown time was not recorded, so requested_at retains its original value.

## Investigation budget

Model: openai/gpt-5; 9 tool calls; 394.16 s; stopped because confident.
