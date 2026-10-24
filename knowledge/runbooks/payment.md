---
id: payment
applies_to: [payment]
category: service
version: 1
action_types: [toggle_flag, restart_service]
---
# Payment charge failures

## Symptoms
Charge errors propagate through checkout into frontend checkout failures. A service-owned exception can mention an invalid token while CPU and memory remain ordinary. Connection errors without a payment server span require a different investigation.

## What to check first
Read `get_traces(service="payment", errors_only=True, lookback_s=120)` and `get_logs(service="payment", severity_min="WARN", lookback_s=120)` for the originating exception. Read `get_container_health(names=["payment"])` and `get_metrics(promql="error_rate_by_service", lookback_s=300)`. If payment traces are absent, inspect `get_traces(service="checkout", errors_only=True, lookback_s=120)` for the caller's destination.

## How to confirm
A fresh PaymentService/Charge server exception plus independent payment application logs supports a local application fault. The running container is context, not independent evidence of the exception. A stopped payment with caller connection failures supports container_down. A healthy payment with a wrong caller destination may implicate checkout. Compare several requests when errors affect only a fraction of charges.

## Allowed remediation
For a local payment application fault, use the application-fault runbook: propose Action API `toggle_flag` with `service=payment`, disabling the failure switch for payment. For a proved stopped payment, propose `restart_service`. Both require policy/risk review, a dry run and explicit approval; payment is critical.

## Rollback
Use the Action API's conditional prior-setting restoration if a setting change fails verification. A restart has no inverse. Escalate non-recovery and do not fabricate a successful payment.

## Verification criteria
Observe fresh successful Charge server calls, successful affected checkout traces, and recovery of the original error signal across the traffic-qualified verification window. Positive request volume is essential to distinguish recovery from lost traffic.

## Prevention
Monitor transaction outcomes, Charge error ratios and end-to-end checkout. Keep exception provenance so caller wrappers do not hide the origin.

## Known pitfalls
A familiar invalid-token message does not establish how failure was activated. Zero payment traffic may be caused by a caller routing problem or earlier checkout failure. Past payment memory never overrides a different current component's evidence.
