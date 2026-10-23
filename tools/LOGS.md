# Confirmed log sources

On 2026-10-23, after the Docker API compatibility setting was repaired, the
running unmodified minimal demo 2.0.2 supplied the `otel` OpenSearch index.
`GET /otel/_mapping` and real documents confirmed these fields:

| Meaning | Exact field |
| --- | --- |
| Service | `resource.service.name`; exact filter `resource.service.name.keyword` |
| Severity | `severity.text`, `severity.text.keyword`, `severity.number` |
| Body | `body` |
| Trace / span | `traceId`, `spanId` |
| Event time | `@timestamp` |
| Export observation time | `observedTimestamp` |
| Attributes / scope | `attributes`, `instrumentationScope.name` |

The service aggregation contained frontend-proxy, cart, currency, ad,
recommendation, and quote (5,793 total documents at the first discovery).
The recorded ad document in `tests/fixtures/recorded_log.json` includes its
original document ID and capture provenance. Its benign body is retained by
the redaction test. Synthetic disclosure variants are separately labelled.

Queries use the discovered service keyword field, `@timestamp` bounds, numeric
severity (`>=13` WARN, `>=17` ERROR), and a body phrase when supplied. Mapping
discovery runs on each OpenSearch call; unsupported mappings produce an error.
The current published port is discovered with `docker port opensearch 9200`.
Without a published port, a read-only in-container HTTP request is used.

Checkout, product-catalog, shipping, email, and frontend emit application logs
to container stdout/stderr. `get_logs` uses the Docker fallback for those known
services, reads both streams, and limits reads to the demo Compose project.
Docker timestamps bound the request; JSON and textual severity are recognized.
Unclassified text is returned only with `--severity-min TRACE` so an ERROR query
does not pretend to classify it. The evidence form is
`dlog:<container>:<sha256-of-original-timestamped-line>`; resolution searches the
latest 5,000 retained lines and snapshot resolution can preserve older proof.

Every log source is scrubbed before truncation. Revealing lines are dropped;
ordinary operational exceptions remain available. Responses contain at most
100 lines and bodies at most 300 characters. The Docker read is capped at
1,000 input lines and reports truncation if that cap is reached.

```powershell
.\.venv\Scripts\python.exe -m tools.cli get_logs payment --severity-min WARN
.\.venv\Scripts\python.exe -m tools.cli get_logs checkout --severity-min TRACE
```
