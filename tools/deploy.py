"""Recent container start/create timestamps and the local action journal."""

from datetime import datetime
import json
from .common import ROOT, bounded, envelope, window
from .containers import inspect_rows
from .evidence import capture_evidence
from .redact import is_sensitive


def action_entries():
    path = ROOT / "action_api" / "log.jsonl"
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Action journal line {number} is not valid JSON") from exc
            entries.append((number, record))
    return entries


@bounded("action_log")
def get_deploy_history(lookback_s=3600):
    span = window(lookback_s)
    start, end = (datetime.fromisoformat(span[k]) for k in ("from", "to"))
    events = []
    def include(timestamp):
        if not timestamp:
            return False
        try:
            return start <= datetime.fromisoformat(timestamp.replace("Z", "+00:00")) <= end
        except (ValueError, TypeError):
            return False
    for item in inspect_rows():
        name = item["Name"].lstrip("/")
        for field, timestamp in (("Created", item["Created"]), ("StartedAt", item["State"].get("StartedAt"))):
            if include(timestamp):
                events.append({"timestamp": timestamp, "kind": field, "container": name,
                               "evidence_id": f"container:{name}:{field}={timestamp}"})
    for line, record in action_entries():
        if is_sensitive(record):
            continue
        timestamp = next((record[k] for k in ("timestamp", "at", "executed_at", "started_at", "created_at", "ts") if record.get(k)), None)
        if include(timestamp):
            events.append({"timestamp": timestamp, "kind": "action", "record": record,
                           "evidence_id": f"action_log:{line}"})
    events.sort(key=lambda e: datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")), reverse=True)
    for event in events[:100]:
        if event["kind"] == "action":
            capture_evidence(event["evidence_id"], "action_log", event["record"])
        else:
            capture_evidence(event["evidence_id"], "docker", {"name": event["container"],
                             "field": event["kind"], "value": event["timestamp"]})
    return envelope("get_deploy_history", "action_log", "container Created/StartedAt + action journal", span,
                    events[:100], [e["evidence_id"] for e in events[:100]], len(events) > 100)
