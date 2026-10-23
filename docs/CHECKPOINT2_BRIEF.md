# Checkpoint 2 brief: three incidents we chose, what we tell the mentor, what the agent must show

Format agreed with the mentor: we pick three practice incidents from the slide, explain the problem, the objective and the expected result, then run the agent live and it must produce that result. One page per incident, read aloud in under a minute each. Fill the run ids after the rehearsal.

## Why these three
They cover an application fault, a stopped application container, and a stopped dependency container. They also exercise different evidence paths: traces plus logs, container state plus upstream errors, and errors that point past their emitting service to a dependency. **All three expected proposals are tier 2**: payment is critical, and every restart requires tier 2 review. The CPU backup demonstrates tier 3 abstention. These are expected diagnoses and proposals; this session does not execute or demonstrate recovery through the Action API.

Run the three cases in the order below and require three consecutive correct live diagnoses for each before moving to the CPU backup and remaining practice incidents. Each run uses a fresh bundle. Do not fill the rehearsal entries from unit tests or from an injection read-back alone.

The one-command sequence is `scripts/checkpoint2.ps1 <incident>`: reset, verify clean telemetry, inject, wait up to 90 seconds for an alert, diagnose, validate, print the report, reset and verify clean telemetry again. It prints elapsed seconds per stage. Reset clearance takes at least 180 seconds, sampled every 30 seconds. An under-90-second diagnosis is a presentation target, not a result to assert before measurement.

## 1. `payment-failure` (the payment service fails when charging)

- **Problem.** Checkout calls the payment service to charge the card; the charge fails for every order. Customers cannot complete purchases. Nothing is down, so a container check alone finds nothing.
- **Objective.** From a payment or checkout error alert, name `payment`, classify an application fault, and support it with failed charge spans and the payment service's own failure logs. Use the actual returned values and severity; this SDK may log payment failures at WARN.
- **Expected result.** `root_cause.component = payment`, `category = application_flag`, final confidence at least 0.75, at least two supporting sources, and a `toggle_flag` proposal targeting `payment` with the reason "disable the failure switch for payment". Impact tier 2 and status `diagnosed`. The proposed reversible switch changes application behavior; it does not retry charges or modify payment records. Payment criticality requires full evidence and explicit typed yes in the later Action API session. Any proposal carrying actual payment-data risk would instead be tier 3 with no action.
- **What the agent must not do.** Cite any feature-flag name (the redaction layer removes them from spans, events and the payment service's log line), or propose a restart (nothing is down).
- Command: `scripts/checkpoint2.ps1 payment-failure`
- Rehearsal 1 (r4) run id: `runs/20261023T112549.360906Z-ac1d2bef`; report: [payment-failure-r4](../reports/payment-failure-r4/report.json)
- Rehearsal 2 (r5) run id: `runs/20261023T113346.104216Z-514905da`; report: [payment-failure-r5](../reports/payment-failure-r5/report.json)
- Rehearsal 3 (r6) run id: `runs/20261023T114143.041886Z-68a917d4`; report: [payment-failure-r6](../reports/payment-failure-r6/report.json)
- Verified: three consecutive complete rehearsals passed. Each diagnosed `payment` / `application_flag` at 0.90 confidence with three tool calls and the expected tier-2 proposal; diagnosis times were 57.015, 58.375 and 57.828 seconds. Both telemetry-clearance windows passed in every run.

## 2. `container-stopped --svc recommendation` (a service container is stopped)

- **Problem.** The recommendation container is stopped. Requests to that component fail and the recommendations journey degrades while other shopping functions may remain available. Its container still exists with an exited state.
- **Objective.** From the alert on the frontend's error rate or on container health, the agent must look past the frontend (where the errors appear) to the component that is actually missing, and prove it with container state, not just with upstream errors.
- **Expected result.** `component = recommendation`, `category = container_down`, final confidence at least 0.75, container evidence (`Status = exited`) plus upstream failed calls, and a `restart_service` proposal targeting `recommendation`. Impact tier **2**, status `diagnosed`: the component is auxiliary, but a process restart always needs full evidence and explicit typed yes. It is self-healing rather than an instant reversible switch, so it does not qualify for tier 1.
- **What the agent must not do.** Blame the frontend, or stop at "errors on frontend" without the container evidence.
- Command: `scripts/checkpoint2.ps1 container-stopped -Service recommendation`
- Rehearsal 1 (r1) run id: `runs/20261023T114929.814263Z-8fd5a8fd`; report: [container-stopped-r1](../reports/container-stopped-r1/report.json)
- Rehearsal 2 (r2) run id: `runs/20261023T115651.341545Z-14d550d5`; report: [container-stopped-r2](../reports/container-stopped-r2/report.json)
- Rehearsal 3 (r3) run id: `runs/20261023T120358.826377Z-c84200c3`; report: [container-stopped-r3](../reports/container-stopped-r3/report.json)
- Verified: three consecutive complete rehearsals passed. Each diagnosed `recommendation` / `container_down` with the expected tier-2 restart proposal. Confidence was 0.85, 0.90 and 0.90; diagnosis times were 56.969, 42.734 and 93.500 seconds. **r3 missed the 90-second presentation target**, while diagnosis, validation and both telemetry-clearance windows passed.

## 3. `cache-unavailable` (the cache becomes unavailable)

- **Problem.** The cart's cache (`valkey-cart`) is stopped while cart remains running. Cart operations fail with dependency connection errors, affecting the cart and checkout journeys. The demonstration does not infer a distinct-user count from span rates.
- **Objective.** The agent must distinguish the symptom owner (cart, which emits the errors) from the root cause (its dependency, which is down), using the cart service's error messages and the container state of `valkey-cart`.
- **Expected result.** `component = valkey-cart`, cart among the explained symptoms, `category = container_down`, final confidence at least 0.75, and evidence joining cart connection failures with the dependency's exited state. Propose `restart_service` on `valkey-cart`, tier 2, status `diagnosed`. Starting an already stopped dependency adds no discard of live cache state; it can restore availability but cannot promise recovery of previously lost contents. Restarting a live stateful cache, conflicting lifecycle evidence, or another identified state-data risk would require tier 3 and no proposal.
- **What the agent must not do.** Propose restarting `cart` (it is healthy), or report two unrelated causes.
- Command: `scripts/checkpoint2.ps1 cache-unavailable`
- Cache r1: `runs/20261023T121227.303255Z-dc304b61`; [report](../reports/cache-unavailable-r1/report.json), needs_human, confidence 0.55, 12 tool calls.
- Cache r2: `runs/20261023T122840.338357Z-47ea815f`; [report](../reports/cache-unavailable-r2/report.json), needs_human, confidence 0.55, 6 tool calls.
- Neither passed acceptance. A stopped backing container is a container_down cause; dependency unavailability is demonstrated by valkey-cart as component and cart as symptom owner. New scoring requires independent runtime state plus caller connection failures; missing corroboration still escalates.

## Backup incident if one of the three misbehaves on the day
`cpu-starve --svc recommendation`: a reduced CPU quota with whatever latency or saturation symptoms are actually measured. Do not claim that errors are absent or that latency rose without evidence. Expected component `recommendation`, category `resource_starvation`, status `needs_human`, impact tier 3, `proposed_action = null` and `proposed_actions = []`, with a resource-investigation runbook. No allowlisted action restores a CPU limit. This demonstrates the valid abstain path.

- Command: `scripts/checkpoint2.ps1 cpu-starve -Service recommendation`
- Run id: `<fill>`; report: `<fill>`

## The sentence that frames all three
"The agent reads traces, metrics, logs and container state, without reading failure settings. Its claims cite evidence that can be re-fetched or checked against retained snapshots. This checkpoint diagnoses and proposes; the later Action API session adds human approval, execution and measured recovery."
