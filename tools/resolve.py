"""Re-fetch an evidence identifier; never accept the identifier as its own proof."""

import argparse
import json
import math
import re
from urllib.parse import quote

from .common import get_json, jaeger, prometheus, search_json
from .containers import inspect_rows, health_row, evidence_value
from .deploy import action_entries
from . import evidence as snapshots
from .redact import sanitize, scrub_trace, is_sensitive
from .queries import QUERIES, named_query


class EvidenceNotFound(ValueError):
    pass


def parse_metric(identifier):
    match = re.fullmatch(r"metric:([a-zA-Z_:][a-zA-Z0-9_:]*)\{(.*)\}@([\d.eE+-]+)=([\d.eE+-]+)", identifier)
    if not match:
        raise EvidenceNotFound("Malformed metric evidence identifier")
    name, text, timestamp, value = match.groups()
    labels = {}
    while text:
        pair = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)=("(?:[^"\\]|\\.)*")(?:,|$)', text)
        if not pair:
            raise EvidenceNotFound("Malformed metric labels")
        labels[pair[1]] = json.loads(pair[2])
        text = text[pair.end():]
    query = labels.pop("__query__", None)
    if query is None:
        selector = ",".join(f"{k}={json.dumps(v)}" for k, v in sorted(labels.items()))
        query = name + "{" + selector + "}"
    if is_sensitive(name) or is_sensitive(labels) or is_sensitive(query):
        raise EvidenceNotFound("Decoded metric identifier contains excluded telemetry")
    if query.startswith("named:") and query[6:] not in QUERIES:
        raise EvidenceNotFound("Unknown named metric evidence query")
    return name, labels, float(timestamp), float(value), query


def _resolve(evidence_id):
    if evidence_id.startswith(("trace:", "span:")):
        kind, identity = evidence_id.split(":", 1)
        trace_id, _, span_id = identity.partition("/")
        if not re.fullmatch(r"[a-fA-F0-9]{16,32}", trace_id) or (kind == "span" and not re.fullmatch(r"[a-fA-F0-9]{16}", span_id)):
            raise EvidenceNotFound("Malformed trace/span identifier")
        raw = get_json(jaeger() + "/traces/" + trace_id)
        trace = next((t for t in raw.get("data", []) if t.get("traceID") == trace_id), None)
        trace = scrub_trace(trace) if trace else None
        if trace:
            if kind == "trace":
                return {"id": evidence_id, "source": "jaeger", "data": trace}
            item = next((s for s in trace.get("spans", []) if s.get("spanID") == span_id), None)
            if item:
                return {"id": evidence_id, "source": "jaeger", "data": item}
    elif evidence_id.startswith("log:"):
        index, separator, document = evidence_id[4:].partition("/")
        if not separator or not index or not document or not re.fullmatch(r"[a-zA-Z0-9_-]+", index):
            raise EvidenceNotFound("Malformed log identifier")
        item = search_json(f"/{quote(index, safe='')}/_doc/{quote(document, safe='')}")
        if item.get("found") and item.get("_id") == document:
            return {"id": evidence_id, "source": "opensearch", "data": item["_source"]}
    elif evidence_id.startswith("metric:"):
        name, labels, timestamp, expected, query = parse_metric(evidence_id)
        expression = named_query(query[6:]) if query.startswith("named:") else query
        raw = get_json(prometheus() + "/api/v1/query_range", params={"query": expression, "start": timestamp, "end": timestamp, "step": 15})
        for series in raw.get("data", {}).get("result", []):
            actual_labels = {k: str(v) for k, v in series.get("metric", {}).items() if k != "__name__"}
            if actual_labels != labels:
                continue
            if name != "query" and series.get("metric", {}).get("__name__") != name:
                continue
            for ts, value in series.get("values", []):
                if abs(float(ts) - timestamp) < .001 and math.isclose(float(value), expected, rel_tol=1e-7, abs_tol=1e-10):
                    return {"id": evidence_id, "source": "prometheus", "data": {"metric": series["metric"], "timestamp": ts, "value": float(value), "query": query}}
    elif evidence_id.startswith("container:"):
        match = re.fullmatch(r"container:([^:]+):([^=]+)=(.*)", evidence_id)
        if not match:
            raise EvidenceNotFound("Malformed container identifier")
        name, field, expected = match.groups()
        if field not in {"Status", "RestartCount", "OOMKilled", "StartedAt", "Created", "NanoCpus", "Memory", "health"}:
            raise EvidenceNotFound("Unsupported container field")
        rows = inspect_rows([name])
        if rows:
            value = health_row(rows[0])[field]
            if evidence_value(value) == expected:
                return {"id": evidence_id, "source": "docker", "data": {"name": name, "field": field, "value": value}}
            raise EvidenceNotFound(f"Container evidence changed: {field} currently equals {value}")
    elif evidence_id.startswith("action_log:"):
        try:
            number = int(evidence_id.split(":", 1)[1])
        except ValueError as exc:
            raise EvidenceNotFound("Malformed action journal identifier") from exc
        for line, entry in action_entries():
            if line == number:
                return {"id": evidence_id, "source": "action_log", "data": entry}
    elif evidence_id.startswith("dlog:"):
        from .logs import resolve_docker_log
        match = re.fullmatch(r"dlog:([a-zA-Z0-9_.-]+):([a-f0-9]{64})", evidence_id)
        if not match:
            raise EvidenceNotFound("Malformed Docker log identifier")
        row = resolve_docker_log(*match.groups())
        if row:
            return {"id": evidence_id, "source": "docker", "data": row}
    raise EvidenceNotFound("Evidence was not found or its value no longer matches")


def resolve(evidence_id, *, run_dir=None, bundle_dir=None):
    try:
        source = snapshots.expected_source(evidence_id)
        if evidence_id.startswith("metric:"):
            _, _, timestamp, value, _ = parse_metric(evidence_id)
            if not math.isfinite(timestamp) or not math.isfinite(value):
                raise ValueError("Metric evidence values must be finite")
        if run_dir is not None:
            run_dir = snapshots.run_path(run_dir)
        if bundle_dir is not None:
            bundle_dir = snapshots.bundle_path(bundle_dir)
    except (ValueError, TypeError, OSError) as exc:
        raise EvidenceNotFound(str(exc)) from exc
    try:
        result = _resolve(evidence_id)
        if is_sensitive(result.get("data")) and evidence_id.startswith(("log:", "dlog:", "action_log:")):
            raise EvidenceNotFound("Evidence is excluded from diagnostic reads")
        result = sanitize(result)
        if result is None or result.get("data") is None or result.get("source") != source:
            raise EvidenceNotFound("Live evidence returned no matching safe payload")
        return {**result, "resolved_from": "live"}
    except Exception as exc:
        live_error = sanitize(str(exc)) or "[redacted]"
    try:
        result = snapshots.find_snapshot(evidence_id, run_dir=run_dir)
        return {**result, "live_error": live_error}
    except (ValueError, OSError) as exc:
        snapshot_error = sanitize(str(exc)) or "[redacted]"
    if bundle_dir is not None:
        try:
            result = snapshots.find_bundle_snapshot(evidence_id, bundle_dir)
            return {**result, "live_error": live_error, "run_snapshot_error": snapshot_error}
        except (ValueError, OSError) as exc:
            raise EvidenceNotFound(f"Could not re-fetch evidence: {live_error}; snapshot: {snapshot_error}; bundle: {exc}") from exc
    raise EvidenceNotFound(f"Could not re-fetch evidence: {live_error}; snapshot: {snapshot_error}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_id")
    parser.add_argument("--run-dir", help="restrict snapshot fallback to this run under runs")
    parser.add_argument("--bundle-dir", help="final fallback to one immediate report bundle under reports")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(resolve(args.evidence_id, run_dir=args.run_dir, bundle_dir=args.bundle_dir), indent=2))
        return 0
    except EvidenceNotFound as exc:
        print(json.dumps(sanitize({"id": args.evidence_id, "error": str(exc)})))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
