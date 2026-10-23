# Build 04 — Evidence-grounded diagnosis

2026-10-23. Brain-only implementation; no application remediation executes.

## Implementation checkpoint

Implemented a LangGraph StateGraph with observe → investigate → diagnose →
assess_risk → propose. Read calls are structured model-selected functions, one
per iteration, capped at 12 including the health overview. The graph persists
in `runs/checkpoints.sqlite` with the run id as thread id and pauses at approval.
Dry run, approval and inert execution/verification nodes are separate. The
Action API and actual approved execution are explicitly deferred.

The pinned primary `openai/gpt-5` answered a minimal structured call through
OpenRouter, medium reasoning: 118 input tokens, 200 output tokens, estimated
$0.002148 at the requested $1.25/M input and $10/M output reference prices.
No fallback was needed for that probe. Models are read from environment values.
LangGraph 1.2.16 and SQLite checkpointer 3.1.2 installed successfully; no plain
loop fallback was used. Initial dependency downloads timed out; retry succeeded.

The first integrated test run passed 293 tests with one existing Windows
symbolic-link privilege skip. This is unit/integration evidence, not a live
diagnosis claim. Live diagnosis results are pending below.

Confidence is computed as the minimum of model confidence and a code score
based on independent positive signals that identify the component. Returned
evidence IDs are checked before admission, and schema validation resolves them.
Risk rules suppress all tier-3 actions. Each bundle includes the report, alert,
sanitized model log, empty action excerpt (no actions), and evidence snapshots.

## Live results

Not yet verified at this implementation checkpoint. Payment, stopped
recommendation and cache will run first; CPU starvation is the abstain backup.
All ten practice cases are tuning data. The no-fault and combination cases will
be held out until the prompt is frozen. Temperature 0 and logged prompts make
runs reproducible in inputs, not outputs.

## Scope and unresolved acceptance

- No Action API, human approval execution, rollback, or recovery caused by an
  agent action is verified in this session.
- Restart proposals are tier 2, overriding the brief's earlier tier-1 example.
- Payment/state data risk means incremental risk of the proposed operation;
  a toggle is not a charge or cart-data mutation. Restarting an already-stopped
  cache is tier 2 only when stopped state is supported and no running-state
  evidence contradicts it.
- Multi-cause incidents escalate without a proposal when aggregate tier 3
  applies; symptoms propagated to callers alone do not create another cause.
- The official demo checkout is never edited. Injection uses the repository's
  existing operator overlay, as measured in BUILD_01B.

Implementation references: [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts),
[OpenRouter tool calling](https://openrouter.ai/docs/guides/features/tool-calling),
[reasoning effort](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
