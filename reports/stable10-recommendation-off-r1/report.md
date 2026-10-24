# Incident: stable10-recommendation-off-r1

**diagnosed** · recommendation · confidence 90%

Container is stopped/exited; frontend calls to RecommendationService/ListRecommendations fail to connect (UNAVAILABLE/EHOSTUNREACH).

Run: `runs/20261024T031911.242799Z-f052efa4` · schema 1.0

## Timeline

| Event | Timestamp |
| --- | --- |
| Detected | 2026-10-24T03:19:06.423997+00:00 |
| Diagnosed | 2026-10-24T03:20:10.919841+00:00 |
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
| frontend | investigation_context | Failure observed in evidence collected after the initial health overview. | dlog:frontend:e1b76f202e2be47b46d41c7d3087634ba4f6f1a086c737effb3e4a7e487a778d, dlog:frontend:7691d916eaf241c697ec0b65cccf1149fa4a136f090dd793a6490bd3c79f4951 |
| frontend-proxy | investigation_context | Failure observed in evidence collected after the initial health overview. | trace:16b3dee4badcb59ae951cb368b900c0a, span:16b3dee4badcb59ae951cb368b900c0a/82a49412522b60fd |

## Root causes

| Component | Cause | Model confidence | Evidence confidence | Final confidence | Explained symptoms | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| recommendation | Container is stopped/exited; frontend calls to RecommendationService/ListRecommendations fail to connect (UNAVAILABLE/EHOSTUNREACH). | 90% | 90% | 90% | frontend, frontend-proxy, recommendation | container:recommendation:Status=exited, dlog:frontend:a322d1a5211a86d83417b3ecf03ea6994c3cd7c7a8b8eddc76570214af29c0e2, span:4938cd70f0cc16bfca62ab7a145f766b/bd51d3b71b227b37 |

## Investigation

| Step | Tool | Why | Finding |
| --- | --- | --- | --- |
| 1 | health_table | Locate every service anomaly before selecting a focused read. | Observed 20 service rows; 3 symptom entries. |
| 2 | get_logs | Recommendation container is exited; check if frontend logs show connection errors to recommendation to corroborate dependency outage impact. | [{"timestamp": "2026-10-24T03:19:19.182593057Z", "severity": "ERROR", "body": "  details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)',", "trace_id": null, "evidence_id": "dlog:frontend:e1b76f202e2be47b46d41c7d3087634ba4f6f1a086c737effb3e4a7e487a778d"}, {"timestamp": "2026-10-24T03:19:19.182566344Z", "severity": "ERROR", "body": " ⨯ Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)", "trace_id": null, "evidence_id": "dlog:frontend:7691d916eaf241c697ec0b65cccf1149fa4a136f090dd793a6490bd3c79f4951"}, {"timestamp": "2026-10-24T03:19:19.181983518Z", "severity": "ERROR", "body": "  details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)',", "trace_id": null, "evidence_id": "dlog:frontend:abbd2b3a8808b7f78031ef4a2e6c25be428a27e7261bd4ffebbbe634a8d36b65"}, {"timestamp": "2026-10-24T03:19:19.181963831Z", "severity": "ERROR", "body": "Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)", "trace_id": null, "evidence_id": "dlog:frontend:a322d1a5211a86d83417b3ecf03ea6994c3cd7c7a8b8eddc76570214af29c0e2"}, {"timestamp": "2026-10-24T03:19:19.181315618Z", "severity": "ERROR", "body": "  details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)',", "trace_id": null, "evide |
| 3 | get_traces | Confirm frontend error traces show failed calls to recommendation, corroborating that the exited recommendation container causes connection errors. | [{"trace_id": "16b3dee4badcb59ae951cb368b900c0a", "duration_ms": 17115.396, "started_at": "2026-10-24T03:19:29.044978+00:00", "ended_at": "2026-10-24T03:19:46.160374+00:00", "root_span": {"span_id": "ef5471a471ca3de3", "service": "frontend-proxy", "operation": "ingress", "duration_ms": 5.89, "status_message": "", "exception": {}}, "first_error_span": {"span_id": "4b5935157f153ec5", "service": "frontend", "operation": "dns.lookup", "duration_ms": 5005.374, "status_message": "getaddrinfo EAI_AGAIN recommendation", "exception": {}}, "origin_error_spans": [{"span_id": "4b5935157f153ec5", "service": "frontend", "operation": "dns.lookup", "duration_ms": 5005.374, "status_message": "getaddrinfo EAI_AGAIN recommendation", "exception": {}}, {"span_id": "82a49412522b60fd", "service": "frontend", "operation": "GET", "duration_ms": 5.461, "status_message": "", "exception": {}}], "error_spans": [{"span_id": "4b5935157f153ec5", "service": "frontend", "operation": "dns.lookup", "duration_ms": 5005.374, "status_message": "getaddrinfo EAI_AGAIN recommendation", "exception": {}}, {"span_id": "9f80314bc99f3f49", "service": "frontend", "operation": "grpc.oteldemo.RecommendationService/ListRecommendations", "duration_ms": 0.763, "status_message": "14", "exception": {}}, {"span_id": "c8fc25e7f2b98f52", "service": "frontend", "operation": "executing api route (pages) /api/recommendations", "duration_ms": 3.53, "status_message": "", "exception": {"exception.message": "14 UNAVAILABLE: No connection e |

## Evidence

| ID | Source | Summary | Reproduce |
| --- | --- | --- | --- |
| container:recommendation:Status=exited | docker | {"name": "recommendation", "field": "Status", "value": "exited"} | python -m tools.resolve 'container:recommendation:Status=exited' --run-dir 'runs/20261024T031911.242799Z-f052efa4' |
| dlog:frontend:7691d916eaf241c697ec0b65cccf1149fa4a136f090dd793a6490bd3c79f4951 | docker | {"timestamp": "2026-10-24T03:19:19.182566344Z", "severity": "ERROR", "body": " ⨯ Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)", "trace_id": null, "evidence_id": "dlog:frontend:7691d916eaf241c697ec0b65cccf1149fa4a136f090dd793a6490bd3c79f4951", "original_line": "2026-10-24T03:19:19.182566344Z  ⨯ Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)"} | python -m tools.resolve 'dlog:frontend:7691d916eaf241c697ec0b65cccf1149fa4a136f090dd793a6490bd3c79f4951' --run-dir 'runs/20261024T031911.242799Z-f052efa4' |
| dlog:frontend:a322d1a5211a86d83417b3ecf03ea6994c3cd7c7a8b8eddc76570214af29c0e2 | docker | {"timestamp": "2026-10-24T03:19:19.181963831Z", "severity": "ERROR", "body": "Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)", "trace_id": null, "evidence_id": "dlog:frontend:a322d1a5211a86d83417b3ecf03ea6994c3cd7c7a8b8eddc76570214af29c0e2", "original_line": "2026-10-24T03:19:19.181963831Z Error: 14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)"} | python -m tools.resolve 'dlog:frontend:a322d1a5211a86d83417b3ecf03ea6994c3cd7c7a8b8eddc76570214af29c0e2' --run-dir 'runs/20261024T031911.242799Z-f052efa4' |
| dlog:frontend:e1b76f202e2be47b46d41c7d3087634ba4f6f1a086c737effb3e4a7e487a778d | docker | {"timestamp": "2026-10-24T03:19:19.182593057Z", "severity": "ERROR", "body": "  details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)',", "trace_id": null, "evidence_id": "dlog:frontend:e1b76f202e2be47b46d41c7d3087634ba4f6f1a086c737effb3e4a7e487a778d", "original_line": "2026-10-24T03:19:19.182593057Z   details: 'No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:19.168Z)',"} | python -m tools.resolve 'dlog:frontend:e1b76f202e2be47b46d41c7d3087634ba4f6f1a086c737effb3e4a7e487a778d' --run-dir 'runs/20261024T031911.242799Z-f052efa4' |
| span:16b3dee4badcb59ae951cb368b900c0a/82a49412522b60fd | jaeger | {"traceID": "16b3dee4badcb59ae951cb368b900c0a", "spanID": "82a49412522b60fd", "operationName": "GET", "references": [{"refType": "CHILD_OF", "traceID": "16b3dee4badcb59ae951cb368b900c0a", "spanID": "322688ebeb0782c5"}], "startTime": 1792811969046000, "duration": 5461, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "http.flavor", "type": "string", "value": "1.1"}, {"key": "http.host", "type": "string", "value": "frontend-proxy:8080"}, {"key": "http.method", "type": "string", "value": "GET"}, {"key": "http.scheme", "type": "string", "value": "http"}, {"key": "http.status_code", "type": "int64", "value": 500}, {"key": "http.status_text", "type": "string", "value": "INTERNAL SERVER ERROR"}, {"key": "http.target", "type": "string", "value": "/api/recommendations?productIds=HQTGWGPNH4"}, {"key": "http.url", "type": "string", "value": "http://frontend-proxy:8080/api/recommend | python -m tools.resolve 'span:16b3dee4badcb59ae951cb368b900c0a/82a49412522b60fd' --run-dir 'runs/20261024T031911.242799Z-f052efa4' |
| span:4938cd70f0cc16bfca62ab7a145f766b/bd51d3b71b227b37 | jaeger | {"traceID": "4938cd70f0cc16bfca62ab7a145f766b", "spanID": "bd51d3b71b227b37", "operationName": "grpc.oteldemo.RecommendationService/ListRecommendations", "references": [{"refType": "CHILD_OF", "traceID": "4938cd70f0cc16bfca62ab7a145f766b", "spanID": "5b4ed7273d9bfd88"}], "startTime": 1792811969795000, "duration": 549, "tags": [{"key": "error", "type": "bool", "value": true}, {"key": "grpc.error_message", "type": "string", "value": "14 UNAVAILABLE: No connection established. Last error: connect EHOSTUNREACH 172.23.0.12:9001 (2026-10-24T03:19:28.383Z)"}, {"key": "grpc.error_name", "type": "string", "value": "Error"}, {"key": "net.peer.name", "type": "string", "value": "recommendation"}, {"key": "net.peer.port", "type": "int64", "value": 9001}, {"key": "otel.scope.name", "type": "string", "value": "@opentelemetry/instrumentation-grpc"}, {"key": "otel.scope.version", "type": "string", "value | python -m tools.resolve 'span:4938cd70f0cc16bfca62ab7a145f766b/bd51d3b71b227b37' --run-dir 'runs/20261024T031911.242799Z-f052efa4' |
| trace:16b3dee4badcb59ae951cb368b900c0a | jaeger | {"traceID": "16b3dee4badcb59ae951cb368b900c0a", "warnings": null, "spans": [{"traceID": "16b3dee4badcb59ae951cb368b900c0a", "spanID": "322688ebeb0782c5", "operationName": "router frontend egress", "references": [{"refType": "CHILD_OF", "traceID": "16b3dee4badcb59ae951cb368b900c0a", "spanID": "ef5471a471ca3de3"}], "startTime": 1792811969045228, "duration": 5599, "tags": [{"key": "component", "type": "string", "value": "proxy"}, {"key": "error", "type": "string", "value": "true"}, {"key": "error", "type": "bool", "value": true}, {"key": "http.protocol", "type": "string", "value": "HTTP/1.1"}, {"key": "http.status_code", "type": "string", "value": "500"}, {"key": "otel.status_code", "type": "string", "value": "ERROR"}, {"key": "peer.address", "type": "string", "value": "172.23.0.14:8080"}, {"key": "response_flags", "type": "string", "value": "-"}, {"key": "span.kind", "type": "string", "val | python -m tools.resolve 'trace:16b3dee4badcb59ae951cb368b900c0a' --run-dir 'runs/20261024T031911.242799Z-f052efa4' |

Resolve an ID with `python -m tools.resolve '<evidence-id>' --run-dir 'runs/20261024T031911.242799Z-f052efa4'`; add `--bundle-dir reports/<incident-id>` to use the retained report bundle after run expiry. The resolver identifies live evidence, run snapshots, or bundle snapshots.

## Impact

| Field | Assessment |
| --- | --- |
| Approval tier | T2 |
| Score | 47.0/100 |
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
| Observability gap | 0.0 |

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

- Transient network issue to recommendation while container remained running
- Frontend disabled recommendation calls
- Temporary DNS resolver issue (EAI_AGAIN) unrelated to container state

—

## Prevention

Monitor component error rate, latency and container lifecycle; alert on sustained resource pressure.

## Limitations

- Actions are proposals only. No approval, execution or recovery was performed.
- Metrics may lag by about 60 seconds; a two-minute rate window retains older observations.
- Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.

## Investigation budget

Model: openai/gpt-5; 3 tool calls; 59.67 s; stopped because confident.
