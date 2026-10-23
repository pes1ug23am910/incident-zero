# Why these controls exist

This session builds detection and diagnosis. It proposes remedies and saves a
graph paused for review. **It cannot execute a remedy.** Live diagnostic results
belong in BUILD_04.md. Tests of control flow do not establish live accuracy.

## Telemetry drives investigation

The first read is health_table across known services. Each later structured tool
call contains a reason and selects one read. The 12-call budget includes health.
Repeated identical calls stop investigation; an explicit graph recursion limit
bounds iteration. A call budget does not guarantee a wall-clock duration.

The detector reads metrics and container health without injection state. Rate
windows are at least two minutes. The checkpoint script waits for error rates
to clear after reset: the connector can retain prior errors for roughly 120
seconds. Future post-action verification must cover at least 180 seconds with
30-second samples; that verifier is not built in this session.

Checks: tests/test_detect.py, tests/test_graph_routes.py and report investigation
arrays. Actual alert timings are recorded separately in the live ledger.

## Diagnosis never reads the answer

The tool layer removes control-setting names, associated trace attributes and
events, revealing log lines, and telemetry emitted by the control backend.
Recorded-span filtering regressions are implemented. Ordinary container liveness
remains observable; excluded backend records are removed from model context.

The caller's incident identifier is report metadata, not prompt input. Diagnostic
packages cannot import the injector or read ground-truth records. Only the
evaluation package may read those records for scoring. Diagnosis depends on
errors, latency, logs, service names and container state.

Service-to-setting mapping belongs only in the future `action_api/flags.py`.
The brain proposes `toggle_flag` with a service target and the phrase "disable
the failure switch for &lt;service&gt;". The hands may read the current variant only
for rollback and world-state hashing. Those reads are not diagnosis. Mapping
and writing are deferred to the Action API session.

Checks: tests/test_no_flag_reads.py, tests/test_agent_isolation.py and
tests/test_redaction.py, alongside review of actual evidence and transcripts.

## Evidence must exist and support the component

Every read snapshots evidence. The planted-evidence guard rejects IDs not
received during the investigation and checks their relationship to the claimed
component. Schema validation independently checks source identifiers and
structured service names. An invented summary alone cannot establish support.

Resolution tries live data, the named run's snapshot, then an explicitly selected
committed report bundle. Origins are labelled live, snapshot or bundle_snapshot.
ID, source, checksum and size are checked. Run and bundle paths are confined, and
linked paths are rejected. A snapshot establishes a recorded observation, not
the current system state.

Checks: tests/test_planted_evidence.py, tests/test_snapshots.py,
tests/test_bundle_resolution.py and tests/test_schema.py. For a retained report,
run `python -m schema.validate reports/<incident-id>/report.json`. For one ID use
`python -m tools.resolve '<id>' --run-dir runs/<run-id> --bundle-dir reports/<incident-id>`.

## Confidence and symptom coverage

The report separates confidence_model from confidence_evidence. Code derives
evidence confidence from independent positive sources and signal magnitude.
Final confidence is their minimum. High confidence needs two supporting sources;
two Docker observations share one backend source. This heuristic needs measured
calibration and is not an established probability.

root_causes is confidence-ordered; root_cause exactly aliases the first entry.
A dependency graph associates caller symptoms with the failing component.
Unexplained symptoms remain visible so one cause need not hide another.
Missing telemetry and unexplained symptoms belong in limitations. Confidence
below 0.6 escalates. Clean findings and STOP-driven aborts have separate safe
statuses. Missing telemetry alone cannot establish no_incident.

Practice incidents are the tuning set. Combinations and no fault remain held
out until tuning stops. Evaluation must identify measured runs and report
calibration counts, Brier score and Wilson intervals honestly.

## Untrusted telemetry cannot choose an action

Shop users can put instructions into logs, exception text and span attributes.
Results are marked as telemetry data, and known instruction-like text is omitted
from model input. Textual defences are supplementary: code selects the action
type from a validated category, and targets belong to the known service list.
The model cannot submit an arbitrary shell command.

Checks: tests/test_injection.py and tests/test_risk.py. A planted instruction
to restart payment must not change the proposal. This regression does not prove
protection against every possible indirect prompt injection.

`action_api/policy.yaml` keeps `auto_approve_tiers: []`. Untrusted input, internal
access and future state-changing tools require a human decision on every action.
There is no approval bypass in this session.

## Risk determines human review

agent/risk.py computes criticality, journeys, blast radius, reversibility, data
risk, confidence, score and tier. It explicitly says distinct users were not
measured: span rates do not become invented user counts.

Tier 1 permits quick review only for one auxiliary/core service, a reversible
proposal and confidence at least 0.75. Its line shows action, target and predicted
effect. Tier 2 needs full evidence and typed yes for critical services or
restarts. Tier 3 suppresses proposals and adds escalation and a runbook for
multiple independent failures, data risk, low confidence or an unsupported remedy.
Inherited caller symptoms remain one established cause; independent failures
increase assessed scope.

Data risk concerns the proposed change. Restarting payment creates payment risk;
restarting a live cart/cache can discard state. A reversible application switch
does not permit payment-data edits or charge retries. An already stopped cache
is distinguished from discarding a live cache's state. A future restart still
needs a human and measured verification. Impact appears before proposals.

Actual quick-keypress and typed-yes clients are deferred. No reviewer agent
exists in this build; evidence confidence supplies the independent-source rule.
A future reviewer must use a different model/vendor from the investigator.

## Durable approval boundaries

The loop is a LangGraph StateGraph. SqliteSaver persists runs/checkpoints.sqlite
with thread_id equal to run_id. Preview and approval are separate nodes because
an interrupted node starts again on resume. The resume value carries the
decision; future approval tokens must travel there too, avoiding a second prompt.

agent.respond checks that the next saved node is exactly approval, refusing
unknown and completed threads. This build permits rejection and refuses approval
because the Action API is unavailable. Even direct graph resume with approval
reaches an inert execute node: action.executed remains false. The verify node
preserves the unperformed record and claims no recovery. STOP prevents resumption
and stops ongoing investigation.

tests/test_graph_persistence.py closes and reopens SQLite connections, resumes
the same checkpoint without repeating preview, refuses mismatched/completed
threads, and confirms approved resume performs no action. These are synthetic
offline lifecycle tests, not live diagnostic evaluation.

## Auditability and future work

The router reads model choices from the environment and uses configured
fallbacks. It logs sanitized requests, public tool decisions, token counts and
reference cost estimates, excluding provider reasoning content.
Temperature 0 and logged prompts make runs reproducible in inputs, not outputs.
Working models and measured costs belong in BUILD_04.md.

The primary schema closes objects and checks aliases, confidence, evidence and
approval/execution consistency. The external adapter is identity until a supplied
schema activates its mapping table. It preserves the internal report and marks
unavailable values instead of inventing them.

The later Action API session must implement the localhost allowlisted service,
authoritative dry runs, human-issued tokens bound to world state and expiry,
per-action approval, append-only audit, STOP endpoints and human clear phrase,
execution, verification and rollback. Those endpoints, expiry guarantees,
successful remediations and rollback tests are not claimed as built or verified.

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
