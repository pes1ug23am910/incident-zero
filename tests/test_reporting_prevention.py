import json
from pathlib import Path
import re

import pytest

from agent.reporting import PREVENTION, build_report, prevention_for
from detect.core import load_thresholds
from reports.render import render_report
from schema.validate import fixture_resolver, validate_report
from tools.redact import is_sensitive


EXAMPLES = Path(__file__).resolve().parents[1] / 'schema' / 'examples'


@pytest.mark.parametrize('category', list(PREVENTION))
def test_category_advice_cites_evidence_and_passes_report_validation(category):
    report = json.loads((EXAMPLES / 'valid.json').read_text(encoding='utf-8'))
    cause = dict(report['root_cause'], category=category, evidence_ids=[row['id'] for row in report['evidence']])
    report['prevention'] = prevention_for([cause])
    assert PREVENTION[category] in report['prevention']
    assert all(identifier in report['prevention'] for identifier in cause['evidence_ids'])
    assert cause['component'] in report['prevention']
    assert not is_sensitive(report['prevention'])
    assert validate_report(report, resolver=fixture_resolver(EXAMPLES / 'evidence_fixture.json')) == []
    assert '\n- ' + cause['component'] + ':' in render_report(report)


def test_alert_snippets_use_supported_threshold_keys_and_current_values():
    thresholds = load_thresholds()
    for advice in PREVENTION.values():
        for key, value in re.findall(r'`([a-z_]+): ([0-9.]+)`', advice):
            assert getattr(thresholds, key) == float(value)


def test_multi_cause_prevention_preserves_distinct_evidence_without_repeating_lines():
    first = {'component': 'payment', 'category': 'application_flag', 'evidence_ids': ['trace:one']}
    second = {'component': 'cart', 'category': 'dependency_unavailable', 'evidence_ids': ['trace:two']}
    text = prevention_for([first, second, first])
    assert text.count('\n- ') == 2
    assert 'trace:one' in text and 'trace:two' in text
    assert 'Proposed safeguards' in text


def test_unknown_and_missing_evidence_do_not_invent_support():
    text = prevention_for([{'component': 'cart', 'category': 'new-category'}])
    assert 'Establish the cause' in text and 'none retained' in text
    assert 'No established cause or evidence' in prevention_for([])


def test_build_report_uses_category_prevention():
    cause = {'component': 'payment', 'category': 'application_flag', 'confidence': .8,
             'evidence_ids': ['trace:one']}
    state = {'hypotheses': [cause], 'evidence': {'trace:one': {
        'source': 'jaeger', 'data': {}, 'strength': .8, 'services': ['payment']}},
        'alert': {'signal': 'error_rate', 'service': 'payment'},
        'incident_id': 'test', 'run_id': 'runs/test'}
    report = build_report(state, {}, 0)
    assert report['prevention'] == prevention_for([cause])
