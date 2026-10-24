---
id: load
applies_to: [frontend, frontend-proxy, load-generator]
category: load
version: 1
action_types: [throttle_load]
---
# Excess generated traffic

## Symptoms
Frontend request rate rises relative to a measured baseline, often with rising CPU or latency and eventually errors. A homepage-heavy load can raise edge traffic while downstream request rates stay comparatively flat.

## What to check first
Use `get_metrics(promql="rps_by_service", lookback_s=600)`, `get_metrics(promql="container_cpu", lookback_s=600)` and `get_metrics(promql="p95_latency_by_service", lookback_s=600)`. Compare `get_traces(service="frontend", errors_only=False, lookback_s=300)` by route and `get_logs(service="frontend-proxy", severity_min="TRACE", lookback_s=300)` for access patterns. Check `get_container_health(names=["load-generator", "frontend"])`.

## How to confirm
Require measured traffic above a relevant baseline and correlated service saturation. Span counts are not unique users or browser page views. Route concentration and flat downstream traffic can explain a frontend-only surge. If the baseline is unavailable, record uncertainty instead of inventing a normal rate.

## Allowed remediation
Propose Action API `throttle_load` for `load-generator`, using policy-approved users and spawn_rate parameters. The dry run records the intended reduction; obtain human approval before changing load. Do not claim the throttle repairs an unrelated application error.

## Rollback
The Action API can conditionally restore the previously recorded workload if verification fails and the current world still matches. If restoration is unsafe or blocked, escalate with the retained workload and verification results.

## Verification criteria
Require the original saturation predicates to recover with sufficient measured frontend traffic and a running generator. A silent application after reducing requests is not proven healthy. The response verifier requires at least 20 measured frontend requests in its qualified window.

## Prevention
Track request mix, request-rate baselines and saturation together. Review workload changes with the same care as application changes.

## Known pitfalls
Traffic may fall because the application or generator failed. Positive requests and successful responses must corroborate recovery. A past throttle's outcome does not establish today's cause.
