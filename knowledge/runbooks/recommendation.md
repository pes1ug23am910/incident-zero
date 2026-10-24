---
id: recommendation
applies_to: [recommendation]
category: service
version: 1
action_types: [toggle_flag, restart_service]
---
# Recommendation availability and memory growth

## Symptoms
ListRecommendations becomes slow, frontend calls fail, or the recommendation process disappears. Growing memory with repeated resets can create a sawtooth pattern; a stopped process instead removes fresh server spans.

## What to check first
Read `get_container_health(names=["recommendation", "product-catalog"])`, `get_metrics(promql="container_memory", lookback_s=900)` and `get_metrics(promql="p95_latency_by_service", lookback_s=900)`. Use `get_traces(service="recommendation", errors_only=False, lookback_s=300)` for internal work and product-list counts, and `get_logs(service="recommendation", severity_min="INFO", lookback_s=300)` for cache hit/miss and startup patterns.

## How to confirm
Repeated growth in memory and app.products.count with an unchanged limit supports runaway application caching. A reduced limit with otherwise ordinary application behavior supports resource starvation. A stopped recommendation container plus frontend connection failures proves container_down. A failing catalogue may be the actual dependency origin. One memory sample or an old restart count is insufficient.

## Allowed remediation
For an evidenced local application workload fault, propose Action API `toggle_flag` with `service=recommendation`. For a stopped component, propose `restart_service` after checking dependencies. Resource-limit repair is outside the allowlist and escalates. Every proposal requires policy validation, dry run and human approval.

## Rollback
Setting changes use conditional Action API rollback. A restart cannot recreate prior process state. Escalate non-recovery and avoid a repeated restart cycle that conceals continued growth.

## Verification criteria
Confirm fresh successful recommendation calls, stable lifecycle and memory behavior over the observed window, plus recovery of frontend symptoms. A short flat memory interval does not prove a leak can never recur; record that limit.

## Prevention
Track cache cardinality and memory growth, use bounded caches, and alert on restart deltas. Retain normal limits for infrastructure comparisons.

## Known pitfalls
Old successful payment memories cannot explain a freshly stopped recommendation container. A process restart temporarily reduces memory even when the underlying workload will grow again; describe that outcome honestly.
