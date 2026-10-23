# Team form

Incident Zero: Build an AI On-Call Engineer. Bosch BGSW hackathon, PES University, Oct 23-24, 2026.

## Team

- **Team name:** `<team name>`
- **Team number (as assigned by Bosch):** `<number>`

## Members and who built which part

Every member committed code under their own name and can explain and change the part listed against them (rules 2 and 3).

| # | Name | SRN | Built |
|---|---|---|---|
| 1 | `<name>` | `<SRN>` | `agent/`: the investigation loop on top of `tools/`, hypotheses and confidence, the abstain path, schema output |
| 2 | `<name>` | `<SRN>` | `action_api/` and `detect/`: allowlist, dry run, approval token, STOP, verify and rollback, action log; the alert poller and thresholds |
| 3 | `<name>` | `<SRN>` | Demo bring-up in minimal mode and `faultctl`: inject, reset with read-back, status, combinations |
| 4 | `<name>` | `<SRN>` | `tools/`: the five read-only tools with evidence ids, `health_table`, `resolve`, the named queries |
| 5 | `<name>` | `<SRN>` | `schema/` and `reports/`: the schema, validator and Markdown renderer; the documents in `docs/` |

Stretch goals, if shipped (one line each, delete the rest):

| Stretch goal | Built by |
|---|---|
| Calibrated confidence | `<name>` |
| Incident memory | `<name>` |
| Reviewer agent | `<name>` |
| Chat-style approval page | `<name>` |
| Prevention suggestions | `<name>` |

Sign-off: each member has walked through and changed their part's code at least once before the freeze.

- [ ] 1 `<initials>`  - [ ] 2 `<initials>`  - [ ] 3 `<initials>`  - [ ] 4 `<initials>`  - [ ] 5 `<initials>`

## Tools and AI models used

AI coding assistants were used and are declared here, as rule 2 requires. Every line of code they produced was reviewed by the member who owns that part.

| Tool or model | What we used it for |
|---|---|
| OpenAI Codex CLI, model gpt-6-astra | Writing code from our specs (faultctl, tools, schema, agent, action API), running the acceptance steps against the live demo |
| Claude Code with Claude Fable 5.1 and Claude Opus | Writing the specs and interfaces, reviewing and auditing the generated code, drafting the documents in `docs/` |
| ChatGPT | Background research on telemetry signatures of each fault type and the demo's metric and log field names |

The agent's own model, called at runtime:

| Provider | Role | Model id |
|---|---|---|
| OpenRouter API | Primary model for the agent's tool calls and diagnosis | `<fill from the report's agent.model>` |
| Google Gemini API | Fallback when the primary fails | `<fill>` |

## Third-party libraries

`<Fill from pyproject.toml and uv.lock before the freeze; delete any line not actually used.>`

| Library | Version | Used in | License |
|---|---|---|---|
| `requests` | `<ver>` | `faultctl/`, `tools/` | `<license>` |
| `fastapi` | `<ver>` | `action_api/` | `<license>` |
| `uvicorn` | `<ver>` | `action_api/` | `<license>` |
| `jsonschema` | `<ver>` | `schema/` | `<license>` |
| `pyyaml` | `<ver>` | `detect/`, `faultctl/` config | `<license>` |
| `pytest` | `<ver>` | `tests/` | `<license>` |
| `<LLM client library>` | `<ver>` | `agent/` | `<license>` |

Software we run but did not change:

| Software | Version | Role |
|---|---|---|
| OpenTelemetry Demo (Astronomy Shop) | 2.0.2, minimal mode | The application under test, cloned unmodified next to this repo |
| Docker Desktop with Compose v2 | `<ver>` | Runs the demo |
| alpine + iproute2 | `<ver>` | The `tc netem` helper image built from `faultctl/netem/Dockerfile` |

## Prior work

Some modules predate today and were reused with the mentors' permission. Each one, its origin and what changed today are listed in [`PRIOR_WORK.md`](PRIOR_WORK.md). Everything not listed there was written on Oct 23-24.
