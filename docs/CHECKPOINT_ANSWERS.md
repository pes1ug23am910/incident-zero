# Checkpoint answers and evidence

These are presenter answers supported by retained runs or commands. Historical
bundles are recordings, not evidence that the current demo line has passed. Fresh
demo-stable results and its deliberate exclusions are in [BUILD_09](../BUILD_09.md). Run commands
with the installed Python environment; only the stack owner may run rehearsals.

**24 October demo-stable:** fresh retained runs are below; knowledge demo default **OFF**, provisional and not freshly validated. See [BUILD_09](../BUILD_09.md) for failed preparations, complete wrapper times, cleanup and uncompleted checks. Checkpoint 3 and typed CLI/live approval were not exercised in this session.

| Fresh bundle | Diagnosis run ID | Result |
|---|---|---|
| [stable09-payment-on-r2](../reports/stable09-payment-on-r2/report.json) | `runs/20261024T020607.182583Z-3fd181d4` | diagnosed; 0.90; 56.851 s agent |
| [stable09-payment-on-r4](../reports/stable09-payment-on-r4/report.json) | `runs/20261024T022402.665842Z-6bf15653` | diagnosed; 0.95; 38.891 s agent |
| [stable09-recommendation-on-r1](../reports/stable09-recommendation-on-r1/report.json) | `runs/20261024T023315.758052Z-0903788b` | diagnosed; 0.80; 56.537 s agent |
| [stable09-recommendation-on-r2](../reports/stable09-recommendation-on-r2/report.json) | `runs/20261024T024152.039733Z-dc7d26df` | diagnosed; 0.90; 172.794 s agent |

## Checkpoint 1: Eyes (10)

1. **What are you running?** The official 2.0.2 minimal demo, with a team-owned
   injection overlay. `python -m faultctl status` and `git -C ../opentelemetry-demo
   status --short` check it. [BUILD_01B](../BUILD_01B.md) records 21 containers and
   clean source status; tonight's read-only preflight also saw 21 running.
2. **Can you inject and reset?** The historical payment rehearsal
   [payment-failure-r6](../reports/payment-failure-r6/checkpoint2.json) records
   operator reset/injection/cleanup. Its run is
   `runs/20261023T114143.041886Z-68a917d4`. Fresh injection and reset records are linked in the table above.
3. **What can the agent read?** Metrics, traces, logs, container health and action
   history. `python -m tools.cli --help` lists the tools; the five calls passed
   the under-five-second checks in the read-only preflight.
4. **Does it explain the symptoms?** Open the investigation table in
   [payment-failure-r6](../reports/payment-failure-r6/report.md): three tool calls,
   payment application cause, historical confidence 0.90. Each row gives a reason.
5. **Where is the architecture?** [ARCHITECTURE.md](ARCHITECTURE.md) shows the tool,
   graph, checkpoint, approval and verification boundaries with current status.

## Checkpoint 2: Brain (20)

1. **What does it output?** Component, category, confidence, evidence, proposal and
   limitations. Run `python -m schema.validate "reports/*/report.json"` to check
   retained bundles; the organiser's final schema is not verified.
2. **Is the evidence real?** Choose an ID from `payment-failure-r6/report.json` and
   run `python -m tools.resolve "ID" --bundle-dir reports/payment-failure-r6`.
   The resolver labels live versus retained-snapshot resolution. Tonight's
   preflight round-tripped a newly observed container ID live.
3. **How does it choose a tool?** A structured model call chooses one next read,
   with a reason. The run's `llm.jsonl` and report investigation table show this.
   Code validates provenance, coverage, risk and the final action labels.
4. **What does confidence mean?** A heuristic capped by evidence support, not a
   calibrated probability. Historical scoring incorrectly counted spanmetrics
   independently of traces; the fold must rerun after correcting that.
5. **What happened on three cases?** Payment r6 named payment/application_flag at
   0.90; recommendation r3 named recommendation/container_down at 0.90
   (`runs/20261023T120358.826377Z-c84200c3`); cache r2 named valkey-cart/container_down
   at 0.55 and escalated (`runs/20261023T122840.338357Z-47ea815f`). The third was not
   a confident diagnosis pass. All-ten accuracy is not verified.

## Checkpoint 3: Hands (20)

1. **What can it change?** Only Action API allowlisted restart, toggle or throttle.
   `python -m action_api --help` exposes the boundary; Compose scaling is unavailable.
2. **Where is approval?** A dry run precedes a bound, expiring, single-use token.
   `scripts/checkpoint3.ps1 payment-failure` or
   `bash scripts/checkpoint3.sh payment-failure` waits for a real decision. Historical
   test and browser automation are disclosed, not presented as human approval.
3. **Has a loop recovered?** [payment-failure-loop-r3](../reports/payment-failure-loop-r3/report.json),
   `runs/20261023T153512.976354Z-13778fd2`, records a real toggle and recovery after
   test-harness approval. [container-stopped-loop-r1](../reports/container-stopped-loop-r1/report.json),
   `runs/20261023T160004.705486Z-ad2f6cb4`, records a restart. Human-approved reruns
   are scheduled, not verified.
4. **Can rejection avoid mutation?** [payment-failure-loop-r4](../reports/payment-failure-loop-r4/hands-rehearsal.json)
   records matching before/after world hashes and no execute event. It used
   `--reject`; it is not evidence of a person typing no.
5. **What do STOP and rollback prove?** [payment-failure-loop-r5](../reports/payment-failure-loop-r5/report.json)
   aborted verification after execution; STOP cannot undo that completed toggle.
   [r8](../reports/payment-failure-loop-r8/report.json) rolled back on lost traffic,
   which the hands audit rejects as the target policy. Unknown verification must
   now escalate without automatic rollback; that live fix is not verified here.

## Checkpoint 4: Hidden test (30)

1. **Can someone else inject?** Detection uses telemetry. Start
   `python -m detect.watch --interval 10`; the diagnosis does not require faultctl
   ground truth. The unseen-incident interface is still for the mentor to confirm.
2. **How are unseen faults entered?** [FAULTCTL.md](FAULTCTL.md) lists existing
   practice aliases and the generic grammar the fold must provide. Do not claim
   arbitrary two-target combinations are tested until a retained run proves it.
3. **How do you guard against reading the answers?** Run
   `python -m pytest -q tests/test_no_flag_reads.py tests/test_agent_isolation.py
   --basetemp=.build/pytest`. Flag disclosure is rejected. The operator-only
   readiness manifest has an exact-path exemption; diagnostic scanning and
   import-isolation tests remain enabled and pass on demo-stable.
4. **Do combinations work?** This snapshot escalates independent causes at tier 3
   with no actions. The fold contract requires separately risked proposals for
   supported pairs, while unsupported or incompletely covered combinations still
   escalate. Six held-out rehearsals and their accuracy are not verified.
5. **What if it cannot decide?** It must return `needs_human` with findings and
   limitations. The cache r1/r2 reports demonstrate escalation. Empty telemetry
   must not be called healthy; outage and no-traffic distinctions remain xfails.

## Three statements to the mentor before hidden testing

1. Our trace tools discover Jaeger's published port before trying the proxy.
   Read-only discovery worked here; proxy-down live failover has not been rehearsed
   by this session. `test_jaeger_proxy_only_is_usable` is an offline regression.
2. Missing telemetry is not proof of health. This snapshot lacks a dedicated
   outage alert and treats a stopped load generator as an application fault. We
   will disclose whether the fold's outage/no-traffic distinction passes its tests.
3. Independent causes currently escalate at tier 3 with no actions. Please confirm
   schema, component/category conventions, multiple-cause export and abstention
   scoring. Cache naming, image faults, misrouted calls and flood naming are not
   defined by another benchmark's conventions.

The six knowledge questions and the mentor's three-layer answer are in
[KNOWLEDGE.md](KNOWLEDGE.md): store versus RAG, why retrieve, practice-answer
leakage, wrong hints, measured benefit, and poisoning. The live wrong-hint demo
and nine-run ablation remain not verified.

For judges: show the evidence/action log, the actual approval surface, the
failed rows in [EVALUATION_NOTE.md](EVALUATION_NOTE.md), and the timed preparation
boundary in [DEMO_SCRIPT.md](DEMO_SCRIPT.md). Do not claim a 10/10 score, calibrated
confidence, human approval or a completed five-minute rehearsal without evidence.
