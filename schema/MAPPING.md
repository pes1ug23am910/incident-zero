# Report field mapping

The team contract is primary. Without a supplied external schema, the adapter
returns an independent identity copy. Supplying a schema enables projection:
fields with the same name map directly, nested objects and arrays are projected
recursively, and fields absent from the external schema are dropped.

The table below is read by `schema.adapter`; update it when the organisers share
their actual names. These conventional aliases support a small test contract and
do not claim to be the organisers' schema. Explicit table mappings take priority
over matching names. Dot paths address nested fields.

| Ours | Theirs | Meaning |
| --- | --- | --- |
| * | * | Identity for fields retained by the external schema |
| incident_id | incidentId | Incident label supplied by the caller |
| detected_at | detectedAt | Detection timestamp |
| root_cause.component | component | Primary component |
| root_cause.cause | cause | Primary explanation |
| root_cause.confidence | confidence | Evidence-limited confidence |
| root_cause | diagnosis | Primary cause object |
| evidence | evidence | Retained evidence fields |
| status | status | Investigation status |

Required external fields without internal values receive `null` when nullable,
or `"not_available"` for strings. A warning records every substitution. If the
external schema exposes `adapter_notes`, the notes are included there; the export
CLI also writes a `.notes.json` sidecar. A required number, enum, or structured
value that does not permit an unavailable marker makes validation fail: the
adapter never invents data to satisfy another contract.

```powershell
python -m schema.export reports/<id>/report.json --schema <their.json>
```

The validated result is `report.external.json` beside the unchanged internal
`report.json`. Both belong in each bundle once an external schema exists.
