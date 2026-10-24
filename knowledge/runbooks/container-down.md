---
id: container-down
applies_to: [frontend, checkout, payment, cart, product-catalog, recommendation, valkey-cart]
category: container_down
version: 1
action_types: [restart_service]
---
# A service container is down

## Symptoms
The component is exited or absent, caller client spans fail with UNAVAILABLE or connection errors, and fresh server spans disappear. The last metric series can remain visible after the process stops.

## What to check first
Call `get_container_health(names=[<suspect>])`, `get_traces(service=<caller>, errors_only=True, lookback_s=120)` and `get_metrics(promql="rps_by_service", lookback_s=300)`. Use `get_logs(service=<caller>, severity_min="WARN", lookback_s=120)` to corroborate the destination. `get_deploy_history(lookback_s=3600)` provides recent Created and StartedAt fields plus the action journal; it is not a complete Docker event history.

## How to confirm
Match the caller's failing destination to a fresh non-running container observation. Name the unavailable callee as the component, even when the alert belongs to its caller. An exited backing cache is category container_down; dependency propagation describes impact, not a different proven cause.

## Allowed remediation
Propose Action API `restart_service` with `service=<down component>`, after the policy checks target and risk. Obtain a dry run and human approval. Stateful dependencies need review of persistence and interruption risk before any restart is approved.

## Rollback
A restart has no inverse that restores prior process state. If it fails to recover the original symptoms, stop repeated changes and escalate with verification observations.

## Verification criteria
Require the component to be running and servicing fresh calls, its callers to recover, and the original alert predicates to pass in the response verifier's qualified window. Missing metrics never establish recovery.

## Prevention
Alert on service availability with caller-side request checks as well as process state. Retain lifecycle observations for comparison over time.

## Known pitfalls
A healthy target with a wrong caller destination is not a stopped service. Restarting a caller whose dependency is down does not fix that dependency and may create a startup loop.
