"""Docker stream, severity, evidence, and isolation behavior."""

import hashlib
import subprocess
from unittest.mock import Mock

import pytest
import requests
from tools import logs
from tools.common import BackendError


def unavailable_search(*args, **kwargs):
    raise BackendError('Search backend unavailable')


def test_docker_fallback_reads_both_streams_filters_and_resolves(monkeypatch):
    stdout = '2026-10-23T09:00:00.123456789Z {"level":"info","message":"ready"}'
    stderr = '2026-10-23T09:00:01.123456789Z {"level":"error","message":"failed request","traceId":"abc"}'
    read = Mock(return_value=subprocess.CompletedProcess([], 0, stdout + "\n", stderr + "\n"))
    monkeypatch.setattr(logs, "search_json", unavailable_search)
    monkeypatch.setattr(logs, "container_names", lambda: ["checkout"])
    monkeypatch.setattr(logs.subprocess, "run", read)
    result = logs.get_logs("checkout", severity_min="ERROR")
    assert result["source"] == "docker"
    assert len(result["data"]) == 1
    row = result["data"][0]
    digest = hashlib.sha256(stderr.encode()).hexdigest()
    assert row["evidence_id"] == "dlog:checkout:" + digest
    assert row["trace_id"] == "abc"
    assert logs.resolve_docker_log("checkout", digest) == row
    assert read.call_args.args[0][:3] == ["docker", "logs", "--timestamps"]


def test_redact_entire_line_before_truncation(monkeypatch):
    lines = ['2026-10-23T09:00:00Z ERROR ' + "x" * 350 + ' feature_flag.key=anything',
             '2026-10-23T09:00:01Z WARN safe warning',
             '2026-10-23T09:00:02Z unclassified text']
    monkeypatch.setattr(logs, "docker_log_lines", lambda *args, **kwargs: lines)
    monkeypatch.setattr(logs, "search_json", unavailable_search)
    result = logs.get_logs("checkout")
    assert len(result["data"]) == 1
    assert result["data"][0]["body"] == "WARN safe warning"
    all_levels = logs.get_logs("checkout", severity_min="TRACE")
    assert len(all_levels["data"]) == 2


def test_docker_log_resolver_rejects_other_projects_and_bad_digests(monkeypatch):
    monkeypatch.setattr(logs, "container_names", lambda: ["checkout"])
    with pytest.raises(ValueError, match="project"):
        logs.resolve_docker_log("outside", "a" * 64)
    with pytest.raises(ValueError, match="digest"):
        logs.resolve_docker_log("checkout", "../escape")


@pytest.mark.parametrize('service', ['payment', 'recommendation', 'cart', 'currency', 'quote'])
def test_any_service_uses_fallback_after_empty_exported_logs(monkeypatch, service):
    monkeypatch.setattr(logs, "discover_fields", lambda _: {"service_filter": "resource.service.name.keyword",
        "time": "@timestamp", "severity": "severity.number", "body": "body"})
    monkeypatch.setattr(logs, "search_json", lambda *a, **kw: {"hits": {"total": {"value": 0}, "hits": []}})
    line = '2026-10-23T09:20:52.164139313Z {"level":"warn","trace_id":"abc","err":{"message":"Payment request failed. Invalid token."}}'
    monkeypatch.setattr(logs, "docker_log_lines", lambda *a, **kw: [line])
    result = logs.get_logs(service)
    assert result["source"] == "docker"
    assert result["data"][0]["severity"] == "WARN"
    assert result["data"][0]["body"] == "Payment request failed. Invalid token."
    assert result["evidence_ids"][0].startswith(f"dlog:{service}:")
    assert 'no usable matching log records' in result['warnings'][0]


@pytest.mark.parametrize('failure', [BackendError('HTTP 503'), requests.ReadTimeout('read timed out'), subprocess.TimeoutExpired('search', 8)])
def test_backend_errors_and_timeouts_fall_back_for_any_service(monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(logs, 'search_json', fail)
    monkeypatch.setattr(logs, 'docker_log_lines', lambda *args, **kwargs: ['2026-10-23T09:20:52Z ERROR dependency failed'])
    result = logs.get_logs('recommendation')
    assert result['source'] == 'docker'
    assert result['data'][0]['body'] == 'ERROR dependency failed'
    assert type(failure).__name__ in result['warnings'][0]


def test_zero_safe_search_hits_uses_docker_and_never_snapshots_disclosure(monkeypatch):
    monkeypatch.setattr(logs, 'discover_fields', lambda _: {'service_filter': 'service.name',
        'time': '@timestamp', 'severity': 'severity.number', 'severity_text': None, 'body': 'body', 'trace': None})
    monkeypatch.setattr(logs, 'search_json', lambda *a, **kw: {'hits': {'total': {'value': 1}, 'hits': [
        {'_id': 'unsafe', '_source': {'body': 'paymentFailure feature flag'}}]}})
    monkeypatch.setattr(logs, 'docker_log_lines', lambda *args, **kwargs: ['2026-10-23T09:20:52Z ERROR safe failure'])
    result = logs.get_logs('currency')
    assert result['source'] == 'docker'
    assert len(result['evidence_ids']) == 1
    assert all(identifier.startswith('dlog:currency:') for identifier in result['evidence_paths'])


def test_exported_logs_are_preferred_even_for_former_stdout_services(monkeypatch):
    monkeypatch.setattr(logs, 'discover_fields', lambda _: {'service_filter': 'service.name',
        'time': '@timestamp', 'severity': 'severity.number', 'severity_text': None, 'body': 'body', 'trace': None})
    monkeypatch.setattr(logs, 'search_json', lambda *a, **kw: {'hits': {'total': {'value': 1}, 'hits': [
        {'_id': 'safe', '_source': {'body': 'safe error', 'service.name': 'checkout', 'severity.number': 17}}]}})
    def forbidden(*args, **kwargs):
        raise AssertionError('Docker fallback should not run when search returns usable logs')
    monkeypatch.setattr(logs, 'docker_log_lines', forbidden)
    result = logs.get_logs('checkout')
    assert result['source'] == 'opensearch'
    assert result['evidence_ids'] == ['log:otel/safe']


def test_docker_log_read_retries_once_and_preserves_both_streams(monkeypatch):
    monkeypatch.setattr(logs, 'container_names', lambda: ['currency'])
    read = Mock(side_effect=[subprocess.TimeoutExpired('docker logs', 8),
        subprocess.CompletedProcess([], 0, 'stdout line', 'stderr line')])
    monkeypatch.setattr(logs.subprocess, 'run', read)
    assert logs.docker_log_lines('currency') == ['stdout line', 'stderr line']
    assert read.call_count == 2
    assert all(call.kwargs['timeout'] == pytest.approx(8) for call in read.call_args_list)
