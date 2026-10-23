"""Recorded observations remain resolvable without trusting identifiers alone."""

import hashlib
import importlib
import json

import pytest

from tools import evidence
from tools.common import bounded, envelope, window

resolver = importlib.import_module("tools.resolve")


def recorded(identifier="container:payment:Status=running", source="docker", data=None, run_dir="recorded"):
    current, token = evidence.begin_run(run_dir)
    try:
        data = {"name": "payment", "field": "Status", "value": "running"} if data is None else data
        evidence.capture_evidence(identifier, source, data)
        result = envelope("example", source, "recorded observation", window(), [data], [identifier])
        return evidence.persist_envelope(result, current)
    finally:
        evidence.end_run(token)


def test_snapshot_contains_payload_original_identity_checksum_and_safe_filename():
    result = recorded()
    identifier = result["evidence_ids"][0]
    path = evidence.ROOT / result["evidence_paths"][identifier]
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == hashlib.sha256(identifier.encode()).hexdigest() + ".json"
    assert snapshot["id"] == identifier
    assert snapshot["data"]["value"] == "running"
    assert snapshot["source"] == "docker"
    assert len(snapshot["checksum"]) == 64
    assert evidence.load_snapshot(path, identifier)["resolved_from"] == "snapshot"


def test_first_capture_in_run_is_immutable():
    result = recorded("action_log:3", "action_log", {"action": "restart_service", "result": "initial"})
    path = evidence.ROOT / result["evidence_paths"]["action_log:3"]
    original = path.read_bytes()
    recorded("action_log:3", "action_log", {"action": "restart_service", "result": "changed"})
    assert path.read_bytes() == original


def test_live_evidence_is_preferred_over_snapshot(monkeypatch):
    result = recorded()
    identifier = result["evidence_ids"][0]
    monkeypatch.setattr(resolver, "_resolve", lambda _: {"id": identifier, "source": "docker", "data": {"value": "live"}})
    resolved = resolver.resolve(identifier, run_dir="recorded")
    assert resolved["resolved_from"] == "live"
    assert resolved["data"]["value"] == "live"


@pytest.mark.parametrize("failure", [ConnectionError("backend unavailable"), resolver.EvidenceNotFound("value changed"), resolver.EvidenceNotFound("expired trace")])
def test_failed_live_resolution_falls_back_to_snapshot(monkeypatch, failure):
    result = recorded()
    identifier = result["evidence_ids"][0]
    def unavailable(_):
        raise failure
    monkeypatch.setattr(resolver, "_resolve", unavailable)
    resolved = resolver.resolve(identifier, run_dir="recorded")
    assert resolved["resolved_from"] == "snapshot"
    assert resolved["data"]["value"] == "running"
    assert str(failure) in resolved["live_error"]
    assert resolved["snapshot_path"] == result["evidence_paths"][identifier]


def test_snapshot_search_without_run_only_visits_evidence(monkeypatch):
    result = recorded()
    identifier = result["evidence_ids"][0]
    outside = evidence.ROOT / "runs" / "other" / "operator.json"
    outside.parent.mkdir()
    outside.write_text("invalid JSON, deliberately not evidence", encoding="utf-8")
    monkeypatch.setattr(resolver, "_resolve", lambda _: (_ for _ in ()).throw(ConnectionError("offline")))
    assert resolver.resolve(identifier)["resolved_from"] == "snapshot"
    with pytest.raises(resolver.EvidenceNotFound):
        resolver.resolve(identifier, run_dir="other")


@pytest.mark.parametrize("mutation", ["checksum", "id", "source"])
def test_corrupt_or_mismatched_snapshots_are_rejected(monkeypatch, mutation):
    result = recorded()
    identifier = result["evidence_ids"][0]
    path = evidence.ROOT / result["evidence_paths"][identifier]
    record = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "checksum":
        record["data"]["value"] = "tampered"
    else:
        record[mutation] = "container:other:Status=running" if mutation == "id" else "jaeger"
        core = {key: value for key, value in record.items() if key != "checksum"}
        record["checksum"] = hashlib.sha256(evidence._canonical(core)).hexdigest()
    path.write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(resolver, "_resolve", lambda _: (_ for _ in ()).throw(ConnectionError("offline")))
    with pytest.raises(resolver.EvidenceNotFound, match="snapshot"):
        resolver.resolve(identifier, run_dir="recorded")


@pytest.mark.parametrize("run_dir", ["../escape", "runs/../escape", "runs/nested/child", "other/run", "."])
def test_run_paths_cannot_escape(run_dir):
    with pytest.raises(ValueError):
        evidence.begin_run(run_dir)


def test_absolute_run_inside_workspace_is_supported():
    target = evidence.ROOT / "runs" / "absolute"
    current, token = evidence.begin_run(target)
    try:
        assert current.path == target
        assert (target / "evidence").is_dir()
    finally:
        evidence.end_run(token)


def test_symlink_run_escape_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    runs = evidence.ROOT / "runs"
    runs.mkdir(exist_ok=True)
    link = runs / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not grant symbolic-link creation")
    with pytest.raises(ValueError):
        evidence.begin_run("linked")


def test_snapshot_strips_sensitive_span_tags_and_events():
    identifier = "trace:" + "a" * 32
    trace = {"traceID": "a" * 32, "processes": {"p1": {"serviceName": "payment"}}, "spans": [{
        "spanID": "b" * 16, "processID": "p1", "operationName": "charge",
        "tags": [{"key": "feature_flag.key", "value": "paymentFailure"}, {"key": "error", "value": True}],
        "logs": [{"fields": [{"key": "feature_flag.variant", "value": "on"}]}],
    }]}
    result = recorded(identifier, "jaeger", trace)
    content = (evidence.ROOT / result["evidence_paths"][identifier]).read_text(encoding="utf-8")
    assert "feature_flag" not in content and "paymentFailure" not in content
    assert '"error"' in content


@pytest.mark.parametrize("identifier,data", [
    ("log:otel/secret", {"body": "Feature Flag adHighCpu enabled"}),
    ("dlog:ad:" + "a" * 64, {"body": "feature_flag.key=adHighCpu"}),
    ("action_log:1", {"parameters": {"flag": "paymentFailure", "variant": "on"}}),
])
def test_disclosing_log_payloads_are_never_snapshotted(identifier, data):
    with pytest.raises(ValueError, match="excluded"):
        recorded(identifier, {"dlog": "docker", "log": "opensearch", "action_log": "action_log"}[identifier.split(":", 1)[0]], data)
    assert not list((evidence.ROOT / "runs").glob("*/evidence/*.json"))


def test_sensitive_and_malformed_ids_fail_before_backend_or_snapshot(monkeypatch):
    calls = []
    monkeypatch.setattr(resolver, "_resolve", lambda _: calls.append("backend"))
    monkeypatch.setattr(evidence, "find_snapshot", lambda *args, **kwargs: calls.append("snapshot"))
    for identifier in ("metric:feature_flag_total{}@1=1", "action_log:0", "trace:bad", "dlog:checkout:not-a-hash"):
        with pytest.raises(resolver.EvidenceNotFound):
            resolver.resolve(identifier)
    assert calls == []


def test_bounded_tools_create_default_and_explicit_run_folders():
    @bounded("docker")
    def sample():
        return envelope("sample", "docker", "read", window(), [{"name": "payment", "Status": "running"}], ["container:payment:Status=running"])
    automatic = sample()
    chosen = sample(run_dir="chosen")
    assert automatic["run_dir"].startswith("runs/")
    assert chosen["run_dir"] == "runs/chosen"
    for result in (automatic, chosen):
        assert len(result["evidence_paths"]) == len(result["evidence_ids"]) == 1
        assert all((evidence.ROOT / name).is_file() for name in result["evidence_paths"].values())


@pytest.mark.parametrize("identifier,source,data", [
    ("trace:" + "a" * 32, "jaeger", {"traceID": "a" * 32, "spans": [{"spanID": "b" * 16}]}),
    ("span:" + "a" * 32 + "/" + "b" * 16, "jaeger", {"spanID": "b" * 16, "operationName": "charge"}),
    ("log:otel/doc", "opensearch", {"body": "payment request failed"}),
    ("dlog:checkout:" + "c" * 64, "docker", {"body": "payment failed", "severity": "ERROR"}),
    ("metric:requests_total{}@100=5", "prometheus", {"metric": {"__name__": "requests_total"}, "timestamp": 100, "value": 5}),
    ("container:payment:Status=running", "docker", {"name": "payment", "field": "Status", "value": "running"}),
    ("action_log:3", "action_log", {"type": "restart_service", "target": "payment"}),
])
def test_all_evidence_types_persist_actual_data(identifier, source, data):
    result = recorded(identifier, source, data)
    snapshot = evidence.find_snapshot(identifier, run_dir=result["run_dir"])
    assert snapshot["source"] == source
    assert snapshot["data"] == data


def test_empty_tool_still_creates_evidence_directory():
    @bounded("jaeger")
    def empty():
        return envelope("empty", "jaeger", "services", window(), [])
    result = empty()
    assert result["evidence_paths"] == {}
    assert (evidence.ROOT / result["run_dir"] / "evidence").is_dir()


def test_failed_tool_reports_its_empty_evidence_directory():
    @bounded("jaeger")
    def unavailable():
        raise ValueError("backend unavailable")
    result = unavailable(run_dir="failed")
    assert result["error"]["message"] == "backend unavailable"
    assert result["run_dir"] == "runs/failed"
    assert result["evidence_paths"] == {}


def test_recorded_docker_line_must_match_its_identifier():
    line = "2026-10-23T00:00:00.000000000Z ERROR payment request failed"
    digest = hashlib.sha256(line.encode()).hexdigest()
    identifier = "dlog:checkout:" + digest
    recorded(identifier, "docker", {"body": "ERROR payment request failed", "original_line": line})
    assert evidence.find_snapshot(identifier)["data"]["original_line"] == line
    with pytest.raises(ValueError, match="digest"):
        recorded(identifier, "docker", {"body": "changed", "original_line": line + "changed"})


def test_resolver_cli_identifies_snapshot_origin(monkeypatch, capsys):
    result = recorded()
    identifier = result["evidence_ids"][0]
    monkeypatch.setattr(resolver, "_resolve", lambda _: (_ for _ in ()).throw(ConnectionError("offline")))
    assert resolver.main([identifier, "--run-dir", "recorded"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["resolved_from"] == "snapshot"
    assert response["snapshot_path"] == result["evidence_paths"][identifier]
