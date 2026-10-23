"""Structured calls with explicit provider fallbacks and redacted audit records.

Adapted environment loading and retry/routing structure from Yash's unpublished
core/llm_router.py; this client has no local/stub success route.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone
import requests

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def load_env(path=None):
    env = dict(os.environ)
    path = Path(path or ROOT / '.env')
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                name, value = line.split('=', 1)
                env.setdefault(name.strip(), value.strip().strip('\"\''))
    return env


def scrub(value, secrets=()):
    if isinstance(value, dict):
        return {k: ('[redacted]' if v is not None and re.search(r'authorization|api[_-]?key|password|secret|^token$', k, re.I)
                    else scrub(v, secrets)) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[redacted]')
        return re.sub(r'(?i)bearer\s+[a-z0-9_.-]+', 'Bearer [redacted]', value)
    return value


class ModelUnavailable(RuntimeError):
    pass


class Router:
    def __init__(self, run_dir, env=None, model=None):
        self.env = load_env() if env is None else env
        self.log_path = Path(run_dir) / 'llm.jsonl'
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_override = model
        self.entries = []
        self.failed_routes = None
        self.session = requests.Session()
        self.session.trust_env = False
        self.secrets = [v for k, v in self.env.items() if any(s in k.upper() for s in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET')) and v]

    def routes(self):
        key = self.env.get('OPENROUTER_API_KEY')
        if key:
            for configured in ('OPENROUTER_MODEL', 'OPENROUTER_FALLBACK_MODEL'):
                model = self.model_override if configured == 'OPENROUTER_MODEL' and self.model_override else self.env.get(configured)
                if model:
                    yield 'openrouter', model, 'https://openrouter.ai/api/v1/chat/completions', {'Authorization': 'Bearer ' + key}
        key, model = self.env.get('GEMINI_API_KEY'), self.env.get('GEMINI_MODEL')
        if key and model:
            yield 'gemini', model, 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', {'Authorization': 'Bearer ' + key}

    def complete(self, messages, functions, *, purpose='investigate'):
        first_entry = len(self.entries)
        for provider, model, url, headers in self.routes():
            for attempt in range(2):
                body = {'model': model, 'messages': messages, 'tools': functions,
                        'tool_choice': 'required', 'parallel_tool_calls': False,
                        'temperature': 0, 'max_tokens': 4500}
                if provider == 'openrouter':
                    body['reasoning'] = {'effort': 'medium', 'exclude': True}
                started = time.monotonic()
                entry = {'timestamp': now(), 'purpose': purpose, 'provider': provider, 'model': model,
                         'attempt': attempt + 1, 'request': scrub(body, self.secrets),
                         'prompt_sha256': hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()}
                status = None
                try:
                    response = self.session.post(url, headers=headers, json=body, timeout=(10, 100))
                    status = response.status_code
                    response.raise_for_status()
                    payload = response.json()
                    message = payload['choices'][0]['message']
                    # Do not retain provider reasoning content; retain the public tool decision.
                    message = {k: v for k, v in message.items() if k in ('role', 'content', 'tool_calls')}
                    calls = message.get('tool_calls') or []
                    if not calls:
                        raise ValueError('No structured tool call returned')
                    call = calls[0]['function']
                    arguments = json.loads(call['arguments']) if isinstance(call['arguments'], str) else call['arguments']
                    usage = payload.get('usage', {})
                    entry.update(ok=True, response=scrub(message, self.secrets), usage=usage,
                                 input_tokens=usage.get('prompt_tokens', 0), output_tokens=usage.get('completion_tokens', 0),
                                 latency_s=round(time.monotonic() - started, 3))
                    # The requested reference estimate; provider actual cost is retained separately.
                    entry['estimated_cost_usd'] = (entry['input_tokens'] * 1.25 + entry['output_tokens'] * 10) / 1e6
                    self._log(entry)
                    self.failed_routes = None
                    return {'name': call['name'], 'arguments': arguments, 'model': model}
                except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
                    entry.update(ok=False, error=type(exc).__name__, error_detail=scrub(str(exc), self.secrets)[:500], http_status=status,
                                 latency_s=round(time.monotonic() - started, 3))
                    self._log(entry)
                    retryable = status in (429, 500, 502, 503, 504) or isinstance(exc, (requests.ConnectionError, requests.Timeout))
                    if not retryable or attempt:
                        break
                    time.sleep(1)
        # Keep the final failure for each attempted route, including failures
        # after an earlier successful investigation decision.
        self.failed_routes = {}
        for entry in self.entries[first_entry:]:
            route = entry['provider'] + '/' + entry['model']
            self.failed_routes[route] = entry
        details = []
        for route, entry in self.failed_routes.items():
            status = f" HTTP {entry['http_status']}" if entry.get('http_status') is not None else ''
            details.append(f"{route}: {entry['error']}{status}: {entry.get('error_detail', '')[:250]}")
        detail = '; '.join(details) or 'No model route has both credentials and a configured model id.'
        raise ModelUnavailable('All configured structured model routes failed. ' + scrub(detail, self.secrets))

    def _log(self, entry):
        self.entries.append(entry)
        with self.log_path.open('a', encoding='utf-8') as output:
            output.write(json.dumps(scrub(entry, self.secrets), ensure_ascii=False) + '\n')

    def summary(self):
        entries = self.entries
        models = list(dict.fromkeys(e['model'] for e in entries if e.get('ok')))
        model = ', '.join(models) or 'not called'
        if self.failed_routes is not None:
            model = 'failed: ' + (', '.join(self.failed_routes) or 'no configured model routes')
        return {'model': model, 'models_used': models,
                'llm_calls': len(entries), 'tokens_input': sum(e.get('input_tokens', 0) for e in entries),
                'tokens_output': sum(e.get('output_tokens', 0) for e in entries),
                'estimated_cost_usd': round(sum(e.get('estimated_cost_usd', 0) for e in entries), 6)}
