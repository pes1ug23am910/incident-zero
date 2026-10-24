# Knowledge and retrieval: mentor page

The design has three layers: versioned procedures in Markdown runbooks, a service
dependency catalogue, and redacted records of earlier incidents. Retrieval brings
relevant sections into an investigation as cited hints. The diagnosis still needs
observations from the tools. Code selects the remedy from the diagnosed category
and component; a human must approve execution. No model weights change.

**Integration status:** the separate knowledge branch implements runbooks,
catalogue, index, memory and optional graph nodes. They are absent from this
`docsport` source snapshot. The fold owns their merge and corrections. Its
historical `BUILD_07.md` records 15 runbooks, 23 catalogue entries, 143 chunks and
694 passing offline tests with 3 skips; these are branch records, not a current
merged-build or live acceptance result. Verify after merge with the commands below.

| Store / interface | What it contains or does | Required boundary |
|---|---|---|
| `knowledge/runbooks/*.md` | Symptoms, checks, confirmation, remediation, rollback, verification, prevention | Written by the team; no incident IDs or control-setting names |
| `knowledge/services.yaml` | Compose service purposes and dependencies | Dependency catalogue, not a knowledge graph |
| `knowledge/index.sqlite` | Local section-level search index | Fold target: SQLite FTS5/BM25 only; the older branch used rank-bm25 |
| `memory/store/*.json` | Telemetry fingerprint, diagnosis, actual action and verification outcome | Opaque IDs; no report paths, run-folder labels or injected-answer IDs |
| `knowledge_consulted` / citation fields | What was retrieved and whether checked | `confirmed`, `refuted` or `not_checked`; hints cannot increase evidence confidence |

Retrieve at observation and proposal: at most three runbook sections and three
relevant memories, each at most 600 characters, framed as untrusted data. The
runbook explains and cross-checks the remedy; `agent.policy.select_action()`
continues to choose it. Disagreement becomes a limitation. `kb:` and `mem:` IDs
must be rejected in telemetry evidence fields. The existing validator rejection
is exercised by `tests/test_regressions_oct23.py`; opaque memory storage remains
a strict expected failure until the fold lands it.

After the merge, with the environment installed:

```text
python -m knowledge build
python -m knowledge search "cart errors connection refused"
python -m knowledge explain reports/payment-failure-r6/report.json
python -m pytest -q -m "not live" --basetemp=.build/pytest
```

The first three commands are unavailable before the merge. Build/index timing,
wrong-hint live behavior, merged report fields and live memory write-back are
**not verified** here. Keep `INCIDENT_ZERO_KNOWLEDGE=0` until the fold validates
the three Checkpoint 2 incidents with retrieval enabled. Then the operator may
set `INCIDENT_ZERO_KNOWLEDGE=1`; no embedding download is required by the target.

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
