---
id: product-catalog
applies_to: [product-catalog]
category: service
version: 1
action_types: [toggle_flag, restart_service]
---
# Product catalogue errors

## Symptoms
GetProduct failures can affect a subset of product pages or orders containing a particular product. ListProducts and other product requests may remain healthy. Recommendation depends on the catalogue as well.

## What to check first
Use `get_traces(service="product-catalog", errors_only=True, lookback_s=120)` and compare operation and product attributes across failing and successful requests. Check `get_logs(service="product-catalog", severity_min="WARN", lookback_s=120)`, `get_container_health(names=["product-catalog"])` and `get_metrics(promql="error_rate_by_service", lookback_s=300)`.

## How to confirm
Fresh catalogue-owned GetProduct errors concentrated on one observed attribute value support an operation/data-specific failure. Record the value from telemetry; never assume a fixed product identifier. A stopped catalogue instead produces caller connection failures. The current service catalogue defines no SQL database dependency for this service, so do not invent a database outage.

## Allowed remediation
For a proved local application fault, propose Action API `toggle_flag` with `service=product-catalog`; for a stopped process, propose `restart_service`. Verify the category, target and risk through policy, then obtain a dry run and human approval.

## Rollback
Use conditional setting rollback when available. Restart is not reversible. Escalate if verification fails or the deployment differs from the catalogue's recorded topology.

## Verification criteria
Check the originally failing operation and observed product subset as well as aggregate errors. Successful calls for different products can hide incomplete recovery. Verify affected frontend and checkout requests under qualified traffic.

## Prevention
Monitor errors by product operation and attribute cardinality with bounded reporting. Refresh the service catalogue after a version/topology change.

## Known pitfalls
Different demo versions can have different backing services. Missing OpenSearch logs may reflect stdout-only instrumentation; use the approved tool's fallback rather than assuming the service produced no error.
