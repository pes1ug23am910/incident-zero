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


def relevant_services(identifier, payload):
    found = set()
    if identifier.startswith(('container:', 'dlog:')):
        found.add(identifier.split(':')[1])
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('service', 'service_name', 'serviceName', 'container_name', 'name') and isinstance(child, str) and child in SERVICES:
                    found.add(child)
                if key == 'services' and isinstance(child, list):
                    found.update(x for x in child if x in SERVICES)
                if key in ('operationName', 'operation', 'status_message', 'body', 'message', 'value') and isinstance(child, str) and not has_instruction(child):
                    lowered = child.lower().replace('_', '-').replace('productcatalog', 'product-catalog')
                    found.update(s for s in SERVICES if s in lowered)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(payload)
    return sorted(found & set(SERVICES))


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
        if 'STATUS_CODE_ERROR' in query:
            return .9 if value >= .05 else .6 if value > 0 else 0
        if 'histogram_quantile' in query:
            return .8 if value >= 500 else .4 if value >= 100 else 0
        if 'cpu' in query or 'memory' in query:
            return .5 if value > 0 else 0
        return .3 if value > 0 else 0
    if identifier.startswith(('trace:', 'span:')):
        return .95 if re.search(r'"error"\s*,\s*"(?:type"\s*:\s*"\w+"\s*,\s*)?"value"\s*:\s*true|exception|unavailable|connection refused|"error"\s*:\s*true|"value"\s*:\s*"ERROR"', text, re.I) else .35
    if identifier.startswith(('log:', 'dlog:')):
        return .9 if re.search(r'error|exception|failed|failure|unavailable|timeout|refused|invalid token|outofmemory', text) else .3
    return .4


def registry(result):
    records = {}
    for identifier in result.get('evidence_ids', []):
        if identifier.startswith(('container:', 'dlog:')) and identifier.split(':')[1] not in SERVICES:
            continue
        record = load_snapshot(snapshot_path(result['run_dir'], identifier), identifier)
        payload = record['data']
        records[identifier] = {'id': identifier, 'source': expected_source(identifier), 'data': payload,
                               'services': relevant_services(identifier, payload), 'strength': strength(identifier, payload)}
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
                if component in record['services'] and record['strength'] >= .5:
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
