# Team contract: fix the interfaces first, then build in parallel (10-minute agreement)

Purpose: two members have templates. Instead of two full builds followed by a merge, both build to the same contract so "merge" means picking modules, and the other three members build contract pieces that are independent of either template. Decide the base with the bake-off in §4, not by argument.

## 1. Repository layout (one team repo, created today; no imported git history)

```
faultctl/      inject | reset | list            (team-built; the organisers' hidden test may use its own)
tools/         read-only eyes: metrics, traces, logs, container health, deploy history
agent/         brain: tool-calling loop, evidence, confidence, abstain, schema output
action_api/    hands: allowlist, dry-run, approval token, kill switch, append-only log
detect/        alert watcher on Prometheus thresholds -> alert.json
schema/        the provided JSON schema + validator (placeholder until the schema is shared)
reports/       one JSON + one Markdown per incident run
docs/          ARCHITECTURE.md (one page), EVALUATION_NOTE.md, TEAM_FORM.md, README.md
runs/          timestamped run folders (ground truth lives OUTSIDE the agent's import path)
```

Hygiene before the first push: no `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.codex/`, `.build/`, prompt files, jury reports, session logs or pack bundles. Declare the AI assistants in `docs/TEAM_FORM.md`, not in the repo tree. Commits today only, each member under their own name.

## 2. Interfaces (freeze these now; implementations may differ)

### faultctl
- `faultctl list` → the practice incident ids (use the organisers' ids verbatim once published).
- `faultctl inject <incident_id>` → sets the flag (flagd) or applies the docker fault; writes `runs/<ts>/injected.json` (ground truth; the agent never reads it).
- `faultctl reset` → all flags off, all containers up with original limits, netem cleared; exit 0 only after positive read-back.
- Infra primitives: `docker stop|restart`, `docker pause`, `docker update --cpus --memory`, stop `valkey-cart`, `tc netem` via a NET_ADMIN sidecar.

### tools (each returns JSON: `{source, query, window, data, evidence_ids}`)
- `get_metrics(promql, lookback_s)` → Prometheus `:9090/api/v1/query_range`
- `get_traces(service, lookback_s, errors_only)` → Jaeger via the frontend proxy `http://localhost:8080/jaeger/ui/api/traces` (the container port is ephemeral on the host)
- `get_logs(service, pattern, lookback_s)` → OpenSearch index `otel` (`docker port opensearch 9200` for the host port)
- `get_container_health()` → docker inspect/stats: status, restart count, OOM, cpu/mem limits
- `get_deploy_history()` → action_api log + container created timestamps
- Forbidden inside `tools/`, `agent/`, `detect/`: any read of flagd (`:8013`, `:8016`, `demo.flagd.json`, flag UI `:4000`). Add a test that greps for these. The demo's own spans carry `feature_flag.key`/`feature_flag.variant` and flagd exports its own telemetry: `tools/redact.py` strips both from every tool result, so the diagnosis never sees a flag name.

### evidence ids (so reports can be checked against the data)
`trace:<trace_id>` · `span:<trace_id>/<span_id>` · `log:<index>/<doc_id>` · `metric:<name>{labels}@<ts>=<value>` · `container:<name>:<field>=<value>` · `action_log:<line_no>`. Every evidence payload is snapshotted at tool time (`runs/<ts>/evidence/`) because Jaeger, Prometheus and OpenSearch keep little history; `resolve` falls back to the snapshot.

### agent
- `python -m agent run --alert runs/<ts>/alert.json --out reports/<incident>.json`
- Loop: pick the next tool from the findings so far (never dump everything into one prompt); stop when confidence ≥ threshold or budget (N tool calls) is spent.
- Output: our schema (SPEC_03; the organisers do not provide one). The incident id is passed by the caller (`--incident-id`), never through the prompt. The placeholder carries: `incident_id, detected_at, symptoms[], root_cause{component, cause, confidence}, evidence[] (ids above), proposed_action{type, target, reason} | null, status ∈ {diagnosed, needs_human, fixed, rolled_back}`.
- Abstain path: `status=needs_human` with findings is a valid, scored outcome.

### action_api
- `POST /actions/dry-run` → plan + predicted effect, no change.
- `POST /actions/execute` → requires `approval_token` issued by a human step; allowlist only: `restart_service`, `toggle_flag`, `throttle_load`; everything appended to `action_api/log.jsonl`.
- `POST /stop` and a root `STOP` file → every executor refuses while present; `clear-stop` only by a human.
- Verify step: re-query the alert condition; on no recovery → rollback → `needs_human`.

### detect
- Poller every 10 s: per-service error rate and p95 latency from spanmetrics; thresholds in `detect/thresholds.yaml`; writes `alert.json` and starts the agent.

## 3. Lanes right now (nobody waits for the merge)

| Lane | Owner | Independent of the base? |
|---|---|---|
| Official demo up (minimal compose), faultctl inject/reset with read-back | member 3 | yes |
| tools/: the five read tools against the live demo, with evidence ids | member 4 | yes |
| schema/ validator + report renderer (JSON → Markdown), docs skeletons, ARCHITECTURE sketch for Checkpoint 1 | member 5 | yes |
| agent/ loop on top of tools/ | template owner A (Yash) | contract-bound |
| action_api/ + detect/ | template owner B | contract-bound |

## 4. Bake-off to choose the base (15 minutes, at an agreed time, before Checkpoint 1)

Both templates run the same incident on the **official, unmodified** demo: `faultctl inject paymentFailure` → agent output. Score each on: (1) runs on the official demo without config edits; (2) emits the schema with real evidence ids; (3) has an approval gate and a working STOP; (4) time to diagnosis; (5) how many of the seven stages exist. Higher count wins and becomes `agent/` + `action_api/`; the other owner ports their strongest module into the contract within 30 minutes. No wholesale merge.

## 5. Declaration (README "Prior work" + TEAM_FORM)

Mentors allowed reuse of unpublished prior code. State it plainly: which modules predate today (author, unpublished), which were built today, which AI assistants were used for what. Honesty is scored (rule 7).
