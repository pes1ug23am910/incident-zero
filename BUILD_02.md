# Build 02 — Read-only telemetry tools

## Follow-up after daemon compatibility fix

On 2026-10-23 the daemon was already running with minimum API 1.24. Live
Prometheus discovery returned 270 names and Jaeger 15 backend services (14 after
diagnostic filtering). The exact names and fields now observed are recorded in
`tools/METRICS.md` and `tools/LOGS.md`; the initial blocker below is historical.

The corrected two-minute metric queries produced finite error rate, p95 and RPS
for all 13 services with traffic. The clean sample had zero error rates and
frontend 5.48379 spans/s, p95 38.25 ms; health took 2.2507 s. Docker health retains
all 21 containers, while excluded telemetry is removed from trace/metric reads.
Jaeger searches and the operator traffic check use explicit microsecond bounds.

The shared redactor filters tool responses and resolution, including span tags,
events and complete disclosing log lines. Docker stdout/stderr supplies the five
services without exported application logs, with `dlog:` evidence. Recorded
backend samples support the redaction regressions. Injection/recovery acceptance
and command timings are recorded separately in `BUILD_01B.md`.

Built and probed on 2026-10-23 against the official minimal 2.0.2 demo.

## Observed blocker

The collector repeatedly stops because its Docker statistics receiver uses API
1.25 while this daemon accepts API 1.40 or newer. Prometheus is reachable but
contains no metric names; Jaeger lists only its own service; OpenSearch is
reachable at the discovered ephemeral host port but the `otel` index does not
exist. Application metrics, traces and logs are **not verified**. The repository
does not change the demo or daemon configuration to bypass this failure.

Discovery happened before implementation. `tools/METRICS.md` and `tools/LOGS.md`
record actual responses and clearly separate provisional names from verified
facts. `tools/fixtures/live_unavailable.json` records the actual empty/error
responses. Positive unit-test documents and spans are synthetic, not claims of
live observations.

## Implemented

Five read-only tools return the agreed envelope; `health_table`, named queries,
CLI, service listing, and evidence resolution are included. Metrics are capped at
20 series and 200 points per series, traces at 50, and logs at 100 with 300-character
bodies. Missing health measurements are null. They never imply zero errors or a
healthy frontend. Runtime metadata discovery selects supported metric names and
log fields only when available. OpenSearch host port discovery runs for each
request, with the specified read-only container fallback if no port is published.

Docker reads are scoped to the demo Compose project. Inspection and resource
sampling run concurrently. The actual official minimal stack contains **21**
containers; the specification's expected count of 22 does not match this tag.

Evidence is re-fetched from its named backend. A changed container value or
missing document fails resolution. Aggregate metric IDs carry their query and
original timestamp, allowing the resolver to verify a historical computation.

## Initial live timings

These probes ran during the other acceptance work and are not a clean baseline.
Times measure the function call, including backend reads.

| Call | Seconds | Observed result |
|---|---:|---|
| `get_metrics('error_rate_by_service')` | 0.0242 | Empty, explicit missing-telemetry warning |
| `get_traces('checkout')` | 0.0164 | No application traces |
| `get_logs('payment')` | 0.1231 | Explicit HTTP 404: missing log index |
| `get_container_health()` | 2.3159 | All 21 containers, state and resource measurements |
| `get_deploy_history()` | 0.3099 | 42 real create/start events |
| `health_table()` | 1.7556 | 21 rows, null metrics, `telemetry_available=false` |
| `list_services()` | 0.0189 | Only the trace backend's own service |

Five live IDs for frontend status, restart count, OOM state, start time and CPU
limit resolved successfully. Individual calls took 0.2074–0.2475 seconds. Raw
local observations are in the ignored `.build/tools-live-initial.json` file.
No initial tool call exceeded three seconds.

An independent fresh-process check also included Python startup: metrics 0.2896s,
traces 0.2492s, logs 0.3425s, container health 2.5280s, deploy history 0.5240s,
health table 1.5596s. All were below three seconds in that run.

## Clean mutation-state baseline

After the initial injection work had been reset, `health_table` was sampled at
2026-10-23 13:56:49 IST. It took **2.4903s**, returned 21 rows, and all containers
were running at that instant. Frontend error rate, p95, and RPS were all null;
`telemetry_available=false` and three missing-measurement warnings were present.
The collector's intermittent running state does not establish telemetry health.
The clean error-rate/RPS acceptance was attempted and is **not verified**.
Raw local observations: `.build/tools-clean-baseline.json`.

## Acceptance status

| Requirement | Result |
|---|---|
| Clean error rates near zero and frontend RPS above zero | Not verified: collector supplies no application telemetry |
| Payment failure visible in metrics, traces, and logs | Not verified: blocked by the same collector failure; injection probes recorded separately below |
| All containers visible | Verified live: 21/21 official minimal containers |
| Stopped cache visible in one call | Pending coordinated injection below |
| Evidence IDs re-fetch real data | Five container fields verified live; other evidence classes exercised with synthetic fixtures |
| Tool latency under three seconds | Verified for initial live calls listed above |
| Unit tests | 21 passed in 0.23s; run below |

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tools.py tests/test_resolve.py --basetemp=.build/pytest-tools -q
.\.venv\Scripts\python.exe -m tools.cli health_table
.\.venv\Scripts\python.exe -m tools.cli get_container_health
.\.venv\Scripts\python.exe -m tools.cli get_metrics error_rate_by_service
.\.venv\Scripts\python.exe -m tools.cli get_traces checkout
.\.venv\Scripts\python.exe -m tools.cli get_logs payment
.\.venv\Scripts\python.exe -m tools.resolve 'container:frontend:Status=running'
```

Only the JSON response is written to stdout. Backend errors return a structured
error envelope and nonzero CLI status. Empty but valid backend queries return
success with no evidence; the health table explicitly marks missing telemetry.
