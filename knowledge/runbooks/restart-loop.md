---
id: restart-loop
applies_to: [recommendation, cart, payment, frontend, ad]
category: restart_loop
version: 1
action_types: [restart_service]
---
# Repeated container restarts

## Symptoms
RestartCount increases across observations, StartedAt changes, and callers see intermittent UNAVAILABLE bursts. Application startup logs repeat. Memory exhaustion may precede each process reset.

## What to check first
Compare repeated `get_container_health(names=[<suspect>])` observations. Use `get_logs(service=<suspect>, severity_min="INFO", lookback_s=600)` for startup and failure messages, `get_metrics(promql="container_memory", lookback_s=600)` for memory shape, and `get_deploy_history(lookback_s=3600)` for recent starts. Check caller failures with `get_traces(service=<caller>, errors_only=True, lookback_s=600)`.

## How to confirm
Require a rising restart count or repeated lifecycle reset plus correlated request failures. A single historical RestartCount is not a current loop. Compare memory limit and usage with retained observations, and inspect dependencies before attributing a startup failure to the restarting process.

## Allowed remediation
Action API `restart_service` for the diagnosed component is a possible policy-approved proposal only when the reason a fresh process would help is evidenced. Seek human approval after a dry run. If a dependency outage, persistent configuration problem or resource constraint will immediately recur, escalate instead of repeating restarts.

## Rollback
Restart cannot restore prior process state. A failed restart escalates with the unchanged symptoms; do not enter an automated restart cycle.

## Verification criteria
RestartCount and StartedAt remain stable through the verification window, fresh requests succeed, and all original alert predicates recover under qualified traffic.

## Prevention
Track restart deltas, memory growth and startup dependency errors. Alert before memory headroom is exhausted and retain before/after limits.

## Known pitfalls
The OOMKilled field can clear after a successful restart, so false is not proof that no OOM occurred. A cart startup loop can be downstream of an unavailable cache. Growing recommendation memory with an unchanged limit can indicate application work rather than an infrastructure limit change.
