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
diagnosis claim. Live measurements and outstanding rehearsal requirements appear below.

Confidence is computed as the minimum of model confidence and a code score
based on independent positive signals that identify the component. Returned
evidence IDs are checked before admission, and schema validation resolves them.
Risk rules suppress all tier-3 actions. Each bundle includes the report, alert,
sanitized model log, empty action excerpt (no actions), and evidence snapshots.

## Live results

Payment r4–r6 and stopped recommendation r1–r3 have each passed three
consecutive complete rehearsals: correct
diagnosis and proposal, valid retained reports, successful report printing,
and verified telemetry clearance before and after every injection. Unavailable
cache rehearsals did not meet acceptance; the CPU starvation backup and no-fault case
remain pending. The earlier failed attempts remain
in the ledger below.

The seconds below are `agent.elapsed_s`, measured inside the diagnosis graph;
they exclude reset, telemetry clearance, injection, alert waiting and the final
validation command. Correctness includes the expected confidence, status and
proposal, so a matching component alone does not count as a pass.

| Incident | Run / report | Component | Correct? | Confidence | Tool calls | Seconds | Model |
|---|---|---|---|---:|---:|---:|---|
| payment-failure | [r1](reports/payment-failure-r1/report.json) | ad | No: model unavailable | 0.30 | 1 | 2.453 | unavailable |
| payment-failure | [r2](reports/payment-failure-r2/report.json) | payment | No: confidence/status below expectation | 0.70 | 4 | 115.187 | openai/gpt-5 |
| payment-failure | [r3](reports/payment-failure-r3/report.json) | payment | Diagnosis yes; report printing failed | 0.90 | 3 | 88.016 | openai/gpt-5 |
| payment-failure | [r4](reports/payment-failure-r4/report.json) | payment | Yes: complete rehearsal | 0.90 | 3 | 57.015 | openai/gpt-5 |
| payment-failure | [r5](reports/payment-failure-r5/report.json) | payment | Yes: complete rehearsal | 0.90 | 3 | 58.375 | openai/gpt-5 |
| payment-failure | [r6](reports/payment-failure-r6/report.json) | payment | Yes: complete rehearsal | 0.90 | 3 | 57.828 | openai/gpt-5 |
| container-stopped | [r1](reports/container-stopped-r1/report.json) | recommendation | Yes: complete rehearsal | 0.85 | 3 | 56.969 | openai/gpt-5 |
| container-stopped | [r2](reports/container-stopped-r2/report.json) | recommendation | Yes: complete rehearsal | 0.90 | 2 | 42.734 | openai/gpt-5 |
| container-stopped | [r3](reports/container-stopped-r3/report.json) | recommendation | Yes: complete rehearsal; over 90 s | 0.90 | 3 | 93.500 | openai/gpt-5 |
| cache-unavailable | [r1](reports/cache-unavailable-r1/report.json) | valkey-cart | No: needs_human, insufficient corroboration | 0.55 | 12 | 512.984 | openai/gpt-5 |
| cache-unavailable | [r2](reports/cache-unavailable-r2/report.json) | valkey-cart | No: needs_human, insufficient corroboration | 0.55 | 6 | 208.219 | openai/gpt-5 |

| Incident / run | Diagnosis run id | Input / output tokens | Reference cost estimate |
|---|---|---:|---:|
| payment-failure r1 | `runs/20261023T102943.979795Z-a1fcd705` | 0 / 0 | $0.000000 recorded; no successful response |
| payment-failure r2 | `runs/20261023T110643.477884Z-ff5ddc4c` | 98,674 / 6,900 | $0.192342 |
| payment-failure r3 | `runs/20261023T111643.077037Z-9461e0c3` | 56,201 / 6,257 | $0.132821 |
| payment-failure r4 | `runs/20261023T112549.360906Z-ac1d2bef` | 39,760 / 3,793 | $0.087630 |
| payment-failure r5 | `runs/20261023T113346.104216Z-514905da` | 34,369 / 3,603 | $0.078991 |
| payment-failure r6 | `runs/20261023T114143.041886Z-68a917d4` | 42,030 / 4,389 | $0.096427 |
| container-stopped r1 | `runs/20261023T114929.814263Z-8fd5a8fd` | 26,926 / 3,882 | $0.072478 |
| container-stopped r2 | `runs/20261023T115651.341545Z-14d550d5` | 20,110 / 2,659 | $0.051727 |
| container-stopped r3 | `runs/20261023T120358.826377Z-c84200c3` | 34,143 / 5,839 | $0.101069 |

Costs use the requested $1.25/M input and $10/M output reference rates rather
than claiming a reconciled provider invoice. Each token total includes every
recorded model decision in the run, including repair decisions.

Stage metadata distinguishes command completion from diagnosis acceptance.
The historical r1 script failed validation because its null approval token had
been replaced during scrubbing; cleanup nevertheless verified clear telemetry
over 181.750 seconds. r2 completed its command and schema validation, but its
diagnosis failed acceptance: it ended `needs_human` without a proposal. Its
reset took 2.032 seconds and clearance was verified over 182.531 seconds.
r3 has a valid `diagnosed` report with `application_flag`, a payment-targeted
`toggle_flag` proposal, tier 2 and `stopped_because = confident`. The subsequent
report-printing stage failed because the Windows character encoding could not
represent the U+2192 arrow. The runner now configures UTF-8 for stdout/stderr
and inherited Python output; eleven runner tests passed. This does not turn r3
into a successful end-to-end rehearsal. Its final `checkpoint2.json` records
verified clearance over 182.406 seconds. The required consecutive full passes
were subsequently completed by r4–r6. Each has seven samples spanning at least
180 seconds in both clearance windows, with the final two samples clean.

| Accepted run | Alert wait (s) | Before clearance (s) | After clearance (s) | Recorded runner stages total (s) |
|---|---:|---:|---:|---:|
| payment-failure r4 | 51.421 | 182.407 | 182.531 | 487.937 |
| payment-failure r5 | 38.969 | 182.657 | 181.750 | 474.781 |
| payment-failure r6 | 39.391 | 182.688 | 181.843 | 476.906 |
| container-stopped r1 | 1.750 | 182.188 | 182.547 | 438.735 |
| container-stopped r2 | 2.531 | 182.469 | 182.203 | 425.969 |
| container-stopped r3 | 2.469 | 182.547 | 182.516 | 477.469 |

All six accepted rehearsals used the same prompt hash
`1b8ed98156c66f6775f94a4ae31d85efee45b7f1a0d5edcd12d846184d207652`.
The full command includes two three-minute clearance windows; the sub-90-second
presentation target applies to diagnosis, not to that complete rehearsal.
Stopped recommendation r1–r3 each produced `container_down`, a recommendation
restart proposal and tier 2, with container state and upstream failures as
support. Its r3 diagnosis took 93.500 seconds, missing the 90-second presentation
target despite correct diagnosis and a complete passing workflow. This latency
miss is retained; it is not counted as an under-90-second result.

Two generic investigation corrections accompanied these rehearsals. Before r2,
the caller graph gained transitive coverage through frontend, frontend-proxy
and load-generator, matching the configured request path while retaining
independent sibling symptoms. r2 then kept its preliminary model confidence at
0.70 despite corroborating logs and an evidence score of 0.95. Finish feedback
incorrectly demanded more sources, and an unsupported alternative consumed a
repair allowance already affected by that feedback. The prompt now reassesses
confidence after new observations and keeps unsupported possibilities out of
the cited cause list; graph feedback distinguishes confidence from evidence
shortfalls and tracks malformed-decision repair separately. Code never raises
model confidence. In r3 the model reassessed 0.70 to 0.90 after logs, corrected
one malformed evidence identifier on its allowed retry, and finished without
requiring a disclosure repair.

Decision validation now checks the returned function against the exact offered
set and validates finish arguments before processing hypotheses. This closes a
bypass where an unoffered finish could avoid a required read, and rejects a
string-valued or missing `no_incident`. Graph/disclosure/replay regressions:
95 passed, two pending live-fixture skips. Runner outcomes also mark unexpected
exceptions and interrupts as failures while retaining cleanup and propagating
interrupts. Operator status Docker reads now share the eight-second, one-retry
policy; mutation timeouts remain unchanged. Targeted runner/transport checks:
44 passed.

All ten practice cases are tuning data. The requested order places the no-fault
case after the CPU backup but before the remaining practice cases. If subsequent
practice tuning changes the prompt, tools or policy, that earlier no-fault run
cannot be counted as evaluation of the final frozen system. Record its provenance
and any later repetition explicitly. Combination evaluation follows the final
tuning freeze. Temperature 0 and logged prompts make runs reproducible in
inputs, not outputs.

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
- Model failure investigation: historical `payment-failure-r1` used run
  `runs/20261023T102943.979795Z-a1fcd705`. Both configured OpenRouter routes
  failed with `SSLError` before an HTTP response (0.296 s and 0.110 s). The old
  log omitted exception detail, so the exact TLS cause cannot be recovered.
  Successful probes bracketed the failure. Its `ad` / unknown / 0.30 was an
  alert-owner placeholder, not an LLM diagnosis. Terminal failures now identify
  attempted provider/model routes, retain sanitized error detail, force
  `needs_human` with no proposal, and give an unestablished cause zero model
  confidence. TLS verification remains enabled; transport failures retry once.
  A new live structured probe succeeded on `openai/gpt-5`: 125 input tokens,
  254 output tokens, reference estimate $0.002696, one call with no fallback.
  Router/report/graph/replay/disclosure tests: 63 passed, two pending live-fixture
  skips. Retained graph/state/replay changes were reviewed and kept; a separate
  graph/replay regression run passed 56 tests with the same two skips.

## Scope and unresolved acceptance

Integration review retained the in-flight transport retry, structured function
validation, temporal evidence checks, logger identity, report context, runner,
and calibration work. Before the final scoring correction the full suite passed
500 tests with three skips. This is regression evidence, not live acceptance.

Cache r1 (`runs/20261023T121227.303255Z-dc304b61`) and r2
(`runs/20261023T122840.338357Z-47ea815f`) both named `valkey-cart` with
`container_down`, confidence 0.55 and status `needs_human`; neither proposed an
action. They used 12 and 6 reads respectively. Their historical reports remain
unchanged. In particular, r2 did not collect positive cart connection failures,
so an exited container alone must still be insufficient for confident action.

The taxonomy decision is based on the observed cause: an exited dependency
container **is `container_down`**. The brief's dependency-unavailable scenario
is satisfied by identifying `valkey-cart` as the cause and `cart` as its symptom
owner. `dependency_unavailable` remains appropriate when unavailability is
established without an exited-container cause. Container lifecycle state and
dependent application connection failures are independent observations even
when both were retrieved through Docker; OpenSearch and Docker copies of the
same application's logs remain a single log source. This general rule permits
evidence confidence above 0.75 only when both positive observations are present;
it never raises model confidence or keys off an incident name.

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
