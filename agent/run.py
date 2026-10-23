"""Run a bounded, read-only diagnosis and save a report bundle."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
from langgraph.checkpoint.sqlite import SqliteSaver
from tools.evidence import run_path
from schema.validate import validate_report
from .graph import Investigation, build_graph
from .llm_router import Router, now
from .reporting import write_bundle

ROOT = Path(__file__).resolve().parents[1]


def config_for(run_id):
    return {'configurable': {'thread_id': run_id}, 'recursion_limit': 40}


def run(alert, incident_id, output=None, max_tools=12, model=None, run_id=None, external_schema=None, router=None, toolset=None):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}', incident_id) or incident_id in ('.','..'):
        raise ValueError('incident-id must be a safe metadata slug')
    run_dir = run_path(run_id, create=True)
    run_id = run_dir.relative_to(ROOT).as_posix()
    router = router or Router(run_dir, model=model)
    investigation = Investigation(run_dir, router, max_tools, toolset=toolset)
    output = Path(output) if output else ROOT / 'reports' / incident_id / 'report.json'
    with SqliteSaver.from_conn_string(str(ROOT/'runs'/'checkpoints.sqlite')) as saver:
        graph = build_graph(investigation, saver)
        config = config_for(run_id)
        if graph.get_state(config).values:
            raise ValueError('Run id already exists; use a fresh run for a new investigation')
        for update in graph.stream({'run_id': run_id, 'incident_id': incident_id, 'alert': alert}, config=config, stream_mode='updates'):
            # Only node names and timestamps; opaque interrupt internals never serialized.
            with (run_dir/'graph_updates.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'ts':now(),'nodes':list(update)})+'\n')
        state = graph.get_state(config)
        report = state.values['report']
        write_bundle(report,alert,run_dir,output,getattr(router,'secrets',()),external_schema)
        errors = validate_report(report,bundle_dir=output.parent)
        (run_dir/'validation.json').write_text(json.dumps({'errors':errors},indent=2),encoding='utf-8')
        if errors:
            raise ValueError('Report validation failed: '+'; '.join(errors[:5]))
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
