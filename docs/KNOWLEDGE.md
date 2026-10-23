# Incident knowledge and memory

The agent retrieves operational guidance before investigating and again before proposing a remedy. Enable it with `INCIDENT_ZERO_KNOWLEDGE=1`; the default graph keeps its existing behavior. Retrieval supplies hints with provenance. Telemetry evidence and the policy allowlist still determine what the agent may conclude and propose.

| Location | Contents |
| --- | --- |
| `knowledge/runbooks/*.md` | Versioned SRE guidance: symptoms, named tool queries, confirmation, allowed remediation, rollback, verification, prevention and pitfalls. |
| `knowledge/services.yaml` | Service dependencies generated from a read-only Compose configuration, plus reviewed purpose, criticality and operational guidance. |
| `knowledge/index.sqlite` | Rebuildable SQLite chunks, term frequencies and source file/section/version/hash. |
| `memory/store/*.json` | One redacted record per validated incident: observed symptoms, diagnosed cause, actual action, verified outcome, recovery time when known, prompt hash and report provenance. |
| `reports/<id>/report.json` | Exact consulted snippets in `runbook_refs`, `memory_refs` and `knowledge_consulted`; also visible in Markdown and the Control Room. |

Build with `python -m knowledge build`; inspect with `python -m knowledge search "cart errors connection refused"` or `python -m knowledge explain reports/<id>/report.json`. `INCIDENT_ZERO_KNOWLEDGE_INDEX` and `INCIDENT_ZERO_MEMORY_DIR` isolate experimental stores. The shipped retrieval mode is BM25 through `rank-bm25`; it does not download an embedding model. SQLite has space for optional vectors, but this build makes no dense-retrieval claim.

The first query comes from anomalous services, signals and redacted observed errors. The second uses the evidence-backed cause and component. Each stage returns up to three runbooks, three prior incidents and one service entry, with `kb:` or `mem:` citations and relevance scores. Runbooks are sectioned so initial investigation receives checks and planning receives allowed remediation. Similarity is not diagnosis confidence.

The index builder reads only the runbook directory, catalogue and redacted memory. It does not read incident injection records, expected answers, evaluation fixtures or operator labels as diagnostic inputs. Stored text passes through redaction. Retrieved content stays inside the model's untrusted telemetry block and never enters the evidence registry. The wrong-hint test supplies a misleading payment memory while evidence supports a stopped recommendation container; evidence wins and the report records the disagreement. Policy also rejects a runbook remedy outside the allowlist and logs the conflict.

After a terminal report, the agent validates against retained evidence, writes its redacted memory record and immediately indexes it. A diagnosis paused for approval is not remembered as a finished incident. Repeated writes update that incident's outcome. A proposed action is not recorded as executed; escalation, rollback and unknown recovery remain explicit. This is retrieval from prior outcomes, not model training.

Run `python -m eval.knowledge_ablation --output .build/knowledge-ablation.json` for the offline comparison. It validates the three retained reports, builds a temporary index with **empty memory**, and measures retrieval. Existing decisions and their metrics are frozen; equal on/off values are expected and cannot demonstrate an improvement.

| Retained case | Component | Confidence | Recorded tool calls | Recorded seconds | Fresh live off/on |
| --- | --- | ---: | ---: | ---: | --- |
| Payment failure | payment | 0.90 | 3 | 57.828 | Pending |
| Stopped container | recommendation | 0.90 | 3 | 93.500 | Pending |
| Cache unavailable | valkey-cart | 0.55 | 6 | 208.219 | Pending |

`BUILD_07.md` gives the integration owner the live commands: compare the same three cases with retrieval off/on, holding the model and clean baseline constant and using a fresh empty memory for each case. Separately, repeat payment failure with the first result retained to test memory reuse. Report component, confidence, tool calls and seconds honestly, including ties or regressions. No live acceptance or improvement claim was made in the knowledge worktree.
