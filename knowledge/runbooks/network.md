---
id: network
applies_to: [frontend, checkout, payment, cart, product-catalog, recommendation, ad]
category: network
version: 1
action_types: []
---
# Delay or loss along a service edge

## Symptoms
Caller duration increases without a comparable increase in the callee's own work. Timeouts and intermittent UNAVAILABLE can appear while containers remain running. Tail latency can rise more sharply than typical latency.

## What to check first
Use `get_traces(service=<caller>, errors_only=False, lookback_s=300)` to compare client and server durations and peer identity. Check `get_metrics(promql="p95_latency_by_service", lookback_s=600)`, `get_metrics(promql="container_cpu", lookback_s=600)` and `get_container_health(names=[<caller>, <callee>])`. Search `get_logs(service=<caller>, severity_min="WARN", lookback_s=300)` for timeouts.

## How to confirm
Compare several fresh traces against a normal baseline. A large client-to-server duration gap with normal callee work is consistent with a path problem, but queueing, retries and incomplete traces can also create gaps. Busy or quota-limited CPU and slow application spans support other explanations. State the uncertainty; these tools do not measure packet loss directly.

## Allowed remediation
Escalate with the affected edge, trace timings and resource checks. There is no allowlisted Action API networking change. Do not substitute a restart or an application setting change for an unverified network diagnosis.

## Rollback
No automatic change is proposed. An operator must define a restoration and rollback plan for any external network repair.

## Verification criteria
After an operator's repair, compare fresh client/server timings and the original latency/error alert under measured traffic. Missing server spans remain an observability limitation.

## Prevention
Track edge latency alongside internal server latency and establish baseline distributions. Add approved path diagnostics only through a reviewed tooling change.

## Known pitfalls
An image-only proxy delay can resemble a network delay; inspect affected routes and proxy response metadata. Do not claim an exact packet-loss percentage from a timeout ratio.
