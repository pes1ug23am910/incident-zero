"""Inspect or reject the exact paused graph; execution is a later deliverable."""
import argparse
import json
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from .graph import Investigation, build_graph
from .llm_router import Router
from .run import config_for, ROOT


def resume(report, decision):
    run_id = report['run_id']
    with SqliteSaver.from_conn_string(str(ROOT/'runs'/'checkpoints.sqlite')) as saver:
        graph = build_graph(Investigation(ROOT/run_id, Router(ROOT/run_id)),saver)
        config = config_for(run_id)
        if graph.get_state(config).next != ('approval',):
            raise ValueError('Checkpoint is not waiting at approval; refusing a mismatched resume')
        if (ROOT/'STOP').exists():
            raise ValueError('STOP is latched')
        if decision.get('decision') != 'reject':
            raise ValueError('Action API is unavailable in this brain-only build; no approval token can be minted or executed')
        graph.invoke(Command(resume=decision),config=config)
        return graph.get_state(config).values['report']


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--reject',action='store_true')
    args=parser.parse_args(argv)
    report=json.loads(args.report.read_text(encoding='utf-8'))
    try:
        result=resume(report,{'decision':'reject'} if args.reject else {'decision':'approve'})
        args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        from reports.render import render_report
        args.report.with_suffix('.md').write_text(render_report(result),encoding='utf-8')
        print('Rejected; no action executed.')
        return 0
    except ValueError as exc:
        print(str(exc))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
