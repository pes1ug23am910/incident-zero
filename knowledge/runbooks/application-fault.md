---
id: application-fault
applies_to: [payment, cart, product-catalog, recommendation, ad, checkout, frontend]
category: application_flag
version: 1
action_types: [toggle_flag]
---
# Application fault in a running service

## Symptoms
Application errors originate within a service's server span while its container remains running. Errors may affect one operation, one product attribute, or a fraction of calls. CPU and memory can remain normal; resource growth can instead identify runaway application work.

## What to check first
Use `get_metrics(promql="error_rate_by_service", lookback_s=300)` and `get_traces(service=<suspect>, errors_only=True, lookback_s=120)` to locate the deepest failing server operation. Then use `get_logs(service=<suspect>, severity_min="WARN", lookback_s=120)` for an independent application observation and `get_container_health(names=[<suspect>])` for lifecycle context. Use `get_deploy_history(lookback_s=3600)` to check recent starts and approved changes.

## How to confirm
Require a fresh service-owned exception or repeated operation-specific failure, corroborated by another signal type. Caller wrappers alone do not identify the origin. A missing server span with a client connection error calls for dependency investigation. An unchanged resource limit with rising application work differs from a newly constrained container. Record any competing evidence and lower confidence when it conflicts.

## Allowed remediation
For a confidently diagnosed application fault, propose Action API `toggle_flag` with `service=<diagnosed service>`: disable the failure switch for that service. The Action API resolves the setting internally. The proposal must pass the category and service allowlist, a dry run and explicit human approval. Do not use a remembered action as proof of diagnosis.

## Rollback
If verification fails, request the Action API's conditional rollback to its recorded prior setting, subject to the current-world check and stop control. Escalate when rollback cannot safely proceed. Do not reconstruct or query prior settings through diagnostic tools.

## Verification criteria
Recheck the original error or latency signal and fresh successful calls to the affected operation. Require the response verifier's traffic-qualified observation window and two consecutive healthy samples. A running container or an empty error query alone is insufficient.

## Prevention
Monitor errors by service and operation, deploy changes with rollback metadata, and alert on application resource growth before exhaustion.

## Known pitfalls
Application exceptions and an infrastructure outage can coexist. A successful past mitigation is a hint; present telemetry and policy override it. Do not infer an activation mechanism from a familiar error string.
