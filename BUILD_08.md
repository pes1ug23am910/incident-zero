# Fold verification

The base revision was `2a7b83c5`. The full baseline suite returned **671 passed,
3 skipped in 35.79 seconds**. Read-only readiness showed all 21 containers running
and an unchanged official demo checkout. These observations precede the changes
below; they are not final acceptance.

## Approval provenance

Approval records now retain surface, live/test mode, approver, timestamps and a
non-secret token fingerprint through the durable store, responder, report and
Control Room. Test approvals render explicitly as test harness decisions.

Twenty-five historical bundles were re-rendered from their retained records.
Twelve approvals are test-mode, including the automated browser acceptance in
payment r9. The two rejections retain their actual surfaces. Raw action logs and
evidence snapshots were not rewritten. Historical prompt-start timestamps were
not measured and remain identified as such. Repeating the migration changed no
bundle.

The ten new provenance tests passed in 1.43 seconds. Two renderer/API compatibility
checks also passed in the focused 12-test group. No new live approval or recovery
is claimed by this step.
