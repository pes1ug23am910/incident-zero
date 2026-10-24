# Team form

Incident Zero: Build an AI On-Call Engineer. Bosch BGSW hackathon, October 23-24,
2026. Team name, assigned team number and complete five-member roster: **not
verified**. Member identities/contributions below must be confirmed before freeze;
this document does not claim all five have committed.

| Member | SRN | Contribution evidence / current declaration |
|---|---|---|
| Yash Verma | PES1UG23AM910 | Repository integration; unpublished router-template adaptation declared in PRIOR_WORK; this branch's scripts, regression tests and documents use his configured Git identity |
| Preetham (full name not verified) | not verified | Parallel prototype and six port ideas listed in PRIOR_WORK; landing commits and event-day written confirmation not verified in this snapshot |
| Member 3: not verified | not verified | Completed contribution and commit not verified |
| Member 4: not verified | not verified | Completed contribution and commit not verified |
| Member 5: not verified | not verified | Completed contribution and commit not verified |

Proposed next work is in [LANES.md](LANES.md), not credited as already delivered.
Preetham's assigned lanes are per-operation detection, diagnosis-only campaign,
and Control Room stage/approval walkthrough. Each person must explain and change
their submitted part. Five-member code contribution and sign-off: not verified.

## Assistants and runtime models

| Tool / model | Declared use and evidence state |
|---|---|
| OpenAI Codex, GPT-6 family | Coding, scripts, tests and documentation; this docs/portability session. Exact backend model ID beyond the session family: not verified |
| OpenAI Codex CLI, gpt-6-astra | Earlier coding and acceptance work, per the previous team-form declaration; exact per-commit model attribution not verified |
| Claude Code, Claude Fable 5.1 and Claude Opus | Specs, review/audits and drafting, per earlier declaration; exact Opus version and activity log not verified |
| ChatGPT, exact model not verified | Background telemetry research, per earlier declaration |
| OpenRouter `openai/gpt-5` | Configured primary in `.env`; actual successful model recorded in retained `report.agent.model` and `llm.jsonl` |
| OpenRouter `google/gemini-2.5-pro` | Configured fallback in `.env`; failed routes disclosed in cache r2 |
| Direct Gemini / reviewer / fast model | Optional route/reserved configuration; an actual direct Gemini or reviewer invocation is not verified |
| Teammate's other assistants/models | not verified; Preetham must complete this declaration |

Model IDs were read without exposing credentials. The preflight's authenticated
OpenRouter probe succeeded; it does not establish every fallback route's health.
Assistants are declared here under the event rules, never as Git authors or
co-authors. Review of every line by its member and individual explanation sign-off
remain to be confirmed; they are not inferred from tool use.

## Third-party libraries

Version constraints come directly from `pyproject.toml`; there is no checked-in
lockfile. Installed transitive versions vary. License review for submission is
not verified in this session.

| Package | Declared constraint | Purpose |
|---|---|---|
| setuptools | >=68 | Build backend |
| requests | >=2.32,<3 | HTTP telemetry/provider calls |
| jsonschema | >=4.23,<5 | Report/schema validation |
| langgraph | >=1,<2 | Investigation/response graph |
| langgraph-checkpoint-sqlite | >=3,<4 | Durable graph checkpoints |
| PyYAML | >=6,<7 | Policy/configuration |
| fastapi | >=0.115,<1 | Local Action API / UI API |
| uvicorn | >=0.30,<1 | ASGI server |
| pytest | >=8,<10 (test extra) | Offline tests |
| httpx | >=0.27,<1 (test extra) | ASGI/API test client |

The official OpenTelemetry Demo, Docker/Compose, Prometheus, Jaeger, OpenSearch,
Locust and their images are third-party infrastructure, not team-authored code.
The knowledge fold may change package metadata; update this table from the final
`pyproject.toml` instead of copying the older branch's rank-bm25 declaration.
