import json

import pytest

from eval.calibration import case_for_incident, evaluate_bundles, load_cases, main, wilson_interval
from test_calibration import make_report


def bundle(root, name, incident_id, confidence, component='payment', category='application_flag'):
    report = make_report(component, category, confidence)
    report['incident_id'] = incident_id
    path = root / name / 'report.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(report), encoding='utf-8')
    return path


def test_synthetic_bundles_score_hits_misses_unlabelled_and_abstention(tmp_path):
    bundle(tmp_path, 'a', 'payment-failure-r1', .8)
    bundle(tmp_path, 'b', 'payment-failure-loop-r2', .8, component='cart')
    bundle(tmp_path, 'c', 'unrecognised', .99)
    bundle(tmp_path, 'd', 'payment-failure-r3', .3, category='unknown')
    # Other bundle metadata is neither read nor interpreted as a report.
    (tmp_path / 'a' / 'checkpoint2.json').write_text('invalid json')
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    summary = evaluate_bundles(tmp_path)
    assert summary['bundle_count'] == 4 and summary['calibration_count'] == 2
    assert summary['excluded_count'] == 1
    assert summary['unlabelled'][0]['correct'] is None
    assert summary['brier'] == pytest.approx(.34)
    bucket = summary['bundle_buckets'][2]
    assert bucket['count'] == 2 and bucket['correct'] == 1 and bucket['hit_rate'] == .5
    assert bucket['wilson_95'] == pytest.approx(wilson_interval(1, 2))
    assert summary['bundle_buckets'][3]['unlabelled'] == 1
    assert summary['bundle_buckets'][0]['excluded'] == 1
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize('confidence,bucket_index', [(0, 0), (.6, 1), (.75, 2), (.9, 3), (1, 3)])
def test_bucket_boundaries_include_endpoints(tmp_path, confidence, bucket_index):
    bundle(tmp_path, 'a', 'payment-failure', confidence)
    summary = evaluate_bundles(tmp_path)
    assert summary['bundle_buckets'][bucket_index]['count'] == 1
    assert sum(row['count'] for row in summary['bundle_buckets']) == 1


def test_matching_is_conservative_and_never_uses_predicted_cause():
    cases = load_cases()
    assert case_for_incident('container-stopped-loop-r1', cases) == 'container-stopped-recommendation'
    assert case_for_incident('combo-payment-recommendation-r1', cases) == 'combo-payment-recommendation'
    assert case_for_incident('stable09-payment-on-r2', cases) is None
    assert case_for_incident('mock-payment-approved', cases) is None
    assert case_for_incident('payment-failure-other', cases) is None
    cases['ambiguous'] = dict(cases['container-stopped-recommendation'])
    assert case_for_incident('container-stopped-r1', cases) is None


def test_cli_empty_and_unlabelled_data_is_not_a_zero_score(tmp_path, capsys):
    assert main([str(tmp_path)]) == 0
    assert 'not measured' in capsys.readouterr().out
    bundle(tmp_path, 'payment-failure', 'arbitrary', .95)
    assert main([str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert 'unlabelled: 1' in output and 'Small-sample caveat' in output
    assert 'Wilson 95%' in output and 'Brier score (labelled cause-confidence samples): not measured' in output


@pytest.mark.parametrize('confidence', [-.1, 1.1, float('nan'), float('inf')])
def test_invalid_unlabelled_confidence_fails_explicitly(tmp_path, capsys, confidence):
    bundle(tmp_path, 'a', 'unlabelled', confidence)
    assert main([str(tmp_path)]) == 1
    assert 'Evaluation failed' in capsys.readouterr().out
