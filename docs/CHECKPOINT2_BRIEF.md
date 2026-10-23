# Checkpoint 2 brief: three incidents we chose, what we tell the mentor, what the agent must show

Format agreed with the mentor: we pick three practice incidents from the slide, explain the problem, the objective and the expected result, then run the agent live and it must produce that result. One page per incident, read aloud in under a minute each. Fill the run ids after the rehearsal.

## Why these three
They cover three different cause categories (an application failure switch, a container that is down, a dependency that is unavailable), three different evidence paths (traces plus logs, container state plus upstream errors, upstream errors that point past the failing service to its dependency), and three different risk tiers, so the mentor sees the taxonomy, the evidence rule and the approval policy in one sitting. All three recover with an allowlisted action.

## 1. `payment-failure` (the payment service fails when charging)

- **Problem.** Checkout calls the payment service to charge the card; the charge fails for every order. Customers cannot complete purchases. Nothing is down, so a container check alone finds nothing.
- **Objective.** From the alert on checkout's error rate, the agent must name `payment` as the failing component, classify it as an application fault, and support it with error spans from checkout to payment and the payment service's own error log lines, with the exact values.
- **Expected result.** `root_cause.component = payment`, `category = application_flag`, confidence at or above 0.75, at least two evidence sources (traces and logs; metrics show checkout and payment error rate above zero), proposed action `toggle_flag` on target `payment` with a reason, impact tier 2 (payment is on the revenue path), status `diagnosed`. Time to diagnosis under 90 s.
- **What the agent must not do.** Cite any feature-flag name (the redaction layer removes them from spans, events and the payment service's log line), or propose a restart (nothing is down).
- Run id: `<fill>` · report: `reports/payment-failure/report.md`

## 2. `container-stopped --svc recommendation` (a service container is stopped)

- **Problem.** The recommendation container is gone. The home page and product pages still load, but every call from the frontend to recommendations fails, so the page is degraded and error counts climb on the frontend.
- **Objective.** From the alert on the frontend's error rate or on container health, the agent must look past the frontend (where the errors appear) to the component that is actually missing, and prove it with container state, not just with upstream errors.
- **Expected result.** `component = recommendation`, `category = container_down`, confidence at or above 0.75, evidence from `get_container_health` (`State.Status = exited`) plus frontend error spans or logs mentioning the recommendation call, proposed action `restart_service` on `recommendation`, impact tier 1 (an auxiliary service, a self-healing action), status `diagnosed`.
- **What the agent must not do.** Blame the frontend, or stop at "errors on frontend" without the container evidence.
- Run id: `<fill>` · report: `reports/container-stopped-recommendation/report.md`

## 3. `cache-unavailable` (the cache becomes unavailable)

- **Problem.** The cart's cache (`valkey-cart`) is stopped. The cart service is still running but every cart read and write fails with a connection error, so adding to cart and checkout break for everyone.
- **Objective.** The agent must distinguish the symptom owner (cart, which emits the errors) from the root cause (its dependency, which is down), using the cart service's error messages and the container state of `valkey-cart`.
- **Expected result.** `component = valkey-cart` with `cart` named in the symptoms and alternatives, `category = dependency_unavailable`, confidence at or above 0.75, evidence: cart error spans or log lines naming the connection failure, `valkey-cart` container `exited`, cart and frontend error rate above zero; proposed action `restart_service` on `valkey-cart`, impact tier 2 (cart is on the revenue path), status `diagnosed`.
- **What the agent must not do.** Propose restarting `cart` (it is healthy), or report two unrelated causes.
- Run id: `<fill>` · report: `reports/cache-unavailable/report.md`

## Backup incident if one of the three misbehaves on the day
`cpu-starve --svc recommendation` (resource starvation: p95 latency up on recommendation, container CPU pinned at its new limit, no errors). Expected `category = resource_starvation`, action `none` with escalation (nothing on the allowlist lifts a CPU limit), impact tier 3. It shows the abstain path, which the slide says scores better than a confident wrong fix.

## The sentence that frames all three
"The agent only reads telemetry: traces, metrics, logs and container state. It never reads the failure switches. Every claim in its report points at an evidence id you can resolve live. It proposes, we approve."
