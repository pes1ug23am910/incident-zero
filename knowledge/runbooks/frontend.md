---
id: frontend
applies_to: [frontend, frontend-proxy]
category: service
version: 1
action_types: [toggle_flag, restart_service, throttle_load]
---
# Frontend and request entry

## Symptoms
Customers encounter failed product views, cart requests or checkout, elevated page latency, or a large change in homepage traffic. The frontend is a symptom owner for many downstream failures.

## What to check first
Read `get_metrics(promql="error_rate_by_service", lookback_s=300)` and `get_metrics(promql="rps_by_service", lookback_s=600)`. Use `get_traces(service="frontend", errors_only=True, lookback_s=120)` to follow failing calls, `get_logs(service="frontend-proxy", severity_min="TRACE", lookback_s=120)` for affected routes, and `get_container_health(names=["frontend", "frontend-proxy"])` for local availability.

## How to confirm
Follow frontend -> checkout -> payment and frontend -> cart -> valkey-cart when those paths fail. Recommendation, product-catalog, currency, shipping and ad failures can also propagate to frontend. A local frontend fault requires evidence originating there. Increased homepage request rate with flat downstream rates is consistent with edge-focused load, subject to measured baseline and saturation checks.

## Allowed remediation
Choose the runbook for the proved cause. A local application fault can propose Action API `toggle_flag` for frontend; a stopped frontend can propose `restart_service`; excess generated traffic can propose `throttle_load` for load-generator. Each needs policy validation, a dry run and human approval. A downstream failure targets its downstream component, not frontend.

## Rollback
Setting and workload changes use conditional Action API rollback. A restart has no process-state inverse; unsuccessful recovery escalates.

## Verification criteria
Recheck the originally affected routes and their downstream calls with positive traffic. The frontend HTTP check supplements request errors and latency; it does not alone prove checkout or cart recovery.

## Prevention
Monitor customer routes separately and relate edge failures to dependency spans. Preserve workload baselines and distinguish image-path latency from application RPC latency.

## Known pitfalls
Frontend can have only client spans for some operations. Proxy access logs may lack severity, requiring TRACE filtering. A successful homepage does not prove that checkout or a particular product page works.
