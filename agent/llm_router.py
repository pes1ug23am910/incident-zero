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
        return {k: ('[redacted]' if re.search(r'authorization|api[_-]?key|password|secret|^token$', k, re.I)
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
                    return {'name': call['name'], 'arguments': arguments, 'model': model}
                except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
                    entry.update(ok=False, error=type(exc).__name__, http_status=status,
                                 latency_s=round(time.monotonic() - started, 3))
                    self._log(entry)
                    if status not in (429, 500, 502, 503, 504) or attempt:
                        break
                    time.sleep(1)
        raise ModelUnavailable('All configured structured model routes failed; inspect sanitized llm.jsonl')

    def _log(self, entry):
        self.entries.append(entry)
        with self.log_path.open('a', encoding='utf-8') as output:
            output.write(json.dumps(scrub(entry, self.secrets), ensure_ascii=False) + '\n')

    def summary(self):
        entries = self.entries
        models = list(dict.fromkeys(e['model'] for e in entries if e.get('ok')))
        return {'model': ', '.join(models) or 'unavailable', 'models_used': models,
                'llm_calls': len(entries), 'tokens_input': sum(e.get('input_tokens', 0) for e in entries),
                'tokens_output': sum(e.get('output_tokens', 0) for e in entries),
                'estimated_cost_usd': round(sum(e.get('estimated_cost_usd', 0) for e in entries), 6)}
