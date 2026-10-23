# Stack and fault injection verification

Date: 2026-10-23. Official OpenTelemetry Demo tag 2.0.2, minimal mode.
The checkout at `D:\opentelemetry-demo` is read-only to this implementation.
All generated state and overrides are under `D:\incident-zero`.

## Initial bring-up

Executed from the team repository with `DEMO_VERSION=2.0.2`:

```powershell
docker compose --project-directory D:\opentelemetry-demo -f D:\opentelemetry-demo\docker-compose.minimal.yml up -d
```

Compose returned success and created **21 containers**, the actual service count
in this version's minimal file (the specification's 22 is not this file's count).
At 13:42:34 IST the shop returned HTTP 200, Prometheus returned ready, OpenSearch
answered on dynamically published port 65341, and Jaeger answered through the
frontend proxy. These endpoint checks completed in 1.18 seconds.

**Full readiness did not succeed within five minutes.** The unmodified
`otel-collector` image 0.120.1 cannot start its Docker statistics receiver against
this Docker Engine 29.8.1: `client version 1.25 is too old. Minimum supported API
version is 1.40`. The collector continuously restarts, so no application metrics,
traces, or logs are exported. The daemon reports API 1.56, minimum 1.40.
The demo configuration, image versions, and daemon settings were preserved.
Telemetry-dependent acceptance is **not verified**; empty responses cannot prove
either the absence of an incident or recovery.

## Boundary decisions

The specification's direct edit to the demo checkout conflicts with the explicit
read-only constraint. Injection instead copies the pristine settings into
`faultctl/.pristine`, maintains an active copy under `faultctl/.state`, and uses a
repository-owned Compose override to redirect only the injection data mount.
Reset restores the official mount. Neither official configuration nor source is
written. Only the injection package reads this state, solely for setup and
positive read-back; diagnostic tools cannot import it.

Manual `docker restart` does not increment Docker's automatic `RestartCount`.
The restart-loop mechanism therefore records completed iterations and verifies
`StartedAt` changes; it does not claim automatic restart counts increased.

## Acceptance results

All times below are wall-clock seconds, including Python/CLI startup. Reset was
run with `--timeout 0` to perform cleanup and one complete readiness check without
waiting again for the known collector failure. Every reset returned exit 1 with
`fault_state_clean: true`, `stack_ready: false`.

| Acceptance | Result | Seconds |
|---|---|---:|
| Fresh `status`, including 60-second traffic observation | Not ready: collector restarts, three application trace services absent, no new frontend traces; shop/Prometheus/OpenSearch/Locust reachable | 61.023 |
| `inject payment-failure` | Variant, active mount, watcher startup, and unchanged pristine source verified | 4.303 |
| Checkout error trace polling over 60 s | **Not verified**: 13 successful API calls, each with zero traces; collector unavailable | 60.756 |
| Payment reset | Original data mount and pristine bytes restored; telemetry recovery **not verified** | 3.559 |
| `inject cpu-starve --svc recommendation` | `NanoCpus=50000000` | 0.699 |
| CPU reset | Original `NanoCpus=0`, memory and swap limits restored | 6.566 |
| `inject network-latency --svc product-catalog` | qdisc shows `delay 800ms loss 10%` | 1.537 |
| Network reset | Both immediate and final qdisc show `noqueue`, no netem | 3.120 |
| `inject --combo payment-failure,cart-intermittent` | Both variants verified; watcher WRITE event observed | 6.846 |
| Remaining six flag incidents in one sequence | All read back successfully; application symptoms **not verified** | 16.323 |
| All flag incidents reset | Original mount and pristine bytes restored | 3.344 |
| Container stop + memory starvation on recommendation | Exited state and memory/swap `50331648` verified | 4.545 |
| Stop + memory reset | Running again, original 50 MiB limit and swap restored | 3.048 |
| Restart loop on quote | First restart succeeded; later `StartedAt=08:25:43.180562753Z` confirms continuing loop; automatic restart count correctly remains 0 | 1.309 to inject |
| Restart-loop reset | Worker cancelled and original container recreated | 3.409 |

The baseline settings SHA-256 repeatedly read back by the operator package was
`20ecdbe4edca79013c3199e76a950838ee30868d8f5278ca601f44b215811793`.
The helper image `incident-zero-netem:local` was built from the supplied Dockerfile
(Alpine 3.21 plus iproute2); the successful build's reported stages took about 15 s.
Two initial sandbox-only build attempts failed due to inaccessible host Docker
configuration/credential storage; an anonymous repository-local `DOCKER_CONFIG`
under `.build/docker` resolved this without reading credentials or changing host
configuration. The original build was not stopwatch-timed.

`pytest tests/test_faultctl.py tests/test_no_flag_reads.py` passes. Faultctl has 14
unit tests covering STOP, allowlisting, baseline tamper refusal, rollback state,
failed cleanup journaling, and flag/infrastructure read-back. The required source
scans are included. Raw local operator transcripts are under `.build` (ignored),
and injection journals are under `runs` (ignored).

All source files in the official demo remain unchanged (`git status --porcelain`
empty). Complete readiness, new checkout error traces after payment injection,
and their disappearance after reset are **not verified**. No empty telemetry
response is counted as a successful recovery. The cache fault's live check is
recorded with the read-tool acceptance in BUILD_02.md.
