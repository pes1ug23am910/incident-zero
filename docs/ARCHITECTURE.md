# Architecture

One page: the parts, how an alert becomes a report, how the agent picks its next step, and what stops it from doing harm. Anything marked (planned) does not exist yet. The status table at the end is the source of truth.

## The picture

```
            OpenTelemetry Demo 2.0.2, minimal mode, unmodified, Docker Compose
  traces -> Jaeger | metrics -> Prometheus | logs -> OpenSearch | docker inspect / stats
                                   |
                                   v  read only, capped, every result carries evidence ids
  +-------------------------------- tools/ ---------------------------------------+
  | health_table  get_metrics  get_traces  get_logs  get_container_health          |
  | get_deploy_history  resolve                                                    |
  +---------------------------------------------------------------------------------+
       ^ thresholds              ^ one tool per step             ^ re-check the alert signal
       |                         |                               |
  detect/ --alert.json--> agent/run --draft--> schema/validate --> reports/<id>.json + .md
                                                     |
                                                     v
        agent/respond: dry run -> human says yes (token) -> action_api execute -> verify
                                                     |                            |
                                         action_api/log.jsonl          not recovered: rollback,
                                                                        status rolled_back
  STOP (file or POST /stop): detect, agent, action_api and faultctl all refuse while it exists.
  faultctl/ injects and resets incidents. Nothing above imports it or reads runs/*/injected.json.
```

## Components

| Part | What it does |
|---|---|
| `faultctl/` | Injects the practice incidents (demo failure flags and Docker faults), `--combo` for two at once, `reset` with read-back, `status` ready check. Ground truth goes to `runs/<ts>/injected.json`. |
| `tools/` | Read-only eyes. Every tool returns `{tool, source, query, window, data, evidence_ids, truncated}`. Caps: 50 traces, 100 log lines, 20 series of 200 points. A wider question means a narrower second call, never a dump. |
| `detect/` | Polls every 10 s. Fires on error rate >= 5 % over 1 min, p95 >= 1500 ms, a container not running, +2 restarts in 5 min, OOMKilled, or frontend rps >= 3x its 10-min baseline. One alert per service per 3 min. |
| `agent/` | `run`: the investigation loop and the report. `respond`: dry run, approval, execute, verify, update the report. |
| `action_api/` | FastAPI on `localhost:8787`. The only path by which the agent changes the system. |
| `schema/`, `reports/` | JSON Schema (draft 2020-12, `additionalProperties: false`), a validator with cross-field rules, a Markdown renderer. |

## From alert to report

1. A fault happens. In practice runs `faultctl` injects it; in the hidden test the organisers do. Nothing downstream knows how.
2. `detect/` sees a threshold crossed in telemetry, writes `runs/<ts>/alert.json` (signal, service, observed, threshold, window, baseline) and starts `python -m agent.run`.
3. The agent investigates (next section) and writes the report: symptoms, every investigation step with its reason, root cause with category and confidence, the evidence list, and a proposed action that is not executed.
4. `schema/validate` checks the report; `reports/render` writes the Markdown next to it.
5. `python -m agent.respond --report <file>`: dry run, then the diagnosis and plan go to a human. Only a "yes" yields a token. Execute, verify, and the same report gets `approval`, `action`, `verification` and its final `status` (`fixed`, `rolled_back`, `needs_human`, `aborted`).
6. Every Action API call is appended to `action_api/log.jsonl`. `get_deploy_history` reads it, so the next investigation sees what we changed.

## How the agent decides what to call next

- State: the alert, findings so far, evidence ids seen, up to two hypotheses (category, confidence, supporting and contradicting ids), calls used.
- The first call is always `health_table`: one row per service with error rate, p95, rps, restarts, status, CPU and memory.
- After that the model returns exactly one structured tool call and a one-sentence reason. The result is compacted under the caps and appended to the findings. The model updates its hypotheses and must quote evidence ids for every claim.
- The prompt teaches eight cause categories as telemetry patterns: `application_flag`, `container_down`, `restart_loop`, `dependency_unavailable`, `network`, `resource_starvation`, `load`, `unknown`. It knows the service names and the allowlist. It never sees an incident id, a flag name, or the word faultctl.
- It stops when a hypothesis reaches 0.75 backed by two independent sources (traces and logs, or metrics and container health), when 12 calls are spent, or when STOP appears.
- Confidence below 0.6 means `status = needs_human` with an escalation note: what we found, what is uncertain, what a person should check.
- Cause to action: `toggle_flag` for application causes, `restart_service` for container down, restart loop or OOM, `throttle_load` for load, `none` plus escalation for network and resource starvation (nothing on the allowlist fixes those).
- Model: OpenRouter first, Gemini as fallback, temperature 0. Every request and response goes to `runs/<ts>/llm.jsonl` without keys. Model used in our runs: `<fill>`.

## Evidence ids

| Id | Names |
|---|---|
| `trace:<trace_id>` | one Jaeger trace |
| `span:<trace_id>/<span_id>` | the error span inside it |
| `log:otel/<doc_id>` | one OpenSearch log document |
| `metric:<name>{<labels>}@<ts>=<value>` | the peak point of one series |
| `container:<name>:<field>=<value>` | one `docker inspect` or `docker stats` field |
| `action_log:<line_no>` | one line of our action log |

The report builder rejects any id that no tool returned in this run, so the model cannot invent evidence. The validator requires every cited id to appear in `evidence[]`. `python -m tools.resolve "<id>"` fetches it again. Limit: Jaeger keeps 5,000 traces in memory, Prometheus keeps one hour, OpenSearch has no volume. Old ids stop resolving, so each evidence entry also stores a summary and the query that produced it (`raw_ref`).

## Safety controls

- **Allowlist.** `restart_service`, `toggle_flag`, `throttle_load`. `scale_service` answers `not_available_on_compose`. Anything else is refused.
- **Dry run.** `POST /actions/dry-run` returns the plan, the predicted effect, preconditions and a world-state hash. It changes nothing; a test compares container ids and the flag-file hash before and after.
- **Approval token bound to world state.** Issued only when a human answers yes. It carries the hash of container ids plus the flag file and expires after 10 minutes. Execute without a token: 403. World changed since approval: 409.
- **STOP kill switch.** `POST /stop` or a `STOP` file in the repo root. While it exists the executor answers 423, the agent stops (`stopped_because = stop_signal`, `status = aborted`), `detect/` starts nothing, `faultctl` injects nothing. Clearing it takes `DELETE /stop` with an operator phrase.
- **Verify and rollback.** 30 s after acting we re-run the alert's own query. Recovered means below threshold on two samples in a row. Not recovered in 120 s: `toggle_flag` restores the previous variant, `throttle_load` restores the previous user count, `restart_service` has nothing to undo, so we escalate. Status becomes `rolled_back`.
- **Action log.** Append-only `action_api/log.jsonl`: time, actor, action, target, parameters, token, result, duration.
- **Test-only approval bypass.** `--auto-approve-for-tests` works only with `INCIDENT_ZERO_TEST=1` and prints a banner. Never used in a demo.

## What the agent must not read

- **The flag settings**: flagd files, the flag API (ports 8013, 8016, `ofrep`) and the flag UI (4000). `tests/test_no_flag_reads.py` scans production modules with exact exemptions for `faultctl/`, the filter-only `tools/redact.py`, and future `action_api/flags.py`; it also rejects disclosure keys and known control names. `tests/test_agent_isolation.py` fails if anything outside `faultctl/` imports it or reads `runs/*/injected.json`. The validator rejects any report containing `flagd`, `demo.flagd.json` or `defaultVariant`.
- **Flag names that leak into telemetry.** `tools/redact.py` removes revealing span tags, events, log lines, backend spans and control metrics before responses or snapshots are produced. `tests/test_redact.py` covers recorded telemetry and explicit disclosure variants. Docker liveness and resource metadata still includes all 21 containers; it does not read their settings.
- **The one exception.** `action_api/flags.py` writes the flag file for `toggle_flag` and its rollback, the way the flag UI would. It is reached only through the Action API after approval.

A source scan is a tripwire, not a proof. The operator owns injection; the redactor only filters already-read telemetry; the future Action API's setting adapter remains a separate boundary.

## Status

<!-- Builder: change a row to "built" or "verified live (run id)" only when its acceptance step has passed. -->

| Part | Status |
|---|---|
| faultctl, demo bring-up | Verified live; injections and resets recorded in BUILD_01B.md |
| tools, health_table, resolve | Verified live; retained snapshots and explicit live/snapshot resolution |
| schema, validator, renderer | Built; 56 schema tests pass; CLI examples checked |
| detect, agent run | (planned) |
| action_api, agent respond, verify, rollback | (planned) |
| telemetry redaction of flag attributes | Built; recorded span/log fixtures and source-boundary regressions pass |
| stretch: calibration, memory, reviewer agent, approval web page, prevention | (planned) |
