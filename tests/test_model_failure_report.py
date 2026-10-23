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
