"""Transport helpers. These helpers only issue reads."""

from __future__ import annotations

import contextvars
import functools
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

import requests

ROOT = Path(__file__).resolve().parents[1]
DEADLINE = contextvars.ContextVar("telemetry_deadline", default=None)


class BackendError(ValueError):
    pass


def now_iso(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, timezone.utc).isoformat()


def window(lookback_s=0):
    if not 0 <= lookback_s <= 86400:
        raise ValueError("lookback_s must be between 0 and 86400")
    end = time.time()
    return {"from": now_iso(end - lookback_s), "to": now_iso(end)}


def envelope(tool, source, query, span, data, ids=(), truncated=False, **extra):
    return dict(tool=tool, source=source, query=query, window=span, data=data,
                evidence_ids=list(dict.fromkeys(ids)), truncated=bool(truncated), **extra)


def remaining():
    deadline = DEADLINE.get()
    seconds = 2.6 if deadline is None else deadline - time.monotonic()
    if seconds <= 0:
        raise BackendError("Read deadline exceeded")
    return max(0.01, min(2.6, seconds))


def bounded(source):
    def decorate(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            token = DEADLINE.set(time.monotonic() + 2.8)
            started = time.monotonic()
            try:
                result = func(*args, **kwargs)
            except (ValueError, OSError, subprocess.SubprocessError, requests.RequestException) as exc:
                result = envelope(func.__name__, source, json.dumps({"args": args, "kwargs": kwargs}, default=str)[:8192], window(), [],
                                  error={"type": type(exc).__name__, "message": str(exc)[:500]})
            finally:
                DEADLINE.reset(token)
            result["elapsed_s"] = round(time.monotonic() - started, 4)
            from .redact import sanitize
            return sanitize(result)
        return wrapped
    return decorate


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=remaining(), check=False)
    if result.returncode:
        raise BackendError(result.stderr.strip()[-500:] or "Docker read failed")
    return result.stdout


def get_json(url, params=None, body=None):
    # OpenSearch search supports a GET body, so even searches use GET.
    response = requests.get(url, params=params, json=body, timeout=remaining())
    if not response.ok:
        raise BackendError(f"HTTP {response.status_code} reading {url}: {response.text[:250]}")
    return response.json()


def prometheus():
    return os.environ.get("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")


def jaeger():
    return os.environ.get("JAEGER_URL", "http://localhost:8080/jaeger/ui/api").rstrip("/")


def search_json(path, body=None):
    base = os.environ.get("OPENSEARCH_URL")
    if not base:
        try:
            mappings = docker("port", "opensearch", "9200").splitlines()
            port = mappings[0].rsplit(":", 1)[1]
            base = f"http://localhost:{int(port)}"
        except (ValueError, IndexError, BackendError):
            base = None
    if base:
        return get_json(base.rstrip("/") + path, body=body)
    args = ["exec", "opensearch", "curl", "-fsS", "--max-time", "2", "-X", "GET"]
    if body is not None:
        args += ["-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    args += ["http://localhost:9200" + path]
    return json.loads(docker(*args))


def log_index():
    index = os.environ.get("LOG_INDEX", "otel")
    if not index.replace("-", "").replace("_", "").isalnum():
        raise ValueError("LOG_INDEX must be a single concrete index")
    return index
