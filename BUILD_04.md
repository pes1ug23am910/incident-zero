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

## Audit corrections before the repeated rehearsal

- B1: origin selection examines the complete parent/child graph and returns
  leaf error spans deepest first, with a separate `span:` proof for each. The
  retained nine-error payment trace now names `payment` / `PaymentService/Charge`
  first and retains `Payment request failed. Invalid token…`. A two-hop synthetic
  failure with a second independent branch verifies ordering and both span IDs.
- B2: every report string uses the shared disclosure guard, with the offending
  JSON path returned. The audit's leak is rejected. The runner validates before
  writing a bundle and gives one finish-only repair using the same evidence and
  tool count, including when all twelve reads have been used. Persistent refusal
  writes no invalid bundle and ends the checkpoint. Targeted suite: 143 passed,
  two existing live-fixture skips.
- M1: the operator prepares one persistent injection directory mount at `up`.
  Injection rewrites the file; reset restores its pristine bytes. Diagnostic
  container/deploy/health outputs exclude the control backend. Named spanmetrics
  filter its evaluation operations before aggregation and retain safe query
  aliases in evidence; resolution expands those aliases at the backend boundary.
  The retained working-tree evidence-grounding improvements were reviewed and
  kept; named aliases preserve the same positive signal scoring.
  Live verification on 23 October: checkout error rate 0.20, payment 0.50;
  ad/cart/recommendation each 0.00. Frontend/proxy/load-generator had propagated
  checkout failures. The control container ID was identical before injection,
  after injection and after reset. Reset succeeded; error rates cleared by the
  92-second sample and remained clean through 182 seconds. Observations are in
  `reports/verification-m1/observations.json`. The official demo checkout remained
  clean. Targeted operator/filter/query/disclosure checks: 61 passed; query and
  evidence-isolation checks: 72 passed.
- M3/M4/M5: trace reads and resolution, plus operator status, use the published
  Jaeger port before the proxy. Backend reads have an eight-second timeout and
  one retry; tools report elapsed time without the former 2.5-second kill.
  OpenSearch errors and zero usable records fall back to Docker stdout/stderr
  for any demo service. Live with an intentionally unreachable proxy override,
  direct Jaeger returned a frontend trace in 0.219 s. With an unreachable
  OpenSearch override, recommendation returned three Docker log records in
  4.437 s. Transport/operator tests: 28 passed; trace/log/resolver regressions:
  43 passed. No service was stopped for these checks.

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
