# Demo script: 5 minutes live, 3 minutes of questions

Each member presents the part they built. Commands are PowerShell on the demo laptop, run from the repo root with the venv active. If `faultctl` is not on PATH, use `python -m faultctl`. Fill every `<...>` during the rehearsal, not on stage.

## Before we go on stage (T-10 min)

- [ ] `faultctl reset` exits 0, then `faultctl status` shows every check passing.
- [ ] Action API up: `curl.exe -s http://localhost:8787/health` answers. No `STOP` file in the repo root.
- [ ] Terminal T1 (operator): repo root, font size 18+.
- [ ] Terminal T2 (watcher): `python -m detect.watch --interval 10 --thresholds detect/thresholds.yaml` running, printing `no_alert`.
- [ ] Terminal T3 (action log): `Get-Content action_api\log.jsonl -Wait -Tail 3`.
- [ ] Browser: tab 1 the architecture picture from `docs/ARCHITECTURE.md`, tab 2 Jaeger at `http://localhost:8080/jaeger/ui/`, tab 3 the limitations slide (end of this file).
- [ ] Two full rehearsals today: `<time 1>`, `<time 2>`. Laptop on power, notifications off.

## The five minutes

**0:00-0:15 | M5 | Opening**
- Screen: tab 1, the architecture picture.
- Say: "This is an on-call agent for the OpenTelemetry demo. It investigates with tools, names a cause with evidence, and changes nothing until one of us says yes."

**0:15-0:30 | M3 | Inject**
- Run (T1): `faultctl inject payment-failure`
- Screen: T1 prints the run id.
- Say: "faultctl is our injector. The agent cannot see it or its ground truth file; a test checks that."

**0:30-1:30 | M4 then M1 | Detection and investigation**
- Screen: T2 prints the alert (`error_rate`, service, observed vs threshold), then the agent's steps, one per line: tool, query, why.
- Say (M4, while waiting): "Detection watches error rate, latency and container health in Prometheus and Docker. It knows nothing about flags."
- Say (M1, as steps appear): "First call is always the health table. After that it picks one tool at a time and writes down why. Read the why column."

**1:30-2:15 | M1 then M4 | The report**
- Run: open `reports\<report>.md` (path printed by T2).
- Screen: verdict line (status, component, confidence), the investigation table, the evidence table.
- Run: `python -m tools.resolve "span:<trace>/<span>"`, then open that trace in tab 2.
- Say (M4): "Every id in the report came back from a tool in this run. Here is that span, live in Jaeger. If the model names an id no tool returned, the report is rejected."

**2:15-2:40 | M2 | Rejection**
- Run: `python -m agent.respond --report reports\<report>.json`
- Screen: dry-run plan and predicted effect, then the prompt "Approve? yes/no". Type `no`.
- Screen: report status `needs_human`; T3 shows the rejection line; T2 health row still shows the errors.
- Say: "We said no. Nothing changed. The rejection is in the log and in the report."

**2:40-3:40 | M2 | Approve, act, verify**
- Run: the same `agent.respond` command again. Type `yes`.
- Screen: token issued, `toggle_flag` executed, T3 shows the execute line, then verification: error rate before `<x>` and after `<y>`, status `fixed`.
- Say (during the 30-60 s wait): "The token is tied to a hash of the world when we approved. If a container changed in between, execute answers 409 and asks again. After acting it re-runs the alert's own query; if the system has not recovered in two minutes it rolls back and escalates."

**3:40-4:20 | M2 | STOP**
- Run: `python -m agent.run --alert runs\<ts>\alert.json --out reports\stop-demo.json`
- After the second step appears, run in T1: `curl.exe -s -X POST http://localhost:8787/stop`
- Screen: the agent halts, report status `aborted`, `stopped_because: stop_signal`. Then `faultctl inject cart-intermittent` refuses, and T3 shows the stop line.
- Run: `<clear command with the operator phrase, from README>`
- Say: "One command stops the agent, the executor, the watcher and the injector. Only a person with the phrase can clear it."

**4:20-4:40 | M5 | Proof**
- Run: `python -m schema.validate reports\*.json` then `pytest -q tests\test_no_flag_reads.py tests\test_agent_isolation.py`
- Screen: validator and tests green; `docs/EVALUATION_NOTE.md` table.
- Say: "Every report validates. In our own testing we got `<n>`/10 practice incidents right. The misses and why are in the evaluation note."

**4:40-5:00 | M5 | Limitations slide** (tab 3, below). Read it as written.

## Limitations slide

- We run Docker Compose, so `scale_service` returns `not_available_on_compose`.
- Network and resource-starvation faults: we diagnose and escalate. Nothing on the allowlist fixes them.
- Two faults at once: we report one primary cause and one alternative. A third is missed.
- Practice set: `<n>`/10 correct, `<m>` escalated, `<k>` wrong (`<which>`). Combos: `<c>`/6.
- Confidence is the model's own number, checked against only `<runs>` runs.
- Evidence lifetime: Jaeger keeps 5,000 traces in memory, Prometheus one hour. Older ids stop resolving.
- Approval is one operator on localhost. No login, no second approver.

## Questions (3 min): who answers

| Likely question | Who | Short answer, detail in `docs/WHY.md` |
|---|---|---|
| How do you know it did not read the flags? | M5 | Two tests and the validator; flag code lives in two files. |
| What if the model invents a trace id? | M4 | The builder rejects ids no tool returned. |
| Why not let it act on high confidence? | M2 | Rule 4, and a confident wrong fix scores worse than escalation. |
| What happens on an unseen fault? | M1 | Detection is telemetry-only; low confidence means `needs_human` with findings. |
| What would you change in your part? | each | One honest sentence each, prepared: `<fill per member>` |

## If something fails on stage

| If this fails | Do this | Say this |
|---|---|---|
| No alert after 90 s | Run `python -m detect.once`; if it fires, start `agent.run` by hand on that alert | "The watcher missed a tick; same check, run once." |
| LLM call errors or hangs | The router falls back to Gemini on its own; if both fail, open the rehearsal report `reports\<rehearsal>.md` | "Live model call failed. This is our <time> rehearsal run, recorded, not live." |
| Wrong component or `needs_human` | Show the escalation note; skip to the rejection and STOP parts | "This is the abstain path. It is the correct outcome when evidence is thin." |
| Verification does not recover | Let it roll back; show `rolled_back` | "This is the rollback path, live." |
| Action API not answering | Restart it (README); STOP still works as `New-Item STOP` | "The kill switch is a file too, so it works without the API." |
| `faultctl reset` reports leftovers | Read its list aloud; `docker compose -f docker-compose.minimal.yml up -d` in the demo folder | "Reset tells us what it could not clean. We do not hide it." |
| Laptop freezes | Second laptop with the repo and the rehearsal reports | "Here is the same run from <time>, recorded." |
