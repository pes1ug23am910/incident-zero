---
id: resource-starvation
applies_to: [ad, recommendation, frontend, checkout, cart]
category: resource_starvation
version: 1
action_types: []
---
# CPU or memory starvation

## Symptoms
Latency increases while CPU is constrained near a low quota, or memory approaches a limit and the process restarts. One overloaded service can slow unrelated services on the same host.

## What to check first
Use `get_container_health(names=[<suspect>])` for NanoCpus, Memory, RestartCount and current usage. Read `get_metrics(promql="container_cpu", lookback_s=600)`, `get_metrics(promql="container_memory", lookback_s=600)` and `get_metrics(promql="p95_latency_by_service", lookback_s=600)`. Compare `get_traces(service=<suspect>, errors_only=False, lookback_s=300)` with startup/error logs.

## How to confirm
Compare quotas and limits with retained normal observations, not an assumed universal limit. CPU pinned at a small allowance differs from CPU doing substantial application work. A declining limit differs from a steady limit with growing usage. Require a resource observation and a correlated service-impact signal; one high memory sample does not prove a leak.

## Allowed remediation
Escalate with the limit, usage and impact evidence. The Action API has no resource-quota change. A restart does not restore a constrained allocation and must not be proposed as a quota repair.

## Rollback
No automatic resource change is available. An operator's resource restoration needs its own measured baseline and rollback review.

## Verification criteria
After operator repair, show fresh resource headroom, stable lifecycle and recovery of the original latency/error signal over the qualified verification window.

## Prevention
Monitor utilization relative to allocated capacity, memory growth and restart deltas. Retain resource limits with normal telemetry for comparisons.

## Known pitfalls
CPU utilization units depend on the exported metric and can exceed 100 for several cores. OOMKilled may reset after restart. Repeated lifecycle fields are one evidence source, not several independent confirmations.
