# Knowledge and retrieval: mentor page

The design has three layers: versioned procedures in Markdown runbooks, a service
dependency catalogue, and redacted records of earlier incidents. Retrieval brings
relevant sections into an investigation as cited hints. The diagnosis still needs
observations from the tools. Code selects the remedy from the diagnosed category
and component; a human must approve execution. No model weights change.

**Demo-stable integration:** the knowledge branch is merged, including optional
`retrieve_context` and `remember` graph nodes behind `INCIDENT_ZERO_KNOWLEDGE=1`.
The disabled path retains the integration-state investigation and response logic.
The local index build produced 15 runbooks, 23 catalogue entries and 143 chunks
before fresh memory records. See [BUILD_09](../BUILD_09.md) for current live results
and the selected demo flag. The full fold is deliberately excluded.

| Store / interface | What it contains or does | Required boundary |
|---|---|---|
| `knowledge/runbooks/*.md` | Symptoms, checks, confirmation, remediation, rollback, verification, prevention | Written by the team; no incident IDs or control-setting names |
| `knowledge/services.yaml` | Compose service purposes and dependencies | Dependency catalogue, not a knowledge graph |
| `knowledge/index.sqlite` | Local section-level search index | SQLite persistence and rank-bm25 ranking; FTS5 migration is excluded |
| `memory/store/*.json` | Telemetry fingerprint, diagnosis, actual action and verification outcome | Opaque SHA-256 IDs stable across response updates; source IDs and report paths are not retained |
| `knowledge_consulted` / citation fields | Retrieved references and limitations | Hints cannot enter telemetry evidence; per-hint verdict fields are not implemented on this line |

Retrieve at observation and proposal, with hints framed as untrusted data. The
merged implementation includes a cited planning call checked against the policy
allowlist. `kb:` and `mem:` IDs are rejected in telemetry evidence fields. Memory
storage and retrieval cannot retain the operator's incident label or report path;
the former opaque-memory expected failure now passes. The remaining knowledge
addendum, including retrieval sizing changes and verdict rendering, is deferred.

After the merge, with the environment installed:

```text
python -m knowledge build
python -m knowledge search "cart errors connection refused"
python -m knowledge explain reports/payment-failure-r6/report.json
python -m pytest -q -m "not live" --basetemp=.build/pytest
```

These commands are available on demo-stable. No embedding download is required.
Wrong-hint live behavior and a controlled retrieval ablation remain **not verified**.
Use the flag selected from the fresh repetitions in BUILD_09; repeated cases are
not evidence of improved unseen-incident accuracy.

## Six mentor questions

1. **Is it RAG or a database?** Both describe different parts: inspectable files
   and a SQLite index store knowledge; retrieval supplies selected, cited text to
   the model. It is not fine-tuning.
2. **Why retrieve if all runbooks fit in a prompt?** Section citations and bounded
   context make it easier to inspect what influenced a decision. We have not
   measured whether this beats supplying every runbook.
3. **Are runbooks hard-coded practice answers?** They describe failure categories,
   checks and safe remedies. They must contain neither injection labels nor flag
   settings. Evidence must still establish the component and mechanism.
4. **What if memory is wrong?** Treat it as a hypothesis, seek current evidence,
   record its verdict, and escalate when corroboration is insufficient. A live
   wrong-hint demonstration is not verified; do not describe it as completed.
5. **Does retrieval help?** That is not verified. The nine-run, leave-one-family-out
   protocol and empty measurement cells are in [EVALUATION_NOTE.md](EVALUATION_NOTE.md).
   Repeated-incident lookup is a separate experiment, not unseen-incident accuracy.
6. **Can knowledge be poisoned?** Yes. Untrusted-data framing, redaction, evidence
   validation, closed action labels and approval reduce risk; they do not prove
   immunity. Store structured observations and outcomes, including failed fixes.

For unseen incidents, general procedures may guide useful checks; memory can be
irrelevant. On repeats it can supply a precedent, never proof of the current
cause or recovery. Do not claim the agent learns or self-improves, that retrieval
prevents hallucination or improves accuracy, that memory helps unseen incidents,
that dense retrieval beats BM25, or that this is production-ready. Do not present
another team's or a research paper's numbers as our measurements. The team wrote
the runbooks; they are not Bosch or OpenTelemetry endorsed procedures.
