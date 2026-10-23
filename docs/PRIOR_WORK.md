# Prior-work and teammate attribution

The recorded mentor clarification permits reuse of Yash's unpublished rehearsal
code with declaration. No template Git history was imported. This describes
origin; it is not a claim of novel prior-art-free design.

| File in this repository | Origin | Adaptation / evidence |
|---|---|---|
| `agent/llm_router.py` | Yash Verma's unpublished `hack-template/core/llm_router.py` | Environment loading and provider/retry structure; structured calls, environment-only pins, sanitized logs, usage accounting and explicit model failure; source header records adaptation |

The earlier evidence-checker/hypotheses modules were inspected but not ported
according to the existing declaration. No additional template port is verified.
The hands/response implementation was written for this contract, per that
declaration; `scripts/checkpoint2.py` came from the team's concurrent checkout,
not an external package. Event-day authorship timing and overnight-work acceptance
must be confirmed with the mentor before the freeze.

## Teammate modules

These are the six approved port targets from Preetham's parallel event-day
prototype at `preeeetham/break_point@273ae06`. They are **not verified as landed**
in this snapshot; no teammate live results transfer. The fold must fill commit
IDs from actual re-implementations, without merging the source branch history.

| Destination | Origin at 273ae06 | Idea author | Required adaptation | Landing commit |
|---|---|---|---|---|
| `agent/reporting.py` prevention | `incident_zero/agents/reporter.py:16-31` | Preetham | Our cause categories, component-specific single string, disclosure check | not verified |
| `tools/redact.py` name additions | `incident_zero/redact.py:18-25` | Preetham | Names only; preserve whole-record drop semantics | not verified |
| `tools/traces.py` client/server gaps | `incident_zero/telemetry/tools.py:161-173` | Preetham | Scrubbed v1 spans, both evidence IDs; gap >=200ms and >=50% client duration | not verified |
| `scripts/campaign.py` | Idea from `incident_zero/practice/campaign.py:72-152` | Preetham | Rewrite against checkpoint2 and our manifest; diagnosis-only, no auto-approval | not verified |
| `tools/queries.py`, `agent/evidence.py` sample age | Idea from `incident_zero/tools.py:429-454` | Preetham | Correct query and valkey attribution; absence is unknown | not verified |
| `action_api/executors.py` paused restart | `incident_zero/actions/mock_server.py:45-46` | Preetham | Approved unpause then restart; STOP checked between commands | not verified |

No `break_point/*` imports or pre-event public code may enter. Not ported: the
teammate sentinel, prompts, judge, lifecycle/approval API, verifier, planner, React
UI, email notifications or Jaeger v3 client. Per-operation alerting is newly built
from the hidden-test requirements, not a port of a feature in that prototype.

Required provenance: obtain Preetham's confirmation that the port source was
written after 09:15 on the event day. Re-implement against this contract, with
`Port-of: preeeetham/break_point@273ae06 path:lines` in the commit body and a named
test. If Yash lands a port, he remains the author and names Preetham as the idea
author in the body. Never impersonate a teammate or import AI co-author trailers.
Preetham's own contributions and the five-member rule remain to be verified.
