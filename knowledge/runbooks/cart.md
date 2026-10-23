---
id: cart
applies_to: [cart]
category: service
version: 1
action_types: [toggle_flag, restart_service]
---
# Cart RPC failures

## Symptoms
GetCart, AddItem or EmptyCart errors can affect frontend cart routes and order preparation. An isolated cleanup failure may occur after an otherwise successful checkout.

## What to check first
Use `get_traces(service="cart", errors_only=True, lookback_s=120)` to group failures by method. Check `get_container_health(names=["cart", "valkey-cart"])` and `get_logs(service="cart", severity_min="INFO", lookback_s=120)`. Use `get_metrics(promql="error_rate_by_service", lookback_s=300)` to measure the affected service interval.

## How to confirm
Compare failed methods with fresh successful methods. EmptyCart-only errors while GetCart and AddItem succeed suggest an application-specific path. Broad storage failures with unavailable valkey-cart point to the cache runbook; inspect the cache before assigning the cause to cart. A cart startup loop can be a consequence of cache loss.

## Allowed remediation
A proved local cart application fault can propose Action API `toggle_flag` with `service=cart`; a stopped cart with healthy dependencies can propose `restart_service`. A cache outage targets the cache under its own risk review. Policy, dry run and explicit human approval remain mandatory.

## Rollback
The Action API conditionally restores a previous application setting if safe. Restart cannot recover prior process state. Escalate failure and preserve observed cart-state risks.

## Verification criteria
Exercise the originally failing cart operation through fresh traces, confirm dependency availability and recover the initial cart/frontend signal with qualified traffic. Successful order completion alone does not prove EmptyCart recovered.

## Prevention
Monitor cart methods separately and correlate dependency connection events. Review startup behavior when the backing cache is unavailable.

## Known pitfalls
Shared storage-error wording cannot distinguish a local application path from real cache loss. Logs at INFO may carry the useful connection events; an empty WARN-only query does not rule out an outage.
