# Schema and readable reports — 2026-10-23

Implemented the team-defined report contract, field-by-field guide, CLI validator, Markdown renderer, explicit illustrative examples, and semantic tests. All work is inside this repository. These components only read report/evidence data and write repository artifacts; they never change the running demo.

The contract closes every object with `additionalProperties: false`, including action-specific parameter objects. The validator checks evidence references and genuine backend resolution by default, source/type agreement, confidence and escalation, component support, explicit approval before execution, fixed/recovered consistency, audit fields, timezone-aware event order, finite numbers, and prohibited diagnostic disclosure text. Runtime-assembled guard markers keep the package source free of the literal endpoint/configuration strings caught by the repository isolation scan. The validator never opens those sources.

## Verification completed

Measured using the local Python environment on this laptop at approximately 13:50 IST. CLI durations include process startup.

| Check | Result | Time |
| --- | --- | ---: |
| `pytest tests/test_schema.py --basetemp=.build/pytest-schema -q` | 37 passed | 0.22 s pytest-reported execution |
| Valid example with explicit offline fixture | Exit 0 | 0.2009 s |
| Exact spec command: `python -m schema.validate schema/examples/valid.json` | Exit 0; independently re-fetched the payment container state from Docker | 0.5282 s |
| Invalid unresolved-evidence example | Exit 1, `$.evidence[0].id` | 0.1934 s |
| Invalid fixed-without-approval-time example | Exit 1, `$.approval.approved_at` | 0.1764 s |
| Invalid low-confidence example | Exit 1, `$.status` | 0.1802 s |
| `python -m reports.render schema/examples/valid.json` | Exit 0; Markdown generated and inspected | 0.1080 s |
| Forbidden-literal scan over schema, reports, and schema tests | No matches | Not timed |
| Repository no-disclosure and isolation tests | 4 passed | 0.24 s pytest-reported execution |

Tests cover malformed/missing/changed/unreachable evidence responses, cross-references, source agreement, approval before execution, complete fixed reports, missing timezone, reversed events, nonfinite values, nested unknown fields, each action's parameter allowlist, CLI glob/error behavior, and rendering with token redaction. The default resolver interface is covered by a controlled test double; that test does not claim live backend verification.

## Limits and acceptance interpretation

The example JSON and its evidence fixture are hand-authored illustrations, visibly labelled as such in both JSON and Markdown. They are not reports from a measured application incident. No application root cause, approved action, or recovery is claimed by this deliverable.

The exact valid-example acceptance command also passed with genuine Docker resolution: its sole assertion, `container:payment:Status=running`, matched the current backend. This verifies the default resolver integration for a live container fact; the example remains hand-authored and does not establish an application diagnosis.

Live metrics/trace/log-backed incident validation is **not verified** here: the stack's collector startup is blocked by a Docker API incompatibility described in BUILD_01. The normal command `python -m schema.validate <report.json>` uses real read-tool resolution and fails closed when its evidence cannot be re-fetched. For reproducible example checks even when the stack changes, the additional `--offline-fixture` option is explicit and prints a console notice on every run.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_schema.py --basetemp=.build/pytest-schema -q
.\.venv\Scripts\python.exe -m schema.validate schema/examples/valid.json --offline-fixture schema/examples/evidence_fixture.json
.\.venv\Scripts\python.exe -m schema.validate 'schema/examples/invalid_*.json' --offline-fixture schema/examples/evidence_fixture.json
.\.venv\Scripts\python.exe -m reports.render schema/examples/valid.json
.\.venv\Scripts\python.exe -m schema.validate 'reports/*.json'
```

The invalid-example command intentionally exits 1. The final command requires real reports with currently resolvable evidence and does not select fixture mode automatically.

## Round 1 continuation: contract additions

The earlier collector blocker above describes the interrupted session. Current live
stack acceptance is recorded separately in `BUILD_01B.md`; it is not inferred from
these schema tests.

Added `health_table` to investigation tools and `dlog:<container>:<hex-hash>` to
evidence IDs with source `docker`. The existing `action_log:<positive-line-number>`
form is now explicitly tested, including invalid line numbers and source mismatch.
Returned resolver sources, when supplied, must agree with the report as well.

Added `status: no_incident` for an evidence-supported clean finding. It retains
the investigated component and category `unknown`, permits low confidence in an
incident cause without escalation, and rejects actionable remediation proposals,
executed actions, recovery/rollback claims, and incident resolution timestamps.
Missing evidence cannot establish a clean finding; authors must also describe the
observed scope and telemetry limitations instead of interpreting absence of data
as application health.

Default validation now passes the report's `run_id` as `run_dir` to the evidence
resolver. Resolution tries live data first and then only that run's snapshots.
CLI wording and rendered reproduction instructions distinguish this fallback from
live evidence. Explicit offline example fixtures remain separately labelled.

| Check | Result | Time |
| --- | --- | ---: |
| `python -m pytest tests/test_schema.py --basetemp=.build/pytest-schema-round1b -q` | 56 passed | 0.30 s pytest execution; 0.87 s whole process |

These focused tests validate the contract, source agreement, snapshot-compatible
resolver interface, and report rendering. They do not claim a live incident or
recovery. The full suite and live acceptance results are recorded by the
continuation's final verification.

Final continuation checks against the completed resolver:

| Command | Result | Seconds |
| --- | --- | ---: |
| `python -m pytest tests/test_schema.py -q` | 56 passed | 0.51 pytest execution |
| `python -m schema.validate schema/examples/valid.json` | Exit 0, current payment container fact resolves | 0.6696 |
| `python -m schema.validate schema/examples/invalid_unresolved.json --offline-fixture schema/examples/evidence_fixture.json` | Exit 1, `$.evidence[0].id` | 0.2084 |
| `python -m schema.validate schema/examples/invalid_fixed_no_approval_time.json --offline-fixture schema/examples/evidence_fixture.json` | Exit 1, `$.approval.approved_at` | 0.2089 |
| `python -m schema.validate schema/examples/invalid_low_confidence.json --offline-fixture schema/examples/evidence_fixture.json` | Exit 1, `$.status` | 0.2183 |
| `python -m reports.render schema/examples/valid.json` | Exit 0 | 0.1071 |
