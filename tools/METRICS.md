# Verified metric discovery

Rechecked against the running, unmodified official minimal 2.0.2 stack on
2026-10-23 at 09:10:37 UTC (14:40:37 IST), after the Docker compatibility fix.
`GET http://localhost:9090/api/v1/label/__name__/values` returned **270 names**.
The discovery and eight sample queries took **0.1539 s** in one process.
Raw observations are in the ignored `.build/metrics-live-discovery.json`.
The earlier empty-telemetry observation in BUILD_02.md describes the previous
collector failure, not the current stack.

| Purpose | Confirmed metric | Confirmed labels |
| --- | --- | --- |
| Span count | `traces_span_metrics_calls_total` | `service_name`, `span_name`, `span_kind`, `status_code`, `job`, `service_namespace` |
| Span duration | `traces_span_metrics_duration_milliseconds_bucket` | Same labels, plus `le` |
| Container CPU percent | `container_cpu_utilization_ratio` | `container_name` |
| CPU time | `container_cpu_usage_nanoseconds_total` | `container_name` |
| Container memory bytes | `container_memory_usage_total_bytes` | `container_name` |
| Memory limit bytes | `container_memory_usage_limit_bytes` | `container_name` |
| Memory percent | `container_memory_percent_ratio` | `container_name` |
| Frontend HTTP probe | `httpcheck_status` | `http_method`, `http_status_class`, `http_status_code`, `http_url` |

The name inventory also contained duration `_sum` and `_count`, CPU
`_kernelmode_nanoseconds_total` and `_usermode_nanoseconds_total`, network
`container_network_io_usage_rx_bytes_total`, `container_network_io_usage_tx_bytes_total`,
`container_network_io_usage_rx_dropped_total`, `container_network_io_usage_tx_dropped_total`,
`httpcheck_duration_milliseconds`, and `httpcheck_error`. These names were seen;
no units or behavior beyond the sample queries above were measured here.

The checkout samples had `span_kind="SPAN_KIND_CLIENT"`,
`status_code="STATUS_CODE_UNSET"`, and operations including
`oteldemo.CurrencyService/Convert` and `oteldemo.PaymentService/Charge`.
An independent series inventory also returned `SPAN_KIND_SERVER` and
`SPAN_KIND_INTERNAL`. Error-labelled queries returned real
`STATUS_CODE_ERROR` series with zero rates on the clean stack.
The HTTP probe sample was `GET`, status `200`, class `2xx`, value `1`, for
`http://frontend-proxy:8080`.

## Named queries and interpretation

`queries.py` prefers these confirmed names and still discovers supported older
alternatives at runtime. Span counters and histograms use **`[2m]`** because
the connector updates about once per minute. A one-minute window often contains
too few samples for `rate`. When the error series is absent, the numerator is
zero only for services with a matching total-call series. A missing denominator
or non-finite result stays null; missing telemetry never proves health.

The named queries are `error_rate_by_service`, `p95_latency_by_service`,
`rps_by_service`, `container_cpu`, `container_memory`, and `frontend_http_check`.
The three service queries aggregate all span kinds. Consequently `rps` is the
rate of recorded spans, including internal and client work; it is not a count
of distinct customer requests. This also gives client-only services such as
the load generator a measurement. P95 is in milliseconds.

Container state comes from Docker inspection. Prometheus container series can
retain their last values for minutes after a container stops and are not used
to decide whether it is running.

At the clean follow-up probe, `health_table` took **2.2507 s**. All **13 services
with a positive span rate** had non-null error rate, p95 and RPS; all reported
zero error rate. Frontend had **5.48379 spans/s** and **38.25 ms p95**.
Infrastructure without span traffic retained null service measurements.
The memory query took 0.0370 s, a two-trace checkout query 0.0474 s, and service
listing 0.0067 s. Raw envelopes are in
`.build/metrics-traces-live-baseline.json`.

## Evidence and trace reads

Range queries return at most 20 series and 200 points per series. The step grows
to cover the requested window within that limit. Each finite series carries
its peak-point evidence ID and its latest-point evidence ID. The health table
includes the **latest** ID, so a recovered current value is never supported
only by an earlier peak. If the last point is null, it is not replaced by an
older finite point.

Aggregations use `metric:query{...}` IDs, with the complete PromQL stored in a
JSON-escaped `__query__` pseudo-label. The resolver replays that query at the
original timestamp and checks its labels and value. Raw series retain their
metric name. Diagnostic responses and evidence pass through the telemetry
redactor before use.

Jaeger is reachable at `http://localhost:8080/jaeger/ui/api`. Trace searches send
explicit **microsecond `start` and `end`** values; they do not rely on the ignored
`lookback` parameter. The live service listing returned 15 backend services,
14 after the required telemetry exclusion. Trace summaries redact tags and
events before examining errors.

```powershell
.\.venv\Scripts\python.exe -m tools.cli get_metrics error_rate_by_service
.\.venv\Scripts\python.exe -m tools.cli get_metrics p95_latency_by_service
.\.venv\Scripts\python.exe -m tools.cli get_metrics container_memory
.\.venv\Scripts\python.exe -m tools.cli health_table
```
