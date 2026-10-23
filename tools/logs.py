"""Discover log mappings before filtering, rather than guessing field names."""

import json
import hashlib
import re
import subprocess
from urllib.parse import quote
from .common import bounded, envelope, search_json, log_index, window, BackendError, remaining
from .containers import container_names
from .redact import sanitize, is_sensitive

SEVERITIES = {"TRACE": 1, "DEBUG": 5, "INFO": 9, "WARN": 13, "ERROR": 17, "FATAL": 21}
STDOUT_SERVICES = {"checkout", "product-catalog", "shipping", "email", "frontend"}


def docker_log_lines(container, since=None, until=None, tail=1000):
    """Read both Docker output streams; diagnostic reads stay in the demo project."""
    if container not in container_names() or is_sensitive(container):
        raise ValueError("Container names must belong to the demo Compose project")
    args = ["docker", "logs", "--timestamps", "--tail", str(tail)]
    if since:
        args += ["--since", since]
    if until:
        args += ["--until", until]
    args.append(container)
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=remaining(), check=False)
    if result.returncode:
        raise BackendError(result.stderr.strip()[-500:] or "Docker log read failed")
    return (result.stdout + "\n" + result.stderr).splitlines()


def parse_docker_line(container, line):
    """Stable evidence hashes include the original Docker timestamp and body."""
    if is_sensitive(line):
        return None
    match = re.match(r"^(\d{4}-\d\d-\d\dT\S+)\s(.*)$", line)
    if not match:
        return None
    timestamp, body = match.groups()
    severity, trace_id = "UNKNOWN", None
    try:
        document = json.loads(body)
    except (ValueError, TypeError):
        document = {}
    if isinstance(document, dict):
        level = document.get("severity", document.get("level", document.get("severityText")))
        if isinstance(level, int):
            severity = {10: "TRACE", 20: "DEBUG", 30: "INFO", 40: "WARN", 50: "ERROR", 60: "FATAL"}.get(level, "UNKNOWN")
        elif isinstance(level, str):
            severity = {"WARNING": "WARN", "CRITICAL": "FATAL", "INFORMATION": "INFO"}.get(level.upper(), level.upper())
        trace_id = document.get("trace_id", document.get("traceId", document.get("traceID")))
    if severity not in SEVERITIES:
        found = re.search(r"(?i)\b(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\b", body)
        if found:
            severity = {"WARNING": "WARN", "CRITICAL": "FATAL"}.get(found[1].upper(), found[1].upper())
    digest = hashlib.sha256(line.encode("utf-8")).hexdigest()
    return {"timestamp": timestamp, "severity": severity, "body": body[:300],
            "trace_id": trace_id, "evidence_id": f"dlog:{container}:{digest}"}


def resolve_docker_log(container, line_hash):
    if not re.fullmatch(r"[a-f0-9]{64}", line_hash):
        raise ValueError("Malformed Docker log digest")
    for line in docker_log_lines(container, tail=5000):
        if hashlib.sha256(line.encode("utf-8")).hexdigest() == line_hash:
            return parse_docker_line(container, line)
    return None


def _docker_logs(service, pattern, span, severity_min, cap, limit):
    lines = docker_log_lines(service, span["from"], span["to"])
    rows = []
    for line in lines:
        row = parse_docker_line(service, line)
        if row is None or (pattern and pattern.casefold() not in line.casefold()):
            continue
        # Unclassified text is included only in an unfiltered TRACE request.
        if SEVERITIES.get(row["severity"], 0) < SEVERITIES[severity_min] and severity_min != "TRACE":
            continue
        rows.append(row)
    rows.sort(key=lambda row: row["timestamp"], reverse=True)
    data = rows[:cap]
    return envelope("get_logs", "docker", json.dumps({"container": service, "since": span["from"],
                    "until": span["to"], "severity_min": severity_min, "pattern": pattern}, sort_keys=True),
                    span, data, [row["evidence_id"] for row in data],
                    len(rows) > cap or len(lines) >= 1000 or limit > 100,
                    log_source="docker logs", warning="Application stdout/stderr fallback; unknown severity requires TRACE")


def flatten_mapping(properties, prefix=""):
    result = {}
    for name, spec in properties.items():
        path = f"{prefix}.{name}" if prefix else name
        if "properties" in spec:
            result.update(flatten_mapping(spec["properties"], path))
        else:
            result[path] = spec
    return result


def discover_fields(index):
    raw = search_json(f"/{quote(index, safe='')}/_mapping")
    mapping = raw.get(index, {}).get("mappings", {}).get("properties", {})
    fields = flatten_mapping(mapping)
    choices = {
        "service": ("resource.attributes.service.name", "resource.service.name", "resource.service@name", "service.name", "resource.attributes.service@name"),
        "time": ("time", "@timestamp", "timestamp", "observed_time", "observedTimestamp"),
        "severity": ("severity_number", "severityNumber", "severity.number"),
        "severity_text": ("severity_text", "severityText", "severity.text"),
        "body": ("body", "message"),
        "trace": ("trace_id", "traceId", "trace.id"),
    }
    found = {role: next((f for f in names if f in fields), None) for role, names in choices.items()}
    if not all(found[k] for k in ("service", "time", "body")):
        raise BackendError("Log mapping has no supported service/time/body fields; inspect the backend mapping")
    found["service_filter"] = found["service"]
    service_spec = fields[found["service"]]
    if service_spec.get("type") == "text" and "keyword" in service_spec.get("fields", {}):
        found["service_filter"] += ".keyword"
    if found["severity_text"]:
        severity_spec = fields[found["severity_text"]]
        found["severity_text_filter"] = found["severity_text"]
        if severity_spec.get("type") == "text" and "keyword" in severity_spec.get("fields", {}):
            found["severity_text_filter"] += ".keyword"
    return found


def field_value(document, path):
    if not path or not isinstance(document, dict):
        return None
    if path in document:
        return document[path]
    head, _, tail = path.partition(".")
    return field_value(document.get(head), tail) if tail else document.get(head)


@bounded("opensearch")
def get_logs(service, pattern=None, lookback_s=300, severity_min="WARN", limit=50):
    span = window(lookback_s)
    if is_sensitive(service) or (pattern and is_sensitive(pattern)):
        raise ValueError("This diagnostic source or pattern is excluded")
    if severity_min.upper() not in SEVERITIES:
        raise ValueError("severity_min must be TRACE, DEBUG, INFO, WARN, ERROR or FATAL")
    cap = max(1, min(int(limit), 100))
    if service in STDOUT_SERVICES:
        return _docker_logs(service, pattern, span, severity_min.upper(), cap, limit)
    index = log_index()
    fields = discover_fields(index)
    filters = [{"term": {fields["service_filter"]: service}},
               {"range": {fields["time"]: {"gte": span["from"], "lte": span["to"]}}}]
    if fields["severity"]:
        filters.append({"range": {fields["severity"]: {"gte": SEVERITIES[severity_min.upper()]}}})
    elif fields["severity_text"]:
        allowed = [name for name, number in SEVERITIES.items() if number >= SEVERITIES[severity_min.upper()]]
        filters.append({"terms": {fields["severity_text_filter"]: allowed + [a.lower() for a in allowed]}})
    else:
        raise BackendError("Log mapping has no severity field; severity filtering cannot be verified")
    if pattern:
        filters.append({"match_phrase": {fields["body"]: pattern}})
    query = {"size": cap, "query": {"bool": {"filter": filters}},
             "sort": [{fields["time"]: {"order": "desc"}}], "track_total_hits": True}
    raw = search_json(f"/{quote(index, safe='')}/_search", query)
    hits = raw.get("hits", {}).get("hits", [])
    total = raw.get("hits", {}).get("total", {})
    count = total.get("value", 0) if isinstance(total, dict) else total
    data, ids = [], []
    for hit in hits[:cap]:
        source = hit.get("_source", {})
        if is_sensitive(source):
            continue
        source = sanitize(source)
        if source is None:
            continue
        evidence = f'log:{hit.get("_index", index)}/{hit["_id"]}'
        data.append({"timestamp": field_value(source, fields["time"]),
                     "severity": field_value(source, fields["severity_text"]) or field_value(source, fields["severity"]),
                     "body": str(field_value(source, fields["body"]))[:300],
                     "trace_id": field_value(source, fields["trace"]), "evidence_id": evidence})
        ids.append(evidence)
    return envelope("get_logs", "opensearch", json.dumps(query, sort_keys=True), span, data, ids,
                    count > cap or len(hits) > cap or limit > 100)
