# Checkpoint 2 brief: three incidents we chose, what we tell the mentor, what the agent must show

Format agreed with the mentor: we pick three practice incidents from the slide, explain the problem, the objective and the expected result, then run the agent live and it must produce that result. The retained diagnosis runs below are historical evidence. The integration round adds the separate full-loop command `scripts/checkpoint3.ps1 <incident>`; measured recovery and approval paths belong in [EVALUATION_NOTE.md](EVALUATION_NOTE.md).

**24 October demo-stable:** fresh runs have not started because readiness is
blocked by the occupied UI port and low free RAM. No fresh run IDs can be listed;
do not present the historical IDs below as this branch's acceptance. Source/tests
and exact morning commands are in [BUILD_09](../BUILD_09.md).

## Why these three
They cover an application fault, a stopped application container, and a stopped dependency container. They also exercise different evidence paths: traces plus logs, container state plus upstream errors, and errors that point past their emitting service to a dependency. **All three expected proposals are tier 2**: payment is critical, and every restart requires tier 2 review. The CPU backup is intended to demonstrate tier 3 abstention; it has not been rehearsed live. Checkpoint 2 runs diagnose and propose; Checkpoint 3 uses the integrated Action API to collect approval, execute and verify.

For demo-stable, run payment twice, stopped recommendation twice, and cache once.
Payment and recommendation require confidence >=0.75, status `diagnosed`, and
agent time below 120 seconds. Retry a failed core case once, then test knowledge
off if the retry fails. Cache is allowed to be intermittent and must be disclosed.
Each attempt uses a fresh bundle; unit tests cannot fill the live table.

The one-command sequence is `scripts/checkpoint2.ps1 <incident>` (bash twin available): preflight, reset, verify clean telemetry, inject, wait for an alert, diagnose, validate, print, reset and verify clean telemetry. Wrappers request a 150-second alert budget; the current watcher still caps it at 90 seconds (strict regression xfail). Reset clearance takes at least 180 seconds, sampled every 30 seconds. The fresh demo-stable table is in [BUILD_09](../BUILD_09.md); older results below remain historical. Approval modes and rollback limitations are qualified in [EVALUATION_NOTE.md](EVALUATION_NOTE.md).

## 1. `payment-failure` (the payment service fails when charging)

- **Problem.** Checkout calls the payment service to charge the card; the charge fails for every order. Customers cannot complete purchases. Nothing is down, so a container check alone finds nothing.
- **Objective.** From a payment or checkout error alert, name `payment`, classify an application fault, and support it with failed charge spans and the payment service's own failure logs. Use the actual returned values and severity; this SDK may log payment failures at WARN.
- **Expected result.** `root_cause.component = payment`, `category = application_flag`, final confidence at least 0.75, at least two supporting sources, and a `toggle_flag` proposal targeting `payment` with the reason "disable the failure switch for payment". Impact tier 2 and status `diagnosed`. The proposed reversible switch changes application behavior; it does not retry charges or modify payment records. Payment criticality requires full evidence and explicit typed yes through the integrated approval gate. Any proposal carrying actual payment-data risk would instead be tier 3 with no action.
- **What the agent must not do.** Cite any feature-flag name (the redaction layer removes them from spans, events and the payment service's log line), or propose a restart (nothing is down).
- Command: `scripts/checkpoint2.ps1 payment-failure`
- Rehearsal 1 (r4) run id: `runs/20261023T112549.360906Z-ac1d2bef`; report: [payment-failure-r4](../reports/payment-failure-r4/report.json)
- Rehearsal 2 (r5) run id: `runs/20261023T113346.104216Z-514905da`; report: [payment-failure-r5](../reports/payment-failure-r5/report.json)
- Rehearsal 3 (r6) run id: `runs/20261023T114143.041886Z-68a917d4`; report: [payment-failure-r6](../reports/payment-failure-r6/report.json)
- Verified: three consecutive complete rehearsals passed. Each diagnosed `payment` / `application_flag` at 0.90 confidence with three tool calls and the expected tier-2 proposal; diagnosis times were 57.015, 58.375 and 57.828 seconds. Both telemetry-clearance windows passed in every run.
- Integration full loop: [payment-failure-loop-r3](../reports/payment-failure-loop-r3/report.json), run `runs/20261023T153512.976354Z-13778fd2`, reached `fixed` in 346.016 seconds from injection through final validation. Developer acceptance explicitly used test auto-approval; the mentor command uses real typed `yes`. Verification lasted 182.359 seconds with all four alert signals zero on the final two samples, 984.049 measured requests and the load generator running. Before/after clean windows were 184.562/184.375 seconds. Earlier integrated r1 missed the alert deadline; r2 refused a historical traffic-baseline mismatch, both retained in the evaluation ledger.
- Integration rejection: [payment-failure-loop-r4](../reports/payment-failure-loop-r4/report.json), run `runs/20261023T154711.305759Z-b5f7c99e`, recorded explicit CLI rejection with test mode off, `needs_human`, no execution and matching world-state hashes before/after the decision. Operator cleanup verified separately.
- Integration STOP: [payment-failure-loop-r5](../reports/payment-failure-loop-r5/report.json), run `runs/20261023T161808.661278Z-149073c4`, used explicit developer test approval, executed the toggle, then latched STOP 15 seconds after execution began. The report is `aborted`, verification reports `STOP_LATCHED`, and rollback did not run. The response finished 137.438 seconds after injection; no action recovery time is claimed. Before/after operator-clearance windows passed at 184.281/184.719 seconds.
- Integration rollback: [payment-failure-loop-r8](../reports/payment-failure-loop-r8/report.json), run `runs/20261023T165913.243864Z-df3099ba`, used explicit developer test approval and stopped the real Locust swarm. Verification lasted 182.750 seconds, refusing recovery despite positive residual request counts because the swarm was stopped. Actual settings rollback produced `rolled_back`; the complete runner passed, finishing 322.844 seconds after injection, with qualified before/after windows of 184.984/184.093 seconds. This is response completion, not remediation recovery. Earlier r6/r7 acceptance failures remain in the evaluation ledger.
- Integration browser run: [payment-failure-loop-r9](../reports/payment-failure-loop-r9/report.json), run `runs/20261023T171108.246095Z-f4afce0d`, ran the actual Checkpoint 3 wrapper with a waiting terminal and real browser confirmation. Browser automation approved as `Integration acceptance`, with test auto-approval off; it was not a person approving. One action executed and reached `fixed` in 313.078 seconds from injection. Verification lasted 183.500 seconds with both alert values zero, 1260.084/1188.079 measured requests and Locust running. The terminal joined completion and qualified before/after windows passed at 184.047/183.922 seconds.

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
- Integration full loop: [container-stopped-loop-r1](../reports/container-stopped-loop-r1/report.json), run `runs/20261023T160004.705486Z-ad2f6cb4`, reached `fixed` after the actual approved restart in 609.922 seconds from injection. Developer test auto-approval was explicit. The nine-call investigation took 394.157 seconds; this run demonstrates recovery but misses the diagnosis presentation target. Verification lasted 182.000 seconds, with the container running on both final samples, 892.045/1220.081 measured requests and load running. Qualified before/after windows were 184.781/184.656 seconds.

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
- Live run: not performed; no retained report or measured abstention claim.

## The sentence that frames all three
"The agent reads traces, metrics, logs and container state, without reading failure settings. Its claims cite evidence that can be re-fetched or checked against retained snapshots. Diagnosis pauses at a real human gate; the integrated Action API executes an approved plan and claims recovery only after measuring the original signals with sufficient traffic."
