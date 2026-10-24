---
id: checkout
applies_to: [checkout]
category: service
version: 1
action_types: [toggle_flag, restart_service]
---
# Checkout order orchestration

## Symptoms
PlaceOrder fails or becomes slow, often wrapping cart, product-catalog, payment, currency or shipping errors. A checkout failure can produce a frontend POST /api/checkout error.

## What to check first
Use `get_traces(service="checkout", errors_only=True, lookback_s=120)` to inspect the full failing dependency path. Use `get_logs(service="checkout", severity_min="WARN", lookback_s=120)` and `get_container_health(names=["checkout", <failing dependency>])` for corroboration. `get_metrics(promql="error_rate_by_service", lookback_s=300)` shows impact but does not locate the origin by itself.

## How to confirm
A payment server-owned exception points to payment; a cart retrieval failure with cache loss points to valkey-cart. If a Charge client span has no payment server child, inspect payment's state and the caller's peer identity. A healthy payment container with an unrelated destination suggests a caller-routing problem; absent server spans alone do not prove it. Check whether PlaceOrder actually failed when only the cleanup EmptyCart operation errors.

## Allowed remediation
For a proved local checkout application fault, propose Action API `toggle_flag` with `service=checkout`; for a stopped checkout, propose `restart_service`. A proved dependency failure uses that dependency's runbook. Policy checks, dry run and explicit approval apply before any action.

## Rollback
Use conditional Action API rollback for a setting change. Restart cannot restore process state. Failed verification escalates; never repeat a customer charge to demonstrate recovery without understanding the request semantics.

## Verification criteria
Require fresh successful order traces through the originally failing stage and recovery of the frontend checkout signal with qualified traffic. Do not infer successful payment or shipping solely from a healthy checkout container.

## Prevention
Track each order stage and its failure origin. Review timeout behavior and preserve trace links across downstream operations.

## Known pitfalls
Checkout may ignore a cart-cleanup error after charging and shipping, so that trace is not necessarily a failed order. Full deployment can publish to an event queue; the service catalogue's startup dependencies do not prove every request uses it.
