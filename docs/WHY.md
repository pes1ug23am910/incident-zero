# Why each control exists

For every safety control and design choice: what it prevents, how you can check it in 30 seconds, and our answer to "why not something simpler". Commands are PowerShell from the repo root. Items marked (planned) are not built yet.

## Safety controls

### 1. The Action API is the only write path, behind an allowlist
- Prevents: the agent running any Docker or shell command it likes against the demo (rule 4).
- Check: `curl.exe -s localhost:8787/actions` lists four actions; `Select-String -Path agent\*.py,tools\*.py,detect\*.py -Pattern 'docker (stop|start|restart|update|rm|kill)'` prints nothing.
- Why not simpler: letting the agent call Docker directly is less code, but then approval is advice, not a gate.

### 2. Nothing executes without a human approval token
- Prevents: any change to the system without an explicit yes (stage 5, rule 4).
- Check: `pytest -q tests\test_action_api.py`; the no-token case returns 403.
- Why not simpler: an `approved: true` field can be set by the same code that asks; a token can only come from the approval step.

### 3. The token is bound to the world state and expires in 10 minutes
- Prevents: approving one system and executing on another (a container recreated, another fix landed in between).
- Check: dry-run, then `docker restart cart`, then execute with the old token: 409.
- Why not simpler: an approval is for one state of the system; a token that outlives that state is a blank cheque.

### 4. Dry run before every approval
- Prevents: a human approving a sentence instead of a concrete plan with a predicted effect.
- Check: the dry-run test compares container ids and the flag-file hash before and after: identical.
- Why not simpler: "restart payment" sounds harmless until the plan shows which container and what it will interrupt.

### 5. STOP is a file and an endpoint, and only a person clears it
- Prevents: a running loop continuing while a person tries to intervene, or clearing its own kill switch.
- Check: `New-Item STOP`, then `faultctl inject cart-intermittent` refuses; `curl.exe -s -X DELETE localhost:8787/stop` without the phrase is refused. `Remove-Item STOP` after.
- Why not simpler: an endpoint alone dies with the API process; a file works even when the API is down, and every component checks it.

### 6. Verify after acting, with the alert's own query
- Prevents: calling an incident fixed because the command returned 0.
- Check: any `fixed` report has `verification.before` and `after`; the validator refuses `fixed` without `recovered: true`.
- Why not simpler: a restart can succeed while the error rate stays at 40 %; we check the signal that raised the alert.

### 7. Roll back and escalate when recovery fails
- Prevents: leaving a fix that did not help in place.
- Check: the forced non-recovery test restores the previous flag variant; the report says `rolled_back`.
- Why not simpler: if our change did not help, the safest state is the one before it, plus a person.

### 8. Append-only action log
- Prevents: changes nobody can reconstruct; it also feeds `get_deploy_history`.
- Check: `Get-Content action_api\log.jsonl -Tail 5`.
- Why not simpler: "what changed recently" is the first question on any incident, including changes we made.

### 9. The test-only approval bypass is opt-in and loud
- Prevents: tests needing a human, and the bypass slipping into a demo.
- Check: `--auto-approve-for-tests` without `INCIDENT_ZERO_TEST=1` refuses; with it, a banner prints.
- Why not simpler: tests need a bypass; making it opt-in and visible keeps it from becoming the default.

### 10. The Action API listens on localhost only
- Prevents: anything else on the venue network calling it (out of scope 5).
- Check: `netstat -ano | findstr 8787` shows only `127.0.0.1`.
- Why not simpler: this is the simple version; one bind address.

## Diagnosis and rule compliance

### 11. No flag reads, enforced by tests
- Prevents: disqualification (rule 6) and an agent that reads the answer instead of reasoning.
- Check: `pytest -q tests\test_no_flag_reads.py tests\test_agent_isolation.py`.
- Why not simpler: trusting ourselves is simpler, but a test fails loudly the moment someone adds a shortcut late at night.

### 12. Flag attributes are stripped from telemetry (planned)
- Prevents: flag keys reaching the model through OpenFeature span attributes and flagd's own metrics.
- Check: `python -m tools.cli get_traces cart` contains no `feature_flag` (planned).
- Why not simpler: the rule bans reading flag settings and these attributes are flag settings; dropping them is cheaper than arguing.

### 13. The prompt never contains incident ids or flag names
- Prevents: matching on names instead of telemetry; hard-coded answers (out of scope 4).
- Check: `Select-String -Path runs\*\llm.jsonl -Pattern 'faultctl|paymentFailure|payment-failure'` prints nothing.
- Why not simpler: giving the model our practice catalogue raises the practice score and lowers the hidden-test score.

### 14. Detection starts from telemetry, not from our injector
- Prevents: an agent that works only with `faultctl`; the hidden test injects its own way.
- Check: `docker stop recommendation` by hand, then `python -m detect.once` fires.
- Why not simpler: having faultctl start the agent is one line and fails the hidden test.

### 15. Every claim cites an evidence id that resolves
- Prevents: invented evidence (penalised in stage 3); the builder rejects ids no tool returned in this run.
- Check: pick any id in any report, `python -m tools.resolve "<id>"`; `pytest -q tests\test_planted_evidence.py`.
- Why not simpler: quoted text can be invented; an id can be fetched again by anyone.

### 16. Below 0.6 confidence the agent escalates instead of acting
- Prevents: a confident wrong fix, which the brief scores below an escalation.
- Check: the validator rejects `confidence < 0.6` with any status but `needs_human`; see the no-fault report.
- Why not simpler: always proposing a fix demos better and scores worse.

### 17. Stop only at 0.75 with two independent sources
- Prevents: stopping on one noisy signal, such as latency that is really load.
- Check: in any `diagnosed` report the evidence table shows at least two different sources.
- Why not simpler: one source always agrees with itself; wrong diagnoses show up where two sources disagree.

### 18. One tool per step, with a reason, health table first, capped output
- Prevents: pasting all telemetry into one prompt (the brief asks for this explicitly), context overflow, cost.
- Check: the `investigation` table of any report; `runs\<ts>\llm.jsonl` has one tool call per turn.
- Why not simpler: one big prompt cannot be explained step by step and breaks as telemetry grows.

### 19. A budget of 12 tool calls
- Prevents: loops that burn the spend limit and miss the 90-second target.
- Check: `agent.tool_calls` is at most 12 in every report; `stopped_because: budget` when it runs out.
- Why not simpler: an unbounded loop is easier to write and impossible to time.

### 20. A strict schema with cross-field rules
- Prevents: reports that parse but lie, such as `fixed` without an approval or a recovery.
- Check: `python -m schema.validate schema\examples\*.json`; the invalid examples exit 1 with the field path.
- Why not simpler: free text is easier to write and cannot be scored automatically.

### 21. The demo stays unmodified; reset restores it byte for byte
- Prevents: tampering (rule 6) and drift between runs.
- Check: after `faultctl reset`, `git -C ..\opentelemetry-demo status --short` prints nothing.
- Why not simpler: vendoring the demo into our repo would make accidental edits easy.

### 22. Temperature 0, a fallback model, and every LLM call logged
- Prevents: runs we cannot repeat or explain, and a dead demo when one provider fails.
- Check: open `runs\<ts>\llm.jsonl`; `agent.model` in each report names the model used.
- Why not simpler: one provider with no log is simpler until it times out on stage.
# Hands boundary (2026-10-23)

Service-to-switch mapping exists only in `action_api/flags.py`. Its configuration
reads are not diagnosis: they retain previous values for rollback and bind
approval to a hash of the actual mounted configuration. The agent receives only
service targets. The executor requires the operator overlay for writes and
never rewrites the official demo checkout. Reads of the baseline for hashing
are permitted when no overlay is mounted.

The weighted impact score adds 20 × uncertainty and 20 × observability gap to
the existing business/reversibility score. These are starting heuristic weights,
not probabilities. Uncertainty is 1 − evidence confidence; observability gap is
the share of the five investigation tools that returned no evidence. Hard tier
rules override the score. Tiers 1–2 require a human, tier 3 escalates with no
proposal, and execution preconditions can BLOCK with an explicit reason code.

Untrusted telemetry, internal access and state-changing tools require a human
for every action. `auto_approve_tiers` stays empty. Test bypass requires both
`INCIDENT_ZERO_TEST=1` and `--auto-approve-for-tests`, and prints a test-only
banner. The localhost HTTP approval endpoint cannot request that bypass.

An approval lasts ten minutes and binds the operation, target, parameters,
report, operator and current world state. SQLite retains token fingerprints,
private rollback state and idempotency records. Cross-process exclusion allows
one mutation/verification sequence at a time; targets have a five-minute
cooldown. Uncertain process crashes remain blocked for operator review.

Dry run, approval and execution are separate nodes. Resuming the same SQLite
thread re-enters `interrupt()` with the token, without prompting again. This
follows the documented [LangGraph interrupt semantics](https://docs.langchain.com/oss/python/langgraph/interrupts).
The one-import integration is `from agent.respond import build_graph` in the
brain entry point; this branch does not edit the other session's graph files.

Recovery needs a 180-second window, two consecutive successful 30-second
samples, at least 20 measured frontend server requests in the two-minute
window, and a running load generator. All original detector alert signals are
rechecked, including signals omitted from the compact report. Unsupported or
unavailable verification blocks an action. A restart cannot restore interrupted
requests; a failed restart verification escalates without claiming rollback.
