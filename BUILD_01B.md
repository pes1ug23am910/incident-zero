# Build 01B — Live follow-up acceptance, 2026-10-23

The daemon compatibility blocker was fixed before this session. Read-only
`docker version --format '{{json .Server}}'` reported Engine 29.8.1, API 1.56,
minimum API **1.24**. The official minimal 2.0.2 checkout was not edited.
`DOCKER_HOST=tcp://localhost:2375`, `DEMO_VERSION=2.0.2`; anonymous local
`DOCKER_CONFIG=D:\incident-zero\.build\docker` avoids inaccessible host credentials.
All injections and resets below invoked `python -m faultctl`; diagnostic tools
only read telemetry, container state and local evidence. No direct Docker mutation
was issued outside that operator package.

## Verified results

| Check | Observed result | Wall-clock seconds |
| --- | --- | ---: |
| `python -m faultctl status` | Passed; 21/21 running, all endpoints reachable, 64 new frontend trace IDs in a 60 s window | 61.313 |
| Clean `health_table()` | 21 rows; all 13 traffic services have error rate 0 and non-null p95/RPS | 2.313 |
| `faultctl inject payment-failure` | Positive operator read-back; injection succeeded | 5.047 |
| Fresh checkout error traces | Appeared after injection completion | 6.906 |
| Error rate above zero | Payment 0.083333; checkout remained 0 in that first metric sample | 46.906 after injection completion |
| Payment reset | Exit 0, original mount restored, pristine/source check passed, stack ready | 3.359 |
| Fresh successful checkout after reset | First successful trace; no new checkout error traces in the observed recovery window | 23.187 after reset completion |
| Metric recovery | Health eventually clean; **not verified within 60 s** | 117.906 after reset completion |
| CPU starvation: recommendation | NanoCpus 50,000,000, then restored to 0; original 52,428,800-byte memory limit retained | 0.797 inject / 7.000 reset |
| Network latency: product-catalog | qdisc `delay 800ms loss 10%`; immediate and final reset qdisc both `noqueue`, no netem | 1.562 inject / 3.156 reset |
| Stopped recommendation | `exited` visible in one `get_container_health` call; then restored running | 4.094 inject / 0.235 read / 2.890 reset |
| Stopped cache (SPEC 02) | valkey-cart `exited` visible in one call; reset restored it | 1.141 inject / 0.219 read / 2.718 reset |
| Demo Git status | Empty porcelain output, exit 0 | 0.313 |
| Final immediate readiness | All checks passed, all 21 containers running | 0.781 |

Payment injection took 51.953 s from command start through both symptom checks.
The 60-second recovery observation began after reset completed; its full duration
including reset and call overhead was 63.578 s. Each trace query used explicit
microsecond start/end bounds restricted to the post-injection or post-reset
period. Recovery required successful fresh checkout traffic as well as zero new
error traces; an empty response alone was never treated as recovery. Polling
finished just after the minute boundary, so these are observations, not proof
that no error could arrive later through delayed export.

The operator reported pristine SHA-256
`20ecdbe4edca79013c3199e76a950838ee30868d8f5278ca601f44b215811793`
on every reset. All resets returned `fault_state_clean=true` and `stack_ready=true`.
The network read-back was `qdisc netem 8002: root refcnt 9 limit 1000 delay 800ms
loss 10%`; reset reported `qdisc noqueue 0: root refcnt 2` twice.

## Log acceptance correction

The initial payment WARN query returned no OpenSearch records. A follow-up
against the same failure interval found five Docker WARN records, including
`Payment request failed. Invalid token. app.loyalty.level=gold`, with trace IDs.
`get_logs('payment')` now falls back to Docker when its OpenSearch query has no
hits. A retained-interval query returned all five in 1.2158 s, and its first
`dlog:` ID resolved live in 0.2303 s. The records were emitted during injection;
the corrected tool was checked after reset. The requirement to return a payment
failure log is verified; an ERROR-severity payment line is **not verified**
because this SDK logs the exception at WARN. Checkout emitted INFO request logs,
so its WARN query correctly returned zero; use TRACE to include unclassified text.

## Confirmed telemetry names

Prometheus discovery returned **270** metric names. Confirmed count:
`traces_span_metrics_calls_total`; histogram:
`traces_span_metrics_duration_milliseconds_bucket`. Both use `service_name`,
`span_name`, `span_kind`, `status_code`, `job`, `service_namespace`; histogram
buckets add `le`. Confirmed container names: `container_cpu_utilization_ratio`,
`container_cpu_usage_nanoseconds_total`, `container_memory_usage_total_bytes`,
`container_memory_usage_limit_bytes`, `container_memory_percent_ratio`, each with
`container_name`. `httpcheck_status` carries `http_method`, `http_status_class`,
`http_status_code`, `http_url`. Details and sample values: `tools/METRICS.md`.

OpenSearch index **`otel`** mapped **`resource.service.name`** and exact-match
**`resource.service.name.keyword`**, **`severity.text`** (also `.keyword`),
**`severity.number`**, **`body`**, **`traceId`**, **`spanId`**, **`@timestamp`** and
**`observedTimestamp`**. The service name is not under `resource.attributes`.
Details: `tools/LOGS.md`. Jaeger API is
`http://localhost:8080/jaeger/ui/api`; searches send explicit microsecond bounds.

## Limits and remaining unverified items

- **Not verified:** two-minute metric error rate returning clean within 60 s.
  It actually cleared at 117.906 s; the export interval and rate window retain
  pre-reset errors. Fresh successful checkout traffic did recover within 60 s.
- **Not verified:** fresh `up -d` to full readiness duration in this follow-up;
  the stack was already running and was deliberately left running.
- **Not verified:** a live `action_log:` record, since round 1 has no Action API
  journal entries. Its source matching and snapshot behavior use unit fixtures.
- **Not verified:** application-level latency/saturation symptoms of the short
  CPU/network injections. Their actual configured state and reset were read back.
- The actual minimal stack has 21 containers; the specs' 22-container count does
  not describe this version. Infrastructure with no span traffic keeps null
  service metrics. RPS aggregates span kinds and means spans/s, not unique requests.
- A symlink-creation test is skipped because this Windows account lacks that
  privilege; ordinary traversal and run-path confinement tests pass.

## Exact acceptance command/call ledger

Python was `.\.venv\Scripts\python.exe`. The recording harness was invoked as
`.\.venv\Scripts\python.exe .build/accept_round1b.py`; that local harness and raw
JSONL are retained under ignored `.build/`. Function calls below are the actual
Python diagnostic calls from that harness; CLI mutations are shown in full.
Each elapsed time measures the individual call including startup for subprocesses.
Timestamps below are UTC; add 05:30 for IST.

The separate readiness command was `.\.venv\Scripts\python.exe -m faultctl status`
(61.313 s, exit 0). An initial attempt to spawn Python using a relative forward-
slash executable path failed before starting faultctl; rerunning with the absolute
`sys.executable` produced the recorded status result. The initial plain demo Git
status hit Windows ownership checking; the successful command uses a per-command
`safe.directory` setting and does not edit Git configuration or the demo checkout.

| UTC completion | Command / call | Seconds | Result |
| --- | --- | ---: | --- |
| 09:20:46.162 | `health_table()` | 2.3130 | 21 rows; positive error rates {} |
| 09:20:46.179 | `get_metrics('error_rate_by_service')` | 0.0000 | 13 records; 26 evidence IDs; source=prometheus |
| 09:20:46.211 | `get_traces('checkout')` | 0.0310 | 0 records; 0 evidence IDs; source=jaeger |
| 09:20:46.538 | `get_logs('payment')` | 0.3130 | 0 records; 0 evidence IDs; source=opensearch |
| 09:20:48.241 | `get_container_health()` | 1.7030 | 21 records; 126 evidence IDs; source=docker |
| 09:20:48.533 | `get_deploy_history()` | 0.2970 | 24 records; 24 evidence IDs; source=action_log |
| 09:20:48.543 | `list_services()` | 0.0150 | 14 records; 0 evidence IDs; source=jaeger |
| 09:20:53.597 | `.\.venv\Scripts\python.exe -m faultctl inject payment-failure` | 5.0470 | exit 0; passed |
| 09:20:53.611 | `get_traces('checkout', lookback_s=1, limit=5)` | 0.0160 | 0 records; 0 evidence IDs; source=jaeger |
| 09:20:55.982 | `health_table()` | 2.3750 | 21 rows; positive error rates {} |
| 09:20:59.028 | `get_traces('checkout', lookback_s=5, limit=5)` | 0.0470 | 1 records; 2 evidence IDs; source=jaeger |
| 09:21:00.498 | `health_table()` | 1.4680 | 21 rows; positive error rates {} |
| 09:21:03.536 | `get_traces('checkout', lookback_s=9, limit=5)` | 0.0320 | 1 records; 2 evidence IDs; source=jaeger |
| 09:21:05.845 | `health_table()` | 2.3120 | 21 rows; positive error rates {} |
| 09:21:08.872 | `get_traces('checkout', lookback_s=15, limit=5)` | 0.0310 | 1 records; 2 evidence IDs; source=jaeger |
| 09:21:10.501 | `health_table()` | 1.6250 | 21 rows; positive error rates {} |
| 09:21:13.534 | `get_traces('checkout', lookback_s=19, limit=5)` | 0.0320 | 1 records; 2 evidence IDs; source=jaeger |
| 09:21:15.849 | `health_table()` | 2.3120 | 21 rows; positive error rates {} |
| 09:21:18.882 | `get_traces('checkout', lookback_s=25, limit=5)` | 0.0310 | 1 records; 2 evidence IDs; source=jaeger |
| 09:21:20.491 | `health_table()` | 1.6100 | 21 rows; positive error rates {} |
| 09:21:23.525 | `get_traces('checkout', lookback_s=29, limit=5)` | 0.0320 | 2 records; 4 evidence IDs; source=jaeger |
| 09:21:25.828 | `health_table()` | 2.2960 | 21 rows; positive error rates {} |
| 09:21:28.872 | `get_traces('checkout', lookback_s=35, limit=5)` | 0.0470 | 2 records; 4 evidence IDs; source=jaeger |
| 09:21:30.492 | `health_table()` | 1.6100 | 21 rows; positive error rates {} |
| 09:21:33.529 | `get_traces('checkout', lookback_s=39, limit=5)` | 0.0320 | 2 records; 4 evidence IDs; source=jaeger |
| 09:21:35.839 | `health_table()` | 2.3120 | 21 rows; positive error rates {} |
| 09:21:38.909 | `get_traces('checkout', lookback_s=45, limit=5)` | 0.0630 | 4 records; 8 evidence IDs; source=jaeger |
| 09:21:40.497 | `health_table()` | 1.5930 | 21 rows; positive error rates {'payment': 0.083333, 'recommendation': 0.045455} |
| 09:21:40.963 | `get_logs('payment', lookback_s=120)` | 0.4690 | 0 records; 0 evidence IDs; source=opensearch |
| 09:21:41.170 | `get_logs('checkout', lookback_s=120)` | 0.2030 | 0 records; 0 evidence IDs; source=docker |
| 09:21:41.207 | `resolve('trace:673b18c344d72acf9cdda35de1b36489')` | 0.0310 | resolved from live (jaeger) |
| 09:21:41.243 | `resolve('span:673b18c344d72acf9cdda35de1b36489/ff3df97b26ec356c')` | 0.0470 | resolved from live (jaeger) |
| 09:21:41.264 | `resolve('metric:query{__query__="(sum by (service_name) (rate(traces_span_metrics_calls_total{status_code=\\"STATUS_CODE_ERROR\\"}[2m])) or (0 * sum by (service_name) (rate(traces_span_metrics_calls_total[2m])))) / sum by (service_name) (rate(traces_span_metrics_calls_total[2m]))",service_name="ad"}@1792747298.911=0.0')` | 0.0160 | resolved from live (prometheus) |
| 09:21:41.275 | `resolve('metric:query{__query__="(sum by (service_name) (rate(traces_span_metrics_calls_total{status_code=\\"STATUS_CODE_ERROR\\"}[2m])) or (0 * sum by (service_name) (rate(traces_span_metrics_calls_total[2m])))) / sum by (service_name) (rate(traces_span_metrics_calls_total[2m]))",service_name="cart"}@1792747298.911=0.0')` | 0.0160 | resolved from live (prometheus) |
| 09:21:44.634 | `.\.venv\Scripts\python.exe -m faultctl reset --timeout 60` | 3.3590 | exit 0; passed |
| 09:21:44.655 | `get_traces('checkout', lookback_s=1, limit=5)` | 0.0160 | 0 records; 0 evidence IDs; source=jaeger |
| 09:21:44.664 | `get_traces('checkout', lookback_s=1, errors_only=False, limit=20)` | 0.0000 | 0 records; 0 evidence IDs; source=jaeger |
| 09:21:46.965 | `health_table()` | 2.3120 | 21 rows; positive error rates {'payment': 0.083333, 'recommendation': 0.045455} |
| 09:21:51.991 | `get_traces('checkout', lookback_s=7, limit=5)` | 0.0160 | 0 records; 0 evidence IDs; source=jaeger |
| 09:21:52.023 | `get_traces('checkout', lookback_s=7, errors_only=False, limit=20)` | 0.0310 | 0 records; 0 evidence IDs; source=jaeger |
| 09:21:53.576 | `health_table()` | 1.5460 | 21 rows; positive error rates {'payment': 0.083333, 'recommendation': 0.045455} |
| 09:21:58.607 | `get_traces('checkout', lookback_s=13, limit=5)` | 0.0320 | 0 records; 0 evidence IDs; source=jaeger |
| 09:21:58.639 | `get_traces('checkout', lookback_s=13, errors_only=False, limit=20)` | 0.0310 | 0 records; 0 evidence IDs; source=jaeger |
| 09:22:00.482 | `health_table()` | 1.8440 | 21 rows; positive error rates {'payment': 0.083333, 'recommendation': 0.045455} |
| 09:22:05.510 | `get_traces('checkout', lookback_s=20, limit=5)` | 0.0310 | 0 records; 0 evidence IDs; source=jaeger |
| 09:22:05.538 | `get_traces('checkout', lookback_s=20, errors_only=False, limit=20)` | 0.0160 | 1 records; 1 evidence IDs; source=jaeger |
| 09:22:07.828 | `health_table()` | 2.2960 | 21 rows; positive error rates {'payment': 0.083333, 'recommendation': 0.045455} |
| 09:22:12.841 | `get_traces('checkout', lookback_s=28, limit=5)` | 0.0160 | 0 records; 0 evidence IDs; source=jaeger |
| 09:22:12.871 | `get_traces('checkout', lookback_s=28, errors_only=False, limit=20)` | 0.0310 | 1 records; 1 evidence IDs; source=jaeger |
| 09:22:15.194 | `health_table()` | 2.3130 | 21 rows; positive error rates {'payment': 0.083333, 'recommendation': 0.045455} |
| 09:22:20.227 | `get_traces('checkout', lookback_s=35, limit=5)` | 0.0320 | 0 records; 0 evidence IDs; source=jaeger |
| 09:22:20.293 | `get_traces('checkout', lookback_s=35, errors_only=False, limit=20)` | 0.0620 | 3 records; 3 evidence IDs; source=jaeger |
| 09:22:22.547 | `health_table()` | 2.2500 | 21 rows; positive error rates {'payment': 0.083333, 'recommendation': 0.045455} |
| 09:22:27.564 | `get_traces('checkout', lookback_s=42, limit=5)` | 0.0160 | 0 records; 0 evidence IDs; source=jaeger |
| 09:22:27.651 | `get_traces('checkout', lookback_s=42, errors_only=False, limit=20)` | 0.0940 | 3 records; 3 evidence IDs; source=jaeger |
| 09:22:29.980 | `health_table()` | 2.3280 | 21 rows; positive error rates {'payment': 0.083333, 'recommendation': 0.045455} |
| 09:22:35.006 | `get_traces('checkout', lookback_s=50, limit=5)` | 0.0150 | 0 records; 0 evidence IDs; source=jaeger |
| 09:22:35.089 | `get_traces('checkout', lookback_s=50, errors_only=False, limit=20)` | 0.0940 | 4 records; 4 evidence IDs; source=jaeger |
| 09:22:37.398 | `health_table()` | 2.2970 | 21 rows; positive error rates {'payment': 0.083333, 'recommendation': 0.045455} |
| 09:22:42.433 | `get_traces('checkout', lookback_s=57, limit=5)` | 0.0310 | 0 records; 0 evidence IDs; source=jaeger |
| 09:22:42.552 | `get_traces('checkout', lookback_s=57, errors_only=False, limit=20)` | 0.1090 | 6 records; 6 evidence IDs; source=jaeger |
| 09:22:44.864 | `health_table()` | 2.3130 | 21 rows; positive error rates {'ad': 0.066667, 'cart': 0.00578, 'frontend': 0.014778, 'payment': 0.25, 'recommendation': 0.05} |
| 09:22:46.937 | `health_table()` | 2.0780 | 21 rows; positive error rates {'ad': 0.066667, 'cart': 0.00578, 'frontend': 0.014778, 'payment': 0.25, 'recommendation': 0.05} |
| 09:22:53.581 | `health_table()` | 1.6400 | 21 rows; positive error rates {'ad': 0.066667, 'cart': 0.00578, 'frontend': 0.014778, 'payment': 0.25, 'recommendation': 0.05} |
| 09:23:00.471 | `health_table()` | 1.8910 | 21 rows; positive error rates {'ad': 0.066667, 'cart': 0.00578, 'frontend': 0.014778, 'payment': 0.25, 'recommendation': 0.05} |
| 09:23:07.787 | `health_table()` | 2.3130 | 21 rows; positive error rates {'ad': 0.066667, 'cart': 0.00578, 'frontend': 0.014778, 'payment': 0.25, 'recommendation': 0.05} |
| 09:23:15.086 | `health_table()` | 2.3120 | 21 rows; positive error rates {'ad': 0.066667, 'cart': 0.00578, 'frontend': 0.014778, 'payment': 0.25, 'recommendation': 0.05} |
| 09:23:21.512 | `health_table()` | 1.4220 | 21 rows; positive error rates {'ad': 0.066667, 'cart': 0.00578, 'frontend': 0.014778, 'payment': 0.25, 'recommendation': 0.05} |
| 09:23:28.811 | `health_table()` | 2.2970 | 21 rows; positive error rates {'ad': 0.066667, 'cart': 0.00578, 'frontend': 0.014778, 'payment': 0.25, 'recommendation': 0.05} |
| 09:23:36.121 | `health_table()` | 2.3120 | 21 rows; positive error rates {'ad': 0.066667, 'cart': 0.00578, 'frontend': 0.014778, 'payment': 0.25, 'recommendation': 0.05} |
| 09:23:42.552 | `health_table()` | 1.4220 | 21 rows; positive error rates {} |
| 09:23:43.338 | `.\.venv\Scripts\python.exe -m faultctl inject cpu-starve --svc recommendation` | 0.7970 | exit 0; passed |
| 09:23:44.573 | `get_container_health(['recommendation'])` | 1.2340 | recommendation: running, NanoCpus=50000000, Memory=52428800 |
| 09:23:51.584 | `.\.venv\Scripts\python.exe -m faultctl reset --timeout 60` | 7.0000 | exit 0; passed |
| 09:23:53.731 | `get_container_health(['recommendation'])` | 2.1570 | recommendation: running, NanoCpus=0, Memory=52428800 |
| 09:23:55.303 | `.\.venv\Scripts\python.exe -m faultctl inject network-latency --svc product-catalog` | 1.5620 | exit 0; passed |
| 09:23:58.452 | `.\.venv\Scripts\python.exe -m faultctl reset --timeout 60` | 3.1560 | exit 0; passed |
| 09:24:00.450 | `get_container_health(['product-catalog'])` | 2.0000 | product-catalog: running, NanoCpus=0, Memory=20971520 |
| 09:24:04.549 | `.\.venv\Scripts\python.exe -m faultctl inject container-stopped --svc recommendation` | 4.0940 | exit 0; passed |
| 09:24:04.780 | `get_container_health(['recommendation'])` | 0.2350 | recommendation: exited, NanoCpus=0, Memory=52428800 |
| 09:24:07.672 | `.\.venv\Scripts\python.exe -m faultctl reset --timeout 60` | 2.8900 | exit 0; passed |
| 09:24:08.929 | `get_container_health(['recommendation'])` | 1.2500 | recommendation: running, NanoCpus=0, Memory=52428800 |
| 09:24:10.066 | `.\.venv\Scripts\python.exe -m faultctl inject cache-unavailable` | 1.1410 | exit 0; passed |
| 09:24:10.276 | `get_container_health(['valkey-cart'])` | 0.2190 | valkey-cart: exited, NanoCpus=0, Memory=20971520 |
| 09:24:13.006 | `.\.venv\Scripts\python.exe -m faultctl reset --timeout 60` | 2.7180 | exit 0; passed |
| 09:24:14.088 | `.\.venv\Scripts\python.exe -m faultctl status --traffic-seconds 0` | 0.7810 | exit 0; passed |
| 09:24:16.390 | `health_table()` | 2.2970 | 21 rows; positive error rates {} |

## Snapshot follow-up

`.\.venv\Scripts\python.exe .build/verify_snapshots.py` used
`run_dir='runs/round1b-snapshot-verification'` for the calls below. Every returned
evidence ID had a file, including all 126 container facts and all 165 joined
health facts. Filenames are SHA-256 IDs because Windows cannot use the logical
IDs' colon/slash/quote characters. The original ID is retained in each JSON.

| Call | Seconds including snapshot writes | Evidence IDs | Missing files |
| --- | ---: | ---: | ---: |
| `get_metrics args=('error_rate_by_service',) kwargs={}` | 0.0736 | 26 | 0 |
| `get_traces args=('checkout',) kwargs={'lookback_s': 1800, 'limit': 5}` | 0.2747 | 10 | 0 |
| `get_logs args=('payment',) kwargs={'lookback_s': 1800}` | 1.2158 | 5 | 0 |
| `get_logs args=('ad',) kwargs={'severity_min': 'INFO'}` | 0.3081 | 25 | 0 |
| `get_container_health args=() kwargs={}` | 2.6173 | 126 | 0 |
| `get_deploy_history args=() kwargs={}` | 0.3440 | 6 | 0 |
| `health_table args=() kwargs={}` | 2.4074 | 165 | 0 |
| `list_services args=() kwargs={}` | 0.0200 | 0 | 0 |

Six evidence classes re-fetched live: metric, trace, span, Docker log, OpenSearch log and container.

| Class | Seconds | Resolution |
| --- | ---: | --- |
| metric | 0.0094 | live |
| trace | 0.0575 | live |
| span | 0.0423 | live |
| dlog | 0.2303 | live |
| log | 0.1385 | live |
| container | 0.2397 | live |

For a controlled unavailable-backend check, only the verification process set
`JAEGER_URL=http://127.0.0.1:1` and resolved the just-captured trace. It returned
`resolved_from="snapshot"` and its path in 2.0729 s.
No backend was stopped or changed. Natural backend-retention expiry was **not
verified**; fallback after a read failure was verified.
