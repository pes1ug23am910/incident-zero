# Integration and teammate lanes

One demo stack exists. The integration/fold owner schedules all injections,
resets, executions and live acceptance. Docs/portability work is read-only against
that stack. This page reconstructs the lane agreement from the comparison record;
the mentioned uncommitted LANES draft was not present in either checkout when read.

| Lane / time | Owner | Files / task | Acceptance evidence |
|---|---|---|---|
| Fold / overnight | Yash, integration owner | Agent, Action API, detector, tools, faultctl, schema, knowledge and memory | Audit fixes and package tests; knowledge merge; current-prompt reruns; live approvals and cleanup |
| Docs and portability / overnight | Yash, docsport branch | scripts; new regression/gate test files and offline fixtures; docs/README; UI text only | Shell help/preview, read-only preflight records, Linux offline gate, bundle-backed documents; no stack mutation |
| 1: detection, 09:00-10:45 | Preetham, planned | `detect/core.py`, `tools/queries.py`, new `tests/test_detect_operation.py` | EmptyCart failures at about 3% of cart traffic raise an operation alert; ten healthy live ticks raise none |
| 2: evaluation, 10:45-12:30 | Preetham, planned, agreed stack slots | Diagnosis-only `scripts/campaign.py`, case manifest, evaluation rows | At least five tuning cases each have a bundle or honest miss; `eval.calibration` scores manifest; no automatic approval |
| 3: operator experience, by 13:15 | Preetham, planned | Control Room stage highlight; approval walkthrough | At 12:00, personally approve one browser plan and reject another; name/surface/mode in action log |

Coordinate edits at handoff: docsport owns scripts and the demo walkthrough tonight;
Preetham takes the listed lane files only after integration. Do not run competing
watchers/checkpoints or port an entire teammate branch. Re-implement only the six
rows in [PRIOR_WORK.md](PRIOR_WORK.md). No teammate live result becomes our result.

Before claiming completion, check [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).
Strict xfails must turn into ordinary passing tests when their fix lands; XPASS
intentionally blocks completion. Confirm event-day port authorship and overnight
commit acceptance at 09:00. Team roster, all five members' commits and each
member's explain/change sign-off remain not verified.
