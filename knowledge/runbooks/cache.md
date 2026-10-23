---
id: cache
applies_to: [valkey-cart, cart, checkout]
category: dependency_unavailable
version: 1
action_types: [restart_service]
---
# Cart cache: connection refused and storage errors

## Symptoms
Cart errors with connection refused, RedisConnectionException, "Can't access cart storage" or "Wasn't able to connect to redis" can indicate an unavailable valkey-cart cache. GetCart, AddItem and EmptyCart can all fail; checkout then cannot obtain the cart. A paused or stalled cache may first produce timeouts. The cache holds cart state.

## What to check first
For cart errors and connection refused, call `get_container_health(names=["valkey-cart", "cart"])` before choosing a cart remedy. Use `get_traces(service="cart", errors_only=True, lookback_s=120)` to compare failed operations, and `get_logs(service="cart", severity_min="INFO", lookback_s=120)` for connection/disconnect events. Inspect `get_metrics(promql="error_rate_by_service", lookback_s=300)` for propagation into checkout and frontend.

## How to confirm
Correlate fresh cart connection errors with cache container state. A non-running valkey-cart plus failed cart requests establishes the cache as component and container_down as category. When state is inconclusive, retain dependency_unavailable with appropriate uncertainty. Failures limited to EmptyCart while GetCart and AddItem succeed suggest an application path rather than whole-cache loss. "Connection failed. Disposing the object" supports a real store disconnect when corroborated.

## Allowed remediation
If the cache is proved unavailable and policy permits the stateful operation, propose Action API `restart_service` with `service=valkey-cart`. Review possible cart-data loss, persistence, the dry run and explicit human approval. A risk escalation takes precedence. Restarting cart while its cache is still unavailable can worsen the outage.

## Rollback
A cache restart cannot restore prior in-memory cart state or process state. If recovery fails or data risk is unacceptable, escalate instead of repeatedly restarting it or its callers.

## Verification criteria
Observe fresh successful GetCart and AddItem calls, a stable running cache, and recovery of the original cart/checkout errors under qualified traffic. "Connection to redis was restored successfully" is useful corroboration, but a log line alone does not verify request recovery.

## Prevention
Monitor cache availability and caller connection errors together. Review cache persistence, startup dependency behavior and the risk of losing cart contents.

## Known pitfalls
The same storage-error wording appears in an application-specific cart failure. An unavailable cache can also make cart crash-loop on startup. Name the deepest proved unavailable component, and preserve any independent cart exception as a separate possibility.
