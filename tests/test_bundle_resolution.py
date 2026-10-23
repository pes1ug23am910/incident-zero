"""Committed report bundles retain independently checked evidence after expiry."""

import hashlib
import importlib
import json
from pathlib import Path
import shutil

import pytest

from tools import evidence
from tools.common import envelope, window

resolver = importlib.import_module("tools.resolve")
IDENTITY = "container:payment:Status=running"


def recorded_bundle(name="sample"):
    current, token = evidence.begin_run("original")
    try:
        data = {"name": "payment", "field": "Status", "value": "running"}
        evidence.capture_evidence(IDENTITY, "docker", data)
        result = evidence.persist_envelope(envelope("sample", "docker", "read", window(), [data], [IDENTITY]), current)
    finally:
        evidence.end_run(token)
    source = evidence.ROOT / result["evidence_paths"][IDENTITY]
    target = evidence.bundle_snapshot_path(name, IDENTITY)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return source, target


def unavailable(_):
    raise ConnectionError("backend expired")


def test_bundle_fallback_after_run_snapshot_expiry(monkeypatch):
    source, target = recorded_bundle()
    source.unlink()
    monkeypatch.setattr(resolver, "_resolve", unavailable)
    result = resolver.resolve(IDENTITY, run_dir="original", bundle_dir="reports/sample")
    assert result["resolved_from"] == "bundle_snapshot"
    assert result["snapshot_path"] == target.relative_to(evidence.ROOT).as_posix()
    assert result["data"]["value"] == "running"
    assert "backend expired" in result["live_error"]
    assert "run_snapshot_error" in result


def test_live_then_run_then_bundle_priority(monkeypatch):
    recorded_bundle()
    monkeypatch.setattr(resolver, "_resolve", lambda _: {"id": IDENTITY, "source": "docker", "data": {"value": "live"}})
    assert resolver.resolve(IDENTITY, run_dir="original", bundle_dir="sample")["resolved_from"] == "live"
    monkeypatch.setattr(resolver, "_resolve", unavailable)
    assert resolver.resolve(IDENTITY, run_dir="original", bundle_dir="sample")["resolved_from"] == "snapshot"


def test_only_selected_bundle_is_considered(monkeypatch):
    source, _ = recorded_bundle("other")
    source.unlink()
    monkeypatch.setattr(resolver, "_resolve", unavailable)
    with pytest.raises(resolver.EvidenceNotFound, match="bundle"):
        resolver.resolve(IDENTITY, run_dir="original", bundle_dir="selected")
    with pytest.raises(resolver.EvidenceNotFound):
        resolver.resolve(IDENTITY, run_dir="original")


@pytest.mark.parametrize("directory", ["..", "reports/../escape", "reports/nested/child", "other/sample", ".", "reports"])
def test_invalid_bundle_directories_fail_before_backend(monkeypatch, directory):
    calls = []
    monkeypatch.setattr(resolver, "_resolve", lambda _: calls.append("backend"))
    with pytest.raises(resolver.EvidenceNotFound):
        resolver.resolve(IDENTITY, bundle_dir=directory)
    assert calls == []


def test_absolute_bundle_outside_reports_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(resolver, "_resolve", unavailable)
    with pytest.raises(resolver.EvidenceNotFound, match="inside repository reports"):
        resolver.resolve(IDENTITY, bundle_dir=tmp_path / "outside")


@pytest.mark.parametrize("mutation", ["checksum", "id", "source", "version"])
def test_bundle_integrity_and_identity_are_verified(monkeypatch, mutation):
    source, target = recorded_bundle()
    source.unlink()
    record = json.loads(target.read_text(encoding="utf-8"))
    if mutation == "checksum":
        record["data"]["value"] = "tampered"
    else:
        record[mutation] = {"id": "container:cart:Status=running", "source": "jaeger", "version": 2}[mutation]
        core = {key: value for key, value in record.items() if key != "checksum"}
        record["checksum"] = hashlib.sha256(evidence._canonical(core)).hexdigest()
    target.write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(resolver, "_resolve", unavailable)
    with pytest.raises(resolver.EvidenceNotFound, match="checksum|identity or source"):
        resolver.resolve(IDENTITY, run_dir="original", bundle_dir="sample")


def test_wrong_filename_is_not_loaded():
    _, target = recorded_bundle()
    wrong = target.with_name("wrong.json")
    target.rename(wrong)
    with pytest.raises(ValueError, match="does not match"):
        evidence.load_bundle_snapshot(wrong, IDENTITY)


@pytest.mark.parametrize("part", ["reports", "bundle", "evidence", "file"])
def test_resolved_link_paths_are_refused_without_needing_host_symlink_privilege(monkeypatch, part):
    _, target = recorded_bundle()
    selected = {"reports": target.parents[2], "bundle": target.parents[1], "evidence": target.parent, "file": target}[part]
    original_resolve = Path.resolve
    def redirected(path, *args, **kwargs):
        if path == selected:
            return evidence.ROOT / "outside"
        return original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", redirected)
    with pytest.raises(ValueError):
        evidence.find_bundle_snapshot(IDENTITY, "sample")


def test_bundle_cli_identifies_origin(monkeypatch, capsys):
    source, _ = recorded_bundle()
    source.unlink()
    monkeypatch.setattr(resolver, "_resolve", unavailable)
    assert resolver.main([IDENTITY, "--run-dir", "original", "--bundle-dir", "sample"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["resolved_from"] == "bundle_snapshot"


def test_invalid_id_never_reaches_bundle_lookup(monkeypatch):
    calls = []
    monkeypatch.setattr(evidence, "find_bundle_snapshot", lambda *args: calls.append("bundle"))
    monkeypatch.setattr(resolver, "_resolve", lambda _: calls.append("backend"))
    with pytest.raises(resolver.EvidenceNotFound):
        resolver.resolve("trace:invented", bundle_dir="sample")
    assert calls == []
