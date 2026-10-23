# Checkpoint answers

Five things the presenter says at each checkpoint, each with the evidence to point at. Commands are PowerShell from the repo root. Fill every `<run id>` from a real run before the checkpoint; if a line cannot be backed by a run, say so instead of saying the line.

## Checkpoint 1: Eyes (10)

1. "We run the official demo 2.0.2 in minimal mode, unmodified, as a sibling folder."
   Evidence: `faultctl status` all checks pass; after `faultctl reset`, `git -C ..\opentelemetry-demo status --short` prints nothing.
2. "We inject a practice incident and reset it with a read-back."
   Evidence: `faultctl inject payment-failure`, then `faultctl reset` exits 0 and prints each read-back. Run id: `<run id>`.
3. "The agent sees through five read-only tools, and every result carries evidence ids."
   Evidence: `python -m tools.cli health_table`; `python -m tools.cli get_traces checkout`; the `evidence_ids` field in each output.
4. "Here it summarises the symptoms of one live incident by calling tools one at a time."
   Evidence: `reports\<report>.md`, sections Symptoms and Investigation. Run id: `<run id>`.
5. "This is our one-page architecture."
   Evidence: `docs\ARCHITECTURE.md`.

## Checkpoint 2: Brain (20)

1. "Each report names the component, the cause, a category and a confidence, in our schema."
   Evidence: `python -m schema.validate reports\*.json` exits 0; open `reports\<report>.json`, field `root_cause`.
2. "The evidence exists. Point at any id and we fetch it again."
   Evidence: `python -m tools.resolve "<id the mentor picks>"`; for a trace, open it in Jaeger at `http://localhost:8080/jaeger/ui/`.
3. "It chooses its next tool from what it found, and writes down why."
   Evidence: the `investigation` table, column `why`, in `reports\<report>.md`; `runs\<ts>\llm.jsonl` shows one tool call per turn.
4. "It stops at 0.75 with two independent sources. Below 0.6 it escalates with its findings."
   Evidence: the evidence table of a `diagnosed` report shows two sources; the no-fault run `reports\<no-fault report>.md` is `needs_human` or produced no alert.
5. "On the mentor's three incidents:" `<incident 1>`: `<component, confidence>`, `<incident 2>`: `<...>`, `<incident 3>`: `<...>`. "Across all ten, `<n>`/10 correct."
   Evidence: run ids `<run id 1>`, `<run id 2>`, `<run id 3>`; `docs\EVALUATION_NOTE.md`.

## Checkpoint 3: Hands (20)

1. "The agent can only act through the Action API: restart, toggle a flag, throttle load. Scale answers `not_available_on_compose`."
   Evidence: `curl.exe -s localhost:8787/actions`; `Select-String -Path agent\*.py,tools\*.py,detect\*.py -Pattern 'docker (stop|start|restart|update|rm|kill)'` prints nothing.
2. "Before approval we show a dry run; only a human yes produces a token, and the token is tied to the world state."
   Evidence: `python -m agent.respond --report reports\<report>.json` shows the plan and waits; `pytest -q tests\test_action_api.py` (403 without a token, 409 after the world changed).
3. "Here is one full run from alert to verified recovery."
   Evidence: report `reports\<report>.md` with status `fixed`, verification before `<x>` and after `<y>`. Run id: `<run id>`.
4. "Every call is in the action log."
   Evidence: `Get-Content action_api\log.jsonl -Tail 10`, lines `<n>` to `<m>` for that run.
5. "STOP halts everything, and a failed fix rolls back."
   Evidence: live `curl.exe -s -X POST localhost:8787/stop` during `agent.run` gives `aborted`; the rollback test, and `reports\<rolled back report>.md` if we have one. Run id: `<run id>`.

## Checkpoint 4: Hidden test (30)

1. "Our agent starts from an alert on telemetry, so it does not care who injected the fault."
   Evidence: `detect\thresholds.yaml`; `python -m detect.once` after a fault injected by hand (`docker stop <svc>`).
2. "To run us on an unseen incident: start the watcher; each alert produces a report."
   Evidence: `python -m detect.watch --interval 10 --thresholds detect/thresholds.yaml`; reports land in `reports\` as `.json` and `.md`. On demand: `python -m agent.run --alert <alert.json> --out reports\<name>.json`.
3. "It never reads flags, and it never sees our practice answers."
   Evidence: `pytest -q tests\test_no_flag_reads.py tests\test_agent_isolation.py`; the validator rejects any report that mentions flagd.
4. "It covers infrastructure faults and two-fault combinations, and lists an alternative when there may be two causes."
   Evidence: the combinations table in `docs\EVALUATION_NOTE.md` (`<c>`/6); `root_cause.alternatives_considered` in `reports\<combo report>.json`.
5. "When it is not sure, it says so and hands over its findings."
   Evidence: `status: needs_human` and `escalation_note` in `reports\<escalated report>.md`.

## Judges (20): one line per criterion

1. **Safety and human approval:** "Nothing changes without a token from a human yes, tied to the world state, with a dry run first and a STOP that a person must clear."
   Evidence: the live demo; `pytest -q tests\test_action_api.py`; `docs\WHY.md` items 1 to 10.
2. **Agent design and tool use:** "One tool per step with a reason, a health table first, capped results, two independent sources before it stops."
   Evidence: `docs\ARCHITECTURE.md`; the `investigation` table of any report.
3. **Explainability:** "Every claim cites an id you can fetch again, and every step says why it was taken."
   Evidence: `python -m tools.resolve "<id>"` on any report; `tests\test_planted_evidence.py`.
4. **Testing and honesty:** "We scored ourselves on all ten practice incidents and six combinations, and we list what failed."
   Evidence: `pytest -q` (`<n>` passed); `docs\EVALUATION_NOTE.md`, sections Practice incidents and What does not work.
5. **Demo:** "Inject, alert, diagnosis, rejection, approval, recovery, STOP, in five minutes, live."
   Evidence: `docs\DEMO_SCRIPT.md`; rehearsal times `<time 1>`, `<time 2>`.
