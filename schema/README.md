# Incident report contract, version 1.0

This is the team's primary report format for a judge or teammate to read alongside the evidence. It records what was observed, how a conclusion was reached, who approved any change, and whether recovery was measured. Unknown fields are rejected throughout the document. The JSON Schema uses draft 2020-12; the Python validator adds evidence resolution and safety checks. All timestamps include a timezone. Earlier illustrative reports remain readable; new investigations supply the multi-cause and impact fields described below together.

`schema_version` identifies the contract. It must be `1.0`; a future incompatible format gets a new version.

`incident_id` identifies the incident. Use a known practice identifier when supplied by the operator, or `unknown-<timestamp>` for an unseen incident. The identifier is a label, never evidence of a cause.

`run_id` identifies the investigation as `runs/<timestamp-or-name>`. Default evidence resolution tries the live source first and then the evidence snapshots from this run only. When validating a report bundle with an `evidence/` sibling, the validator finally tries that bundle's copy. A bundle must be an immediate child of repository `reports/`; traversal, linked paths and corrupted records are rejected. The resolver identifies `live`, `snapshot`, or `bundle_snapshot` explicitly. Validation never opens an injection record.

`detected_at` is when the alert was observed. It is the starting point for the investigation timeline.

`diagnosed_at` is when the agent finished its investigation, including investigations that remain uncertain. It cannot precede detection.

`resolved_at` is when recovery was established, or `null` when it was not. A report marked `fixed` must provide this time.

`alert` records the triggering signal, service, observed value, threshold, and measurement window in seconds. Signals include error rate, 95th-percentile latency, container health, restart count, OOM, traffic, resource limits, and no alert. A numeric or null baseline is optional.

`symptoms` lists observations rather than assumed causes. Each item names a service, signal, human-readable observed value, and the IDs of evidence supporting it.

`investigation` records the ordered tool calls, the query, why each was needed, its finding, and the evidence it returned. Step numbers begin at one and remain consecutive. The five read tools and their `health_table` summary are allowed here.

`root_cause` gives the suspected component, a one-sentence explanation, a category, confidence from zero to one, and alternatives considered. The named component must occur in a symptom or an evidence summary. Confidence below 0.6 requires `needs_human` for incident diagnoses; it does not justify an automated change. For `no_incident`, identify the component checked, describe the evidence's clean finding and its scope, and use category `unknown`; confidence in an incident cause can be zero without forcing an incident diagnosis.

`root_causes` contains all supported causes in descending confidence order, with
`root_cause` an exact alias of the first entry. Each cause contains `component`,
`cause`, `category`, `confidence_model`, `confidence_evidence`, `confidence`,
`evidence_ids`, and `explains_symptoms`; `alternatives_considered` is optional.
The final confidence must equal the minimum of the model and evidence values.
Evidence IDs must occur in the report and cited source data must identify the
component; an invented evidence summary does not establish that connection.
`explains_symptoms` names services from `symptoms`, including callers whose
symptoms follow from a dependency failure. Unexplained symptoms belong in
`limitations`. No incident uses an unknown-category clean finding for its alias.

`impact` describes business criticality, affected journeys, a qualitative user
estimate, blast radius, reversibility, data risk, confidence, tier, score and
rationale. The renderer places it before the proposed action. Tier 3 carries no
proposal and requires `needs_human`; `no_incident` and a STOP-driven `aborted`
report are safe terminal exceptions. This module never infers an affected-user
count from span rates.

`evidence` lists unique, reproducible IDs, their sources, summaries, and queries or paths that reproduce the observation. Supported IDs are `trace:<id>`, `span:<trace>/<span>`, `log:<index>/<document>`, `metric:<name>{labels}@<timestamp>=<value>`, `container:<name>:<field>=<value>`, `action_log:<positive-line-number>`, and `dlog:<container>:<hexadecimal-line-hash>`. The final two forms identify action audit entries and Docker stdout/stderr lines. Their sources are respectively `action_log` and `docker`; other IDs likewise must agree with their backend. Every reference from a symptom or investigation step must appear here. The default validator calls `tools.resolve.resolve` for every listed ID, passes this report's run directory, and rejects evidence absent from both the live source and that run's snapshots. Snapshot evidence preserves the recorded observation and is not a claim about current health.

`proposed_actions` lists eligible remedies in impact order, at most one per cause.
`proposed_action` is its first item or `null` when the list is empty. Each item
has an allowlisted type, target service, reason, risk, parameters, and dry-run
result. Parameter objects are closed: `restart_service` and `toggle_flag` accept
exactly `service`, which must match `target`; `throttle_load` accepts exactly
`users` (a nonnegative integer) and `spawn_rate` (positive). The legacy singular
proposal also permits `none` with an empty parameter object. Internal setting
names never appear in proposals. Proposals describe intended actions and do not
execute them; each future action requires a separate human approval.

`approval` records the required human decision, request time, approver, approval time, and token. A true approval requires all four record fields. No approval time or token can be claimed before approval. The readable renderer redacts a present token.

`action` records whether execution occurred, its start and finish, and its audit-log reference. Execution requires explicit approval and an actionable proposal. The validator and renderer never execute actions.

`verification` records when health was checked, the signal, before and after values, whether recovery occurred, and whether an action was rolled back. A fixed report needs actual before/after measurements, a check time, and `recovered: true`.

`status` is `no_incident`, `diagnosed`, `needs_human`, `fixed`, `rolled_back`, or `aborted`. A fixed report needs approved execution and measured recovery. A rolled-back report must record that rollback occurred. Insufficient confidence in an incident diagnosis produces `needs_human`. Use `no_incident` only for an evidence-supported clean finding within the observed scope, never for unavailable telemetry. It requires evidence and category `unknown`, permits only a null or `none` proposal, and rejects execution, recovery, rollback, or a resolution timestamp.

`escalation_note` explains findings, uncertainty, and the next checks for a human. It must be nonempty for `needs_human`; otherwise it may be `null`.

`prevention` describes a possible way to avoid a repeat, or is `null` when no supported recommendation is available. It is a recommendation, not evidence that a change has been made.

`limitations` lists missing telemetry, unavailable backends, uncertain interpretations, and other limits on the conclusion. Illustrative examples explicitly identify themselves here.

`agent` records the model, count of tool calls (at most 12), elapsed seconds, and why investigation stopped: confidence, symptom coverage, no incident, budget, no progress, stop signal, or error. Optional metadata includes the prompt SHA-256, input/output token counts, estimated cost in USD, LLM call count, models used, and graph framework. Example reports use a clear hand-authored label rather than claim an agent run occurred.

Validation also rejects prohibited diagnostic configuration-disclosure text anywhere in keys or string values, without opening any configuration source. This is an output guard; source isolation is enforced separately by repository tests.

The external adapter is an identity copy until another schema is supplied. See
[MAPPING.md](MAPPING.md) for the executable mapping table and
`python -m schema.export reports/<id>/report.json --schema <their.json>`.
It preserves the internal report and validates the separate external JSON. An
unavailable required field gets an explicit marker and a note; schema types that
cannot represent unavailable values cause export to fail visibly.

## Run validation and rendering

Use the local environment from the repository root:

```powershell
.\.venv\Scripts\python.exe -m schema.validate 'reports/*.json'
.\.venv\Scripts\python.exe -m reports.render 'reports/*.json'
```

Validation exits 0 only when every matched report passes; failures print JSON field paths and exit 1. The first command resolves evidence against real backends, with recorded evidence from the report's run as a fallback. Rendering creates a Markdown sibling for each JSON input; `--output-dir reports` selects another folder. Rendering formats content and does not replace validation.

The examples are deliberately illustrative, not incident results. Validate them only with the explicit offline fixture option; the command prints an offline-mode notice and makes no live evidence claim:

```powershell
.\.venv\Scripts\python.exe -m schema.validate schema/examples/valid.json --offline-fixture schema/examples/evidence_fixture.json
.\.venv\Scripts\python.exe -m schema.validate 'schema/examples/invalid_*.json' --offline-fixture schema/examples/evidence_fixture.json
.\.venv\Scripts\python.exe -m reports.render schema/examples/valid.json
.\.venv\Scripts\python.exe -m pytest tests/test_schema.py
```

The valid example passes; the three invalid reports fail for unresolved evidence, missing approval time on a fixed report, and low confidence without escalation. Offline fixtures check formatting and rules, never proof that a real incident occurred. Live evidence may expire or container state may change; the resolver then tries the recorded snapshot and identifies that origin. Validation fails if neither source resolves the ID.
