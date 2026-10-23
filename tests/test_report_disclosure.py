"""Reject generated setting disclosures and repair once before publishing."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

import agent.run as runner
from agent.graph import Investigation, build_graph
from agent.replay import ReplayRouter, ReplayTools
from schema.validate import SENSITIVE_TEXT_ERROR, fixture_resolver, validate_report
from tools.redact import FLAG_NAMES
from test_agent_offline import offline_graph, synthetic_fixture


EXAMPLES = Path(__file__).resolve().parents[1] / 'schema' / 'examples'
LEAK = 'The paymentFailure feature flag was switched to its 100% variant.'


@pytest.mark.parametrize('disclosure', [LEAK, *FLAG_NAMES, 'Feature-Flag', 'problempattern', 'PROBLEMPATTERN enabled', 'flagd'])
def test_every_sensitive_report_string_is_rejected_with_path_only(disclosure):
    report = json.loads((EXAMPLES / 'valid.json').read_text(encoding='utf-8'))
    report['root_cause']['cause'] = disclosure
    errors = validate_report(report, resolver=fixture_resolver(EXAMPLES / 'evidence_fixture.json'))
    assert '$.root_cause.cause: ' + SENSITIVE_TEXT_ERROR in errors
    assert all(disclosure not in error for error in errors)


def repair_fixture(root, *, persistent=False, exhausted=False):
    fixture = synthetic_fixture(root)
    model_file = fixture / 'llm.jsonl'
    models = [json.loads(line) for line in model_file.read_text(encoding='utf-8').splitlines()]
    finish = models[1]['response']['tool_calls'][0]['function']
    clean_arguments = json.loads(finish['arguments'])
    leaking_arguments = deepcopy(clean_arguments)
    leaking_arguments['hypotheses'][0]['cause'] = LEAK
    finish['arguments'] = json.dumps(leaking_arguments)
    if exhausted:
        tools_file = fixture / 'tools.jsonl'
        reads = [json.loads(line) for line in tools_file.read_text(encoding='utf-8').splitlines()]
        expanded_reads, expanded_models = [reads[0]], []
        for index in range(11):
            read, model = deepcopy(reads[1]), deepcopy(models[0])
            read.update(step=index + 2)
            read['arguments']['lookback_s'] = 120 + index
            call = model['response']['tool_calls'][0]['function']
            arguments = json.loads(call['arguments'])
            arguments['lookback_s'] = 120 + index
            if index == 10:
                arguments['hypotheses'] = leaking_arguments['hypotheses']
            call['arguments'] = json.dumps(arguments)
            expanded_reads.append(read)
            expanded_models.append(model)
        tools_file.write_text(''.join(json.dumps(row) + '\n' for row in expanded_reads), encoding='utf-8')
        models = expanded_models
    repaired = deepcopy(models[0])
    repaired['response']['tool_calls'][0]['function'] = {
        'name': 'finish', 'arguments': json.dumps(leaking_arguments if persistent else clean_arguments)}
    models.append(repaired)
    model_file.write_text(''.join(json.dumps(row) + '\n' for row in models), encoding='utf-8')
    return fixture


def execute_fixture(root, fixture, monkeypatch):
    router = ReplayRouter(fixture, 'disclosure-repair')
    reads = ReplayTools(fixture)
    written = []
    original_write = runner.write_bundle
    def checked_write(report, *args, **kwargs):
        assert validate_report(report, resolver=reads.resolve) == []
        written.append(deepcopy(report))
        return original_write(report, *args, **kwargs)
    monkeypatch.setattr(runner, 'write_bundle', checked_write)
    return router, reads, written, {
        'alert': json.loads((fixture / 'alert.json').read_text(encoding='utf-8')),
        'incident_id': 'synthetic-disclosure', 'run_id': 'disclosure-repair',
        'output': root / 'reports' / 'repaired' / 'report.json',
        'router': router, 'toolset': reads.toolset(), 'resolver': reads.resolve}


@pytest.mark.parametrize('exhausted', [False, True])
def test_report_repair_runs_once_without_repeating_reads_or_resetting_budget(offline_graph, monkeypatch, exhausted):
    fixture = repair_fixture(offline_graph, exhausted=exhausted)
    router, reads, written, arguments = execute_fixture(offline_graph, fixture, monkeypatch)
    result = runner.run(**arguments)
    router.assert_complete()
    reads.assert_complete()
    assert len(written) == 1
    assert written[0]['agent']['tool_calls'] == (12 if exhausted else 2)
    assert written[0]['root_cause']['component'] == 'recommendation'
    assert LEAK not in json.dumps(written[0])
    assert result['next'] == ['approval']
    repair_call = router.entries[-1]
    assert repair_call['purpose'] == 'report_repair'
    assert [tool['function']['name'] for tool in repair_call['request']['tools']] == ['finish']
    assert '$.root_cause.cause: ' + SENSITIVE_TEXT_ERROR in repair_call['request']['messages'][-1]['content']
    validation = json.loads((offline_graph / result['run_id'] / 'validation.json').read_text(encoding='utf-8'))
    assert validation['repair_attempted'] and not validation['errors']


def test_persistent_disclosure_refuses_bundle_and_ends_checkpoint_after_one_retry(offline_graph, monkeypatch):
    fixture = repair_fixture(offline_graph, persistent=True)
    router, reads, written, arguments = execute_fixture(offline_graph, fixture, monkeypatch)
    with pytest.raises(ValueError, match=r'Report validation failed: \$.root_cause.cause'):
        runner.run(**arguments)
    router.assert_complete()
    reads.assert_complete()
    assert len(router.entries) == 3
    assert not written and not arguments['output'].parent.exists()
    with SqliteSaver.from_conn_string(str(offline_graph / 'runs' / 'checkpoints.sqlite')) as saver:
        graph = build_graph(Investigation(router.run_dir, router, toolset=reads.toolset()), saver)
        state = graph.get_state(runner.config_for('runs/disclosure-repair'))
        assert not state.next
        assert state.values['tool_calls_used'] == 2
        assert state.values['stopped_because'] == 'error'
        assert state.values['proposal'] == []


def test_malformed_repair_is_recorded_without_a_bundle(offline_graph, monkeypatch):
    fixture = repair_fixture(offline_graph)
    path = fixture / 'llm.jsonl'
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    rows[-1]['response']['tool_calls'][0]['function']['arguments'] = '{}'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    router, reads, written, arguments = execute_fixture(offline_graph, fixture, monkeypatch)
    with pytest.raises(ValueError, match='report repair failed: ValidationError'):
        runner.run(**arguments)
    router.assert_complete()
    assert not written and not arguments['output'].parent.exists()


def test_stop_latched_after_validation_prevents_repair_call(offline_graph, monkeypatch):
    fixture = repair_fixture(offline_graph)
    router, reads, written, arguments = execute_fixture(offline_graph, fixture, monkeypatch)
    original_validate = runner.validate_report
    def latch_stop(report, **kwargs):
        errors = original_validate(report, **kwargs)
        (offline_graph / 'STOP').touch()
        return errors
    monkeypatch.setattr(runner, 'validate_report', latch_stop)
    with pytest.raises(ValueError, match='report repair failed: ValueError'):
        runner.run(**arguments)
    assert len(router.entries) == 2
    assert not written and not arguments['output'].parent.exists()
