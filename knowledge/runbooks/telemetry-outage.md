---
id: telemetry-outage
applies_to: [otel-collector, prometheus, jaeger, opensearch]
category: unknown
version: 1
action_types: []
---
# Telemetry is missing or stale

## Symptoms
Metrics disappear across services, trace searches unexpectedly return nothing, logs stop arriving, or a backend reports an error. Application health is unknown until the observation path is assessed.

## What to check first
Use `get_container_health(names=["otel-collector", "prometheus", "jaeger", "opensearch"])` and `get_metrics(promql="rps_by_service", lookback_s=300)`. Compare a known active application's `get_traces(service="frontend", errors_only=False, lookback_s=300)` and `get_logs(service="frontend-proxy", severity_min="TRACE", lookback_s=300)`. Check response timestamps and backend warnings.

## How to confirm
Distinguish a query matching no data from an unavailable backend and from a quiet application. Export delay means the latest sample may lag real time. A whole missing source limits confidence even when another source is available. A stopped telemetry container proves its availability problem, not the application's health.

## Allowed remediation
Escalate the observability gap and preserve partial evidence. Do not propose an application fix from missing data. If an independent diagnosis later establishes a stopped, allowlisted telemetry component, apply the container-down runbook with its own risk review and approval.

## Rollback
No change follows from missing telemetry alone. Any separately approved recovery action retains its own Action API rollback rules.

## Verification criteria
First establish fresh telemetry from the restored backend, then re-evaluate application health under positive traffic. Old retained evidence helps explain the past but cannot verify current recovery.

## Prevention
Monitor ingestion freshness, collector health and each backend independently. Keep retained evidence snapshots with checksums for post-incident review.

## Known pitfalls
An empty error result never means zero errors unless fresh successful traffic establishes the denominator. OpenSearch coverage differs by service; approved Docker stdout fallback may supply logs but does not repair a missing metrics or trace source.
