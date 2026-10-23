"""Transport helpers. These helpers only issue reads."""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

import requests

ROOT = Path(__file__).resolve().parents[1]
READ_TIMEOUT_S = 8.0


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
    """Compatibility helper: each backend read receives its own timeout."""
    return READ_TIMEOUT_S


def read_with_retry(operation):
    """Retry a failed read once; never retry a whole diagnostic invocation."""
    for attempt in range(2):
        try:
            return operation()
        except (ValueError, OSError, subprocess.SubprocessError, requests.RequestException):
            if attempt:
                raise
            time.sleep(0.1)


def bounded(source):
    def decorate(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            from .evidence import begin_run, end_run, persist_envelope
            from .redact import sanitize

            started = time.monotonic()
            run_token = None
            current = None
            try:
                current, run_token = begin_run(kwargs.pop("run_dir", None))
                result = sanitize(func(*args, **kwargs))
                result = persist_envelope(result, current)
            except (ValueError, OSError, subprocess.SubprocessError, requests.RequestException) as exc:
                result = envelope(func.__name__, source, json.dumps({"args": args, "kwargs": kwargs}, default=str)[:8192], window(), [],
                                  error={"type": type(exc).__name__, "message": str(exc)[:500]})
                if current is not None:
                    result = persist_envelope(result, current)
            finally:
                end_run(run_token)
            result["elapsed_s"] = round(time.monotonic() - started, 4)
            return sanitize(result)
        return wrapped
    return decorate


def docker(*args, include_stderr=False):
    def read():
        result = subprocess.run(["docker", *args], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=remaining(), check=False)
        if result.returncode:
            raise BackendError(result.stderr.strip()[-500:] or "Docker read failed")
        return result.stdout + "\n" + result.stderr if include_stderr else result.stdout
    return read_with_retry(read)


def get_json(url, params=None, body=None):
    # OpenSearch search supports a GET body, so even searches use GET.
    def read():
        response = requests.get(url, params=params, json=body, timeout=remaining())
        if not response.ok:
            raise BackendError(f"HTTP {response.status_code} reading {url}: {response.text[:250]}")
        return response.json()
    return read_with_retry(read)


def prometheus():
    return os.environ.get("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")


def jaeger_endpoints():
    """Prefer Jaeger's published port so frontend outages cannot blind reads."""
    endpoints = []
    try:
        mappings = docker("port", "jaeger", "16686").splitlines()
        port = int(mappings[0].rsplit(":", 1)[1])
        endpoints.append(f"http://localhost:{port}/jaeger/ui/api")
    except (ValueError, IndexError, OSError, subprocess.SubprocessError):
        pass
    endpoints.append(os.environ.get("JAEGER_URL", "http://localhost:8080/jaeger/ui/api").rstrip("/"))
    return list(dict.fromkeys(endpoints))


def jaeger():
    """Return the preferred endpoint; callers needing failover use jaeger_json."""
    return jaeger_endpoints()[0]


def jaeger_json(path, params=None, *, fetch=None):
    read = fetch or get_json
    errors = []
    for base in jaeger_endpoints():
        try:
            url = base + "/" + path.lstrip("/")
            result = read(url) if params is None else read(url, params=params)
            if result.get("errors"):
                raise BackendError(str(result["errors"]))
            return result
        except (ValueError, OSError, subprocess.SubprocessError, requests.RequestException) as exc:
            errors.append(f"{base}: {exc}")
    raise BackendError("Jaeger endpoints failed: " + "; ".join(errors))


def search_json(path, body=None):
    base = os.environ.get("OPENSEARCH_URL")
    if not base:
        try:
            mappings = docker("port", "opensearch", "9200").splitlines()
            port = mappings[0].rsplit(":", 1)[1]
            base = f"http://localhost:{int(port)}"
        except (ValueError, IndexError, OSError, subprocess.SubprocessError):
            base = None
    if base:
        return get_json(base.rstrip("/") + path, body=body)
    args = ["exec", "opensearch", "curl", "-fsS", "--max-time", "8", "-X", "GET"]
    if body is not None:
        args += ["-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    args += ["http://localhost:9200" + path]
    return json.loads(docker(*args))


def log_index():
    index = os.environ.get("LOG_INDEX", "otel")
    if not index.replace("-", "").replace("_", "").isalnum():
        raise ValueError("LOG_INDEX must be a single concrete index")
    return index
