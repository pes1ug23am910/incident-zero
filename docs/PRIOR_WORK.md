# Prior work declaration

The mentors allowed reuse of Yash Verma's unpublished personal rehearsal code,
provided each port is declared. No git history was imported.

| File in this repository | Origin | Adaptation today |
|---|---|---|
| `agent/llm_router.py` | `D:\hack-template\core\llm_router.py` | Adapted environment loading and provider/retry structure; replaced the client with structured tool calls, environment-only model pins, sanitized request/response audit records, token/cost accounting, and explicit failure instead of stub success. |

The prior evidence checker and hypotheses module were inspected but not ported:
their experiment/prediction interfaces do not match this incident contract.
Safety, approval and recovery-lock modules were not ported in this brain-only
session. No prior documents, prompts, reports, fixtures or build outputs were
copied. The graph, evidence confidence rules, policy and detector were written
for this repository on 2026-10-23.

Live fixtures and reports are recorded from this team's local demo runs.
