"""A failed model decision cannot become a successful diagnosis or proposal."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import validate

from agent.graph import Investigation
from agent.llm_router import ModelUnavailable
from agent.policy import propose
from agent.reporting import build_report
from schema.validate import validate_report


class FailedRouter:
    def complete(self, *args, **kwargs):
        raise ModelUnavailable('All configured structured model routes failed. openrouter/fixture/model: SSLError: TLS handshake ended')

    def summary(self):
        return {'model': 'failed: openrouter/fixture/model', 'models_used': [], 'llm_calls': 2,
                'tokens_input': 0, 'tokens_output': 0, 'estimated_cost_usd': 0}


def investigation_state(prior_cause):
    identifier = 'container:recommendation:Status=exited'
    evidence = {identifier: {'id': identifier, 'source': 'docker', 'services': ['recommendation'],
                            'strength': 1, 'data': {'name': 'recommendation', 'field': 'Status', 'value': 'exited'}}}
    causes = [{'component': 'recommendation', 'category': 'container_down', 'cause': 'The service is exited with correlated failed calls.',
               'confidence_model': .9, 'confidence_evidence': .9, 'confidence': .9,
               'evidence_ids': [identifier], 'explains_symptoms': ['recommendation'], 'alternatives_considered': []}] if prior_cause else []
    health = {'data': [{'service': 'recommendation', 'status': 'exited'}], 'evidence_ids': [identifier]}
    return {'run_id': 'runs/failure-fixture', 'incident_id': 'failure-fixture',
            'alert': {'signal': 'container_health', 'service': 'recommendation', 'observed': 0,
                      'threshold': 1, 'window_s': 120, 'detected_at': '2026-10-23T10:00:00+00:00'},
            'findings': [{'step': 1, 'tool': 'health_table', 'arguments': {'lookback_s': 120},
                          'why': 'Inspect service health.', 'result': health}],
            'health': health, 'evidence': evidence, 'hypotheses': causes, 'tool_calls_used': 1,
            'unexplained': ['recommendation'], 'symptom_services': ['recommendation'], 'clean': False}


@pytest.mark.parametrize('prior_cause', [False, True])
def test_model_failure_keeps_evidence_and_never_proposes_even_with_prior_confidence(tmp_path, monkeypatch, prior_cause):
    monkeypatch.setattr('agent.graph.ROOT', tmp_path)
    state = investigation_state(prior_cause)
    original = deepcopy(state)
    router = FailedRouter()
    update = Investigation(tmp_path, router).investigate(state)
    assert update['stopped_because'] == 'error'
    report = propose(build_report({**state, **update}, router.summary(), 1.5))
    assert report['agent']['model'] == 'failed: openrouter/fixture/model'
    assert report['agent']['stopped_because'] == 'error'
    assert report['status'] == 'needs_human'
    assert report['proposed_actions'] == [] and report['proposed_action'] is None
    assert report['investigation'][0]['tool'] == 'health_table'
    assert report['evidence'][0]['id'] == 'container:recommendation:Status=exited'
    assert any('SSLError: TLS handshake ended' in item for item in report['limitations'])
    assert 'Diagnosis stopped on an error' in report['escalation_note']
    if prior_cause:
        assert report['root_causes'] == original['hypotheses']
    else:
        assert report['root_cause']['category'] == 'unknown'
        assert report['root_cause']['confidence_model'] == report['root_cause']['confidence'] == 0
        assert 'Diagnosis failed' in report['root_cause']['cause']
    schema = json.loads((Path(__file__).resolve().parents[1] / 'schema' / 'incident_report.schema.json').read_text())
    validate(report, schema)
    assert state == original


def test_later_cart_failure_is_cited_as_investigation_context_without_rewriting_alert():
    state = investigation_state(False)
    container_id = 'container:valkey-cart:Status=exited'
    log_id = 'log:otel/later-cart-connection-error'
    state['alert']['service'] = 'valkey-cart'
    original_alert = deepcopy(state['alert'])
    state['health'] = {'data': [{'service': 'valkey-cart', 'status': 'exited'},
                               {'service': 'cart', 'status': 'running', 'error_rate': 0}],
                       'evidence_ids': [container_id]}
    state['evidence'] = {
        container_id: {'id': container_id, 'source': 'docker', 'services': ['valkey-cart'], 'strength': 1,
                       'data': {'name': 'valkey-cart', 'field': 'Status', 'value': 'exited'}},
        log_id: {'id': log_id, 'source': 'opensearch', 'services': ['cart', 'valkey-cart'], 'strength': .9,
                 'data': {'resource': {'service.name': 'cart'}, 'body': "Wasn't able to connect to redis"}},
    }
    state['findings'][0]['result'] = state['health']
    state['findings'].append({'step': 2, 'tool': 'get_logs', 'arguments': {'service': 'cart'},
        'why': 'Check whether caller failures have arrived.',
        'result': {'data': [state['evidence'][log_id]['data']], 'evidence_ids': [log_id]}})
    state.update(symptom_services=['valkey-cart', 'cart'], tool_calls_used=2, unexplained=[],
        stopped_because='confident', hypotheses=[{'component': 'valkey-cart',
        'cause': 'The stopped cache is unavailable to cart requests.', 'category': 'dependency_unavailable',
        'confidence_model': .9, 'confidence_evidence': .9, 'confidence': .9,
        'evidence_ids': [container_id, log_id], 'explains_symptoms': ['cart', 'valkey-cart'],
        'alternatives_considered': []}])
    model = {'model': 'fixture-model', 'models_used': ['fixture-model'], 'llm_calls': 2,
             'tokens_input': 0, 'tokens_output': 0, 'estimated_cost_usd': 0}
    report = propose(build_report(state, model, 1))
    cart = next(symptom for symptom in report['symptoms'] if symptom['service'] == 'cart')
    assert cart['signal'] == 'investigation_context'
    assert cart['evidence_ids'] == [log_id]
    assert 'after the initial health overview' in cart['observed']
    assert report['alert']['service'] == 'valkey-cart'
    assert report['detected_at'] == original_alert['detected_at']
    assert state['alert'] == original_alert
    assert report['root_cause']['explains_symptoms'] == ['cart', 'valkey-cart']
    assert validate_report(report, resolver=lambda identity: state['evidence'][identity]) == []
