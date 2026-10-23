"""Run a bounded, read-only diagnosis and save a report bundle."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
from langgraph.checkpoint.sqlite import SqliteSaver
from jsonschema import validate
from jsonschema.exceptions import ValidationError as JSONValidationError
from tools.evidence import run_path
from schema.validate import SENSITIVE_TEXT_ERROR, validate_report
from .contracts import FUNCTIONS
from .evidence import data_projection, uncovered, validate_causes
from .graph import Investigation, build_graph
from .llm_router import ModelUnavailable, Router, now
from .prompts import SYSTEM
from .reporting import write_bundle

ROOT = Path(__file__).resolve().parents[1]


def config_for(run_id):
    return {'configurable': {'thread_id': run_id}, 'recursion_limit': 40}


def _stream(graph, inputs, config, run_dir):
    for update in graph.stream(inputs, config=config, stream_mode='updates'):
        # Only node names and timestamps; opaque interrupt internals never serialized.
        with (run_dir/'graph_updates.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'ts': now(), 'nodes': list(update)})+'\n')


def _repair_disclosure(graph, config, state, router, errors):
    """Request one replacement diagnosis using the same evidence and tool budget."""
    if (ROOT / 'STOP').exists() or state.get('stop_signal'):
        raise ValueError('STOP is latched; report repair is unavailable')
    finish = next(f for f in FUNCTIONS if f['function']['name'] == 'finish')
    safe_alert = {key: state['alert'].get(key) for key in
                  ('signal', 'service', 'observed', 'threshold', 'window_s', 'baseline')}
    context = {'alert': safe_alert, 'findings': state['findings'],
               'current_hypotheses': state.get('hypotheses', []),
               'unexplained_services': state.get('unexplained', []), 'tool_calls_left': 0}
    reason = 'Report validation rejected the diagnosis: ' + '; '.join(errors)
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': '<telemetry>\n' + json.dumps(data_projection(context), separators=(',', ':')) + '\n</telemetry>'},
                {'role': 'user', 'content': reason + '\nReturn one corrected finish decision using only the existing evidence. Remove the prohibited disclosure from the diagnosis; do not replace it with a guessed setting name. No further reads are available.'}]
    decision = router.complete(messages, [finish], purpose='report_repair')
    if decision.get('name') != 'finish':
        raise ValueError('Report repair must return a finish decision')
    arguments = decision['arguments']
    validate(arguments, finish['function']['parameters'])
    symptoms = set(state.get('symptom_services', [])) or {state['alert'].get('service', 'frontend')}
    causes = validate_causes(arguments['hypotheses'], state['evidence'], symptoms)
    clean = bool(arguments['no_incident']) and state.get('clean', False) and any(
        finding['tool'] == 'get_traces' and finding['result']['data']
        and not any(trace.get('first_error_span') for trace in finding['result']['data'])
        for finding in state['findings'])
    if arguments['no_incident'] and not clean:
        raise ValueError('Report repair cannot declare no_incident without an earlier healthy observation and successful clean trace read')
    remaining = uncovered(causes, symptoms)
    stopped = state.get('stopped_because', 'budget')
    if stopped == 'confident' and not clean and (not causes or remaining or any(cause['confidence'] < .75 for cause in causes)):
        stopped = 'budget'
    # Continue at diagnose, including risk/policy and the approval pause, on the
    # original checkpoint. No observation is repeated or tool allowance reset.
    graph.update_state(config, {'hypotheses': causes, 'unexplained': remaining,
        'done': True, 'finish_blocked': False, 'clean': clean,
        'stopped_because': stopped, 'validation_error': '',
        'audit': [{'node': 'report_repair', 'ts': now(), 'reason': reason}]}, as_node='investigate')


def run(alert, incident_id, output=None, max_tools=12, model=None, run_id=None, external_schema=None, router=None, toolset=None, resolver=None):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}', incident_id) or incident_id in ('.','..'):
        raise ValueError('incident-id must be a safe metadata slug')
    run_dir = run_path(run_id, create=True)
    run_id = run_dir.relative_to(ROOT).as_posix()
    (run_dir/'alert.json').write_text(json.dumps(alert,indent=2)+'\n',encoding='utf-8')
    router = router or Router(run_dir, model=model)
    investigation = Investigation(run_dir, router, max_tools, toolset=toolset)
    output = Path(output) if output else ROOT / 'reports' / incident_id / 'report.json'
    with SqliteSaver.from_conn_string(str(ROOT/'runs'/'checkpoints.sqlite')) as saver:
        graph = build_graph(investigation, saver)
        config = config_for(run_id)
        if graph.get_state(config).values:
            raise ValueError('Run id already exists; use a fresh run for a new investigation')
        _stream(graph, {'run_id': run_id, 'incident_id': incident_id, 'alert': alert}, config, run_dir)
        state = graph.get_state(config)
        report = state.values['report']
        # Validate against the run's retained evidence before publishing a bundle.
        errors = validate_report(report, resolver=resolver)
        disclosure_errors = [error for error in errors if error.endswith(SENSITIVE_TEXT_ERROR)]
        initial_errors = list(errors)
        if disclosure_errors:
            try:
                _repair_disclosure(graph, config, state.values, router, disclosure_errors)
                _stream(graph, None, config, run_dir)
                state = graph.get_state(config)
                report = state.values['report']
                errors = validate_report(report, resolver=resolver)
            except (ModelUnavailable, ValueError, TypeError, KeyError, JSONValidationError) as exc:
                errors = ['$: report repair failed: ' + type(exc).__name__]
        (run_dir/'validation.json').write_text(json.dumps({'errors': errors,
            'initial_errors': initial_errors, 'repair_attempted': bool(disclosure_errors)}, indent=2), encoding='utf-8')
        if errors:
            graph.update_state(config, {'done': True, 'stopped_because': 'error',
                'validation_error': '; '.join(errors[:5]), 'proposal': [],
                'status': 'needs_human'}, as_node='report')
            raise ValueError('Report validation failed: '+'; '.join(errors[:5]))
        write_bundle(report,alert,run_dir,output,getattr(router,'secrets',()),external_schema)
    return {'report': str(output), 'run_id': run_id, 'status': report['status'],
            'component': report['root_cause']['component'], 'confidence': report['root_cause']['confidence'],
            'seconds': report['agent']['elapsed_s'], 'next': list(state.next), 'model': report['agent']['model']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alert',type=Path,required=True)
    parser.add_argument('--incident-id',default=None)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--max-tools',type=int,default=12)
    parser.add_argument('--model')
    parser.add_argument('--run-id')
    parser.add_argument('--external-schema',type=Path)
    args = parser.parse_args(argv)
    os.environ.setdefault('DOCKER_HOST','tcp://localhost:2375')
    os.environ.setdefault('DOCKER_CONFIG',str(ROOT/'.build'/'docker'))
    alert = json.loads(args.alert.read_text(encoding='utf-8-sig'))
    incident_id = args.incident_id or 'unknown-'+now().replace(':','').replace('.','').replace('+','')
    try:
        result = run(alert,incident_id,args.out,args.max_tools,args.model,args.run_id,args.external_schema)
        print(json.dumps(result))
        return 0
    except (ValueError,OSError) as exc:
        print(json.dumps({'error':str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
