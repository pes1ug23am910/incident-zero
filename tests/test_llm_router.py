"""Offline provider-routing and audit-redaction tests; no credentials or network."""

import json

import pytest
import requests

from agent.llm_router import ModelUnavailable, Router, scrub


def environment(**overrides):
    return {
        "OPENROUTER_API_KEY": "fixture-router-credential",
        "OPENROUTER_MODEL": "fixture/primary",
        "OPENROUTER_FALLBACK_MODEL": "fixture/fallback",
        "GEMINI_API_KEY": "fixture-direct-credential",
        "GEMINI_MODEL": "fixture-direct",
        **overrides,
    }


class Response:
    def __init__(self, status=200, *, detail="fixture request failed", payload=None):
        self.status_code = status
        self.detail = detail
        self.payload = payload or {
            "choices": [{"message": {
                "role": "assistant", "content": None, "reasoning": "private reasoning must not be retained",
                "tool_calls": [{"id": "call-1", "type": "function", "function": {
                    "name": "get_logs", "arguments": json.dumps({"service": "payment", "reason": "Inspect errors"})}}],
            }}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
        }

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.detail)

    def json(self):
        return self.payload


class Session:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        result = next(self.outcomes)
        if isinstance(result, Exception):
            raise result
        return result


def make_router(tmp_path, monkeypatch, outcomes, env=None):
    router = Router(tmp_path, env=env or environment())
    router.session = Session(outcomes)
    sleeps = []
    monkeypatch.setattr("agent.llm_router.time.sleep", lambda seconds: sleeps.append(seconds))
    return router, sleeps


def complete(router):
    return router.complete([{"role": "user", "content": "Inspect supplied telemetry"}], [])


def test_scrub_preserves_null_approval_token_and_redacts_actual_value():
    report = {"approval": {"approved": None, "token": None}, "secret": None,
              "rows": [{"token": "fixture-value", "api_key": "fixture-value"}]}
    cleaned = scrub(report)
    assert cleaned["approval"] == {"approved": None, "token": None}
    assert cleaned["secret"] is None
    assert cleaned["rows"] == [{"token": "[redacted]", "api_key": "[redacted]"}]
    assert report["rows"][0]["token"] == "fixture-value"


def test_retryable_status_retries_same_model_then_records_usage(tmp_path, monkeypatch):
    router, sleeps = make_router(tmp_path, monkeypatch, [Response(503), Response()])
    result = complete(router)
    assert result["model"] == "fixture/primary"
    assert [call["json"]["model"] for call in router.session.calls] == ["fixture/primary", "fixture/primary"]
    assert sleeps == [1]
    summary = router.summary()
    assert summary["llm_calls"] == 2
    assert summary["tokens_input"] == 1000
    assert summary["tokens_output"] == 200
    assert summary["estimated_cost_usd"] == pytest.approx(0.00325)
    assert summary["models_used"] == ["fixture/primary"]
    request = router.session.calls[0]["json"]
    assert request["parallel_tool_calls"] is False
    assert request["reasoning"] == {"effort": "medium", "exclude": True}


def test_nonretryable_failure_moves_to_configured_fallback(tmp_path, monkeypatch):
    router, sleeps = make_router(tmp_path, monkeypatch, [Response(400), Response()])
    assert complete(router)["model"] == "fixture/fallback"
    assert [entry["model"] for entry in router.entries] == ["fixture/primary", "fixture/fallback"]
    assert sleeps == []


def test_transport_failures_retry_then_fall_back(tmp_path, monkeypatch):
    router, sleeps = make_router(tmp_path, monkeypatch, [requests.Timeout("fixture timeout"), requests.ConnectionError("fixture disconnected"), Response()])
    assert complete(router)["model"] == "fixture/fallback"
    assert len(router.session.calls) == 3
    assert sleeps == [1]
    assert router.entries[0]["error"] == "Timeout"
    assert router.entries[1]["error"] == "ConnectionError"


def test_chunked_response_retries_same_model_before_fallback(tmp_path, monkeypatch):
    router, sleeps = make_router(tmp_path, monkeypatch, [
        requests.exceptions.ChunkedEncodingError('Response ended prematurely'), Response()])
    assert complete(router)['model'] == 'fixture/primary'
    assert [call['json']['model'] for call in router.session.calls] == ['fixture/primary'] * 2
    assert sleeps == [1]
    assert router.entries[0]['error'] == 'ChunkedEncodingError'
    assert router.entries[0]['error_detail'] == 'Response ended prematurely'
    assert router.summary()['model'] == 'fixture/primary'
    assert router.summary()['models_used'] == ['fixture/primary']


def test_chunked_retry_exhaustion_and_dns_failure_remain_terminal_after_success(tmp_path, monkeypatch):
    router, sleeps = make_router(tmp_path, monkeypatch, [Response(),
        requests.exceptions.ChunkedEncodingError('Response ended prematurely'),
        requests.exceptions.ChunkedEncodingError('Response ended prematurely'),
        requests.ConnectionError('Name resolution failed'), requests.ConnectionError('Name resolution failed')],
        env=environment(GEMINI_MODEL=''))
    complete(router)
    with pytest.raises(ModelUnavailable) as failure:
        complete(router)
    assert sleeps == [1, 1]
    assert [entry['attempt'] for entry in router.entries[1:]] == [1, 2, 1, 2]
    assert [entry['model'] for entry in router.entries[1:]] == ['fixture/primary'] * 2 + ['fixture/fallback'] * 2
    assert 'ChunkedEncodingError: Response ended prematurely' in str(failure.value)
    assert 'ConnectionError: Name resolution failed' in str(failure.value)
    assert router.summary()['model'] == 'failed: openrouter/fixture/primary, openrouter/fixture/fallback'
    assert router.summary()['models_used'] == ['fixture/primary']


def test_direct_provider_is_last_fallback_and_requires_its_model(tmp_path, monkeypatch):
    router, _ = make_router(tmp_path, monkeypatch, [Response(400), Response(400), Response()])
    assert complete(router)["model"] == "fixture-direct"
    assert [entry["provider"] for entry in router.entries] == ["openrouter", "openrouter", "gemini"]
    direct = router.session.calls[-1]
    assert direct["url"].startswith("https://generativelanguage.googleapis.com/")
    assert direct["headers"]["Authorization"] == "Bearer fixture-direct-credential"
    assert "reasoning" not in direct["json"]

    missing = Router(tmp_path / "without-direct-model", env=environment(GEMINI_MODEL=""))
    assert [route[0] for route in missing.routes()] == ["openrouter", "openrouter"]


def test_failed_and_successful_audit_records_strip_credentials_and_reasoning(tmp_path, monkeypatch):
    env = environment()
    detail = "failed Authorization Bearer " + env["OPENROUTER_API_KEY"]
    response = Response()
    response.payload["choices"][0]["message"]["content"] = "echo " + env["GEMINI_API_KEY"]
    router, _ = make_router(tmp_path, monkeypatch, [Response(400, detail=detail), response], env=env)
    router.complete([{"role": "user", "content": "fixture " + env["OPENROUTER_API_KEY"]}], [])
    text = router.log_path.read_text(encoding="utf-8")
    assert env["OPENROUTER_API_KEY"] not in text
    assert env["GEMINI_API_KEY"] not in text
    assert "private reasoning must not be retained" not in text
    rows = [json.loads(line) for line in text.splitlines()]
    assert len(rows) == 2 and rows[0]["ok"] is False and rows[1]["ok"] is True
    assert "[redacted]" in rows[0]["error_detail"]
    assert "[redacted]" in rows[1]["response"]["content"]


def test_all_routes_failed_never_returns_a_stub_success(tmp_path, monkeypatch):
    router, _ = make_router(tmp_path, monkeypatch, [Response(401), Response(401), Response(401)])
    with pytest.raises(ModelUnavailable, match="All configured") as failure:
        complete(router)
    assert router.summary()["model"] == "failed: openrouter/fixture/primary, openrouter/fixture/fallback, gemini/fixture-direct"
    assert router.summary()["models_used"] == []
    assert router.summary()["llm_calls"] == 3
    assert "openrouter/fixture/primary: HTTPError HTTP 401" in str(failure.value)


def test_ssl_failure_retries_once_without_disabling_certificate_verification(tmp_path, monkeypatch):
    router, sleeps = make_router(tmp_path, monkeypatch, [requests.exceptions.SSLError("TLS handshake ended"), Response()])
    assert complete(router)["model"] == "fixture/primary"
    assert sleeps == [1]
    assert [call["json"]["model"] for call in router.session.calls] == ["fixture/primary"] * 2
    assert all(call.get("verify", True) is True for call in router.session.calls)
    assert router.entries[0]["error_detail"] == "TLS handshake ended"
    assert router.summary()["model"] == "fixture/primary"


def test_terminal_failure_remains_visible_after_an_earlier_success(tmp_path, monkeypatch):
    router, _ = make_router(tmp_path, monkeypatch, [Response(), Response(401), Response(401), Response(401), Response()])
    complete(router)
    with pytest.raises(ModelUnavailable):
        complete(router)
    summary = router.summary()
    assert summary["model"].startswith("failed: openrouter/fixture/primary")
    assert summary["models_used"] == ["fixture/primary"]
    assert summary["tokens_input"] == 1000
    complete(router)
    assert router.summary()["model"] == "fixture/primary"


def test_terminal_failure_details_are_sanitized_and_bounded(tmp_path, monkeypatch):
    env = environment(OPENROUTER_FALLBACK_MODEL="", GEMINI_MODEL="")
    detail = "TLS handshake failed for " + env["OPENROUTER_API_KEY"] + " " + "x" * 1000
    router, sleeps = make_router(tmp_path, monkeypatch, [requests.exceptions.SSLError(detail)] * 2, env=env)
    with pytest.raises(ModelUnavailable) as failure:
        complete(router)
    assert env["OPENROUTER_API_KEY"] not in str(failure.value)
    assert "SSLError" in str(failure.value) and "[redacted]" in str(failure.value)
    assert len(str(failure.value)) < 400
    assert len(router.entries) == 2 and sleeps == [1]


def test_unconfigured_router_fails_explicitly_without_network(tmp_path):
    router = Router(tmp_path, env={})
    with pytest.raises(ModelUnavailable, match="No model route"):
        complete(router)
    assert router.summary()["model"] == "failed: no configured model routes"
    assert router.summary()["models_used"] == []
    assert router.summary()["llm_calls"] == 0
