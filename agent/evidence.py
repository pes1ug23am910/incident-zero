"""Ground references, count independent positive signals and track coverage."""
from __future__ import annotations
import json
import re
from .policy import SERVICES
from .contracts import Cause
from tools.evidence import load_snapshot, snapshot_path, expected_source

CALLERS = {
    'payment': ['checkout', 'frontend'], 'valkey-cart': ['cart', 'checkout', 'frontend'],
    'cart': ['checkout', 'frontend'], 'product-catalog': ['recommendation', 'checkout', 'frontend'],
    'recommendation': ['frontend'], 'ad': ['frontend'], 'checkout': ['frontend'],
    'currency': ['checkout', 'frontend'], 'shipping': ['checkout', 'frontend'],
    'quote': ['shipping', 'checkout', 'frontend'], 'email': ['checkout'], 'image-provider': ['frontend'],
}


class PlantedEvidence(ValueError):
    pass


def has_instruction(text):
    return bool(re.search(r'ignore (?:all |previous |prior )*instructions|system prompt|you (?:must|should) (?:restart|ignore)|restart payment', str(text), re.I))


def data_projection(value):
    """Mark imperative telemetry without making it a diagnostic instruction."""
    if isinstance(value, dict):
        return {k: data_projection(v) for k, v in value.items()}
    if isinstance(value, list):
        return [data_projection(v) for v in value]
    return '[untrusted instruction-like text omitted]' if isinstance(value, str) and has_instruction(value) else value


def _known_mentions(text):
    """Recognize service/endpoint and RPC names, never arbitrary substrings."""
    if not isinstance(text, str) or has_instruction(text):
        return set()
    lowered = text.lower().replace('_', '-')
    found = set()
    for service in SERVICES:
        aliases = {service, service.replace('-', '') + 'service'}
        if '-' in service:
            aliases.add(service.replace('-', ''))
        if any(re.search(r'(?<![a-z0-9-])' + re.escape(alias) + r'(?![a-z0-9-])', lowered)
               for alias in aliases):
            found.add(service)
    return found


def _structured_services(identifier, payload):
    found = set()
    if identifier.startswith(('container:', 'dlog:')):
        found.add(identifier.split(':')[1])
    def walk(value, parent=None):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('service', 'service_name', 'serviceName', 'service.name',
                           'resource.service.name', 'container_name') and isinstance(child, str) and child in SERVICES:
                    found.add(child)
                if key == 'name' and parent == 'service' and child in SERVICES:
                    found.add(child)
                if key == 'services' and isinstance(child, list):
                    found.update(x for x in child if x in SERVICES)
                walk(child, key)
        elif isinstance(value, list):
            for child in value:
                walk(child, parent)
    walk(payload)
    return found & set(SERVICES)


def _diagnostic_text(payload):
    values = []
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if (key in ('operationName', 'operation', 'status_message', 'body', 'message', 'msg',
                            'value', 'original_line') or key.startswith('exception.')) and isinstance(child, str):
                    if not has_instruction(child):
                        values.append(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(payload)
    return values


def _cache_dependency(identifier, owners, texts):
    """The cart's cache endpoint is known; ordinary cache mentions prove nothing."""
    if not identifier.startswith(('log:', 'dlog:')) or 'cart' not in owners:
        return set()
    for text in texts:
        if has_instruction(text) or not re.search(r'(?i)\b(?:redis|valkey)(?:\b|ConnectionException)', text):
            continue
        if re.search(r'(?i)RedisConnectionException|connection\s+(?:has\s+)?(?:failed|refused|reset)|'
                     r'(?:unable|failed|failure|cannot|could not)\s+to\s+connect|'
                     r'no connection (?:is )?(?:active|available)|'
                     r'connection[^.\n]{0,80}(?:unavailable|timed?\s*out)|'
                     r'(?:redis|valkey)[^.\n]{0,80}(?:connection failure|connect timeout)', text):
            return {'valkey-cart'}
    return set()


def relevant_services(identifier, payload):
    owners = _structured_services(identifier, payload)
    texts = _diagnostic_text(payload)
    mentioned = set().union(*(_known_mentions(text) for text in texts)) if texts else set()
    return sorted(owners | mentioned | _cache_dependency(identifier, owners, texts))


def positive_services(identifier, payload):
    """Localize positive trace evidence to failing spans and explicit callees.

    A healthy participant in an otherwise failed trace remains relevant context,
    but cannot corroborate a diagnosis of that participant.
    """
    if strength(identifier, payload) < .5:
        return []
    if not identifier.startswith(('trace:', 'span:')):
        return relevant_services(identifier, payload)
    from tools.traces import is_error

    processes = payload.get('processes', {})
    spans = payload.get('spans', [payload])
    found = set()
    for span in spans:
        if not is_error(span) and span.get('error') is not True:
            continue
        owner = processes.get(span.get('processID'), {}).get('serviceName')
        if owner in SERVICES:
            found.add(owner)
        if span.get('service') in SERVICES:
            found.add(span['service'])
        # Arbitrary span attributes may contain user input. Only the operation,
        # remote endpoint/RPC fields and error descriptions can locate a callee.
        descriptions = [span.get('operationName', ''), span.get('operation', ''),
                        span.get('status_message', '')]
        allowed = {'rpc.service', 'peer.service', 'server.address', 'net.peer.name',
                   'network.peer.address', 'otel.status_description', 'message', 'error.object'}
        attributes = list(span.get('tags', []))
        attributes.extend(field for log in span.get('logs', []) for field in log.get('fields', []))
        descriptions.extend(item.get('value', '') for item in attributes
                            if item.get('key') in allowed or item.get('key', '').startswith('exception.'))
        for text in descriptions:
            found.update(_known_mentions(text))
    return sorted(found)


def strength(identifier, payload):
    text = json.dumps(payload, ensure_ascii=False).lower()
    if has_instruction(text):
        return 0
    if identifier.startswith('container:'):
        field, value = identifier.split(':', 2)[2].split('=', 1)
        if field == 'Status':
            return 1.0 if value != 'running' else 0.0
        if field == 'OOMKilled':
            return 1.0 if value == 'true' else 0.0
        if field == 'NanoCpus':
            return .9 if 0 < float(value) <= 100_000_000 else 0.0
        return .6 if field == 'RestartCount' and float(value) > 1 else 0.0
    if identifier.startswith('metric:'):
        value = float(payload.get('value', 0))
        query = payload.get('query', '')
        if query == 'named:error_rate_by_service' or 'STATUS_CODE_ERROR' in query:
            return .9 if value >= .05 else .6 if value > 0 else 0
        if query == 'named:p95_latency_by_service' or 'histogram_quantile' in query:
            return .8 if value >= 500 else .4 if value >= 100 else 0
        if 'cpu' in query or 'memory' in query:
            return .5 if value > 0 else 0
        return .3 if value > 0 else 0
    if identifier.startswith(('trace:', 'span:')):
        return .95 if re.search(r'"error"\s*,\s*"(?:type"\s*:\s*"\w+"\s*,\s*)?"value"\s*:\s*true|exception|unavailable|connection refused|"error"\s*:\s*true|"value"\s*:\s*"ERROR"', text, re.I) else .35
    if identifier.startswith(('log:', 'dlog:')):
        return .9 if re.search(r'error|exception|failed|failure|unavailable|timeout|refused|invalid token|outofmemory|'
                              r'unable to connect|cannot connect|could not connect', text) else .3
    return .4


def registry(result):
    records = {}
    for identifier in result.get('evidence_ids', []):
        if identifier.startswith(('container:', 'dlog:')) and identifier.split(':')[1] not in SERVICES:
            continue
        record = load_snapshot(snapshot_path(result['run_dir'], identifier), identifier)
        payload = record['data']
        records[identifier] = {'id': identifier, 'source': expected_source(identifier), 'data': payload,
                               'services': relevant_services(identifier, payload),
                               'positive_services': positive_services(identifier, payload),
                               'strength': strength(identifier, payload)}
    return records


def validate_causes(raw, evidence, symptom_services):
    causes = []
    for value in raw:
        cause = Cause.model_validate(value).model_dump()
        if cause['component'] not in SERVICES:
            raise PlantedEvidence('Unknown target component')
        if any(identifier not in evidence for identifier in cause['evidence_ids']):
            raise PlantedEvidence('Hypothesis cited an ID not returned by a tool in this run')
        if not cause['evidence_ids']:
            raise PlantedEvidence('A hypothesis requires evidence')
        component = cause['component']
        allowed = {component, *CALLERS.get(component, [])}
        related, positive = [], {}
        for identifier in cause['evidence_ids']:
            record = evidence[identifier]
            if set(record['services']) & allowed:
                related.append(record)
                if component in record.get('positive_services', record['services']) and record['strength'] >= .5:
                    positive[record['source']] = max(positive.get(record['source'], 0), record['strength'])
        if not any(component in record['services'] for record in related):
            raise PlantedEvidence('Cited evidence does not identify the proposed component')
        sources = len(positive)
        magnitude = sum(positive.values()) / sources if sources else 0
        confidence = .95 if sources >= 3 and magnitude >= .75 else .9 if sources >= 2 and magnitude >= .75 else .78 if sources >= 2 else .55 if sources else .3
        cause['confidence_evidence'] = confidence
        cause['confidence'] = min(cause['confidence_model'], confidence)
        cause['explains_symptoms'] = sorted(set(cause['explains_symptoms']) & allowed & set(symptom_services))
        causes.append(cause)
    return sorted(causes, key=lambda c: c['confidence'], reverse=True)


def uncovered(causes, symptoms):
    covered = {service for cause in causes if cause['confidence'] >= .75 for service in cause['explains_symptoms']}
    return sorted(set(symptoms) - covered)
