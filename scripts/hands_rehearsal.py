"""Operator-only live rehearsal. Never run while another session owns the stack."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
import time

from scripts.checkpoint2 import command, require_clean, check_demo_unchanged
from detect.core import Detector, write_alert
from detect.watch import wait_for_alert
from detect.recovery import clean_sample
from tools import health_table
from tools.evidence import run_path
from agent.respond import resume, save_bundle
from action_api.service import ActionService
from schema.validate import validate_report

ROOT = Path(__file__).resolve().parents[1]


def stop_after_execution(service, run_id, delay, cancelled):
    """Operator-requested STOP timer starts only when an attempt begins."""
    while not cancelled.wait(.2):
        if any(a['report_id'] == run_id and a['phase'] in ('executing', 'verifying') for a in service.attempts()):
            if not cancelled.wait(delay):
                service.stop('Operator-requested demonstration timer')
            return


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('incident')
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--svc')
    parser.add_argument('--report-id', required=True)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--reject', action='store_true')
    parser.add_argument('--stop-after-seconds', type=float)
    parser.add_argument('--prepared-stack', action='store_true', help='Demo driver already reset and verified a full clean window')
    parser.add_argument('--defer-cleanup', action='store_true', help='Outer demo driver owns reset/clean verification in finally')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', args.report_id):
        parser.error('report-id must be a safe metadata slug')
    bundle = ROOT / 'reports' / args.report_id
    if bundle.exists():
        parser.error('Report bundle exists; use a fresh id')
    if (ROOT / 'STOP').exists():
        parser.error('STOP is latched; only an operator may clear it')
    if args.stop_after_seconds is not None and not 0 < args.stop_after_seconds <= 180:
        parser.error('STOP delay must be >0 and <=180 seconds')
    if os.environ.get('INCIDENT_ZERO_TEST') == '1':
        parser.error('Unset INCIDENT_ZERO_TEST before a live rehearsal')
    os.environ.setdefault('DOCKER_HOST', 'tcp://localhost:2375')
    os.environ.setdefault('DOCKER_CONFIG', str(ROOT/'.build/docker'))
    os.environ.setdefault('DEMO_VERSION', '2.0.2')
    directory = run_path(create=True)
    timings = {}
    failed = False
    timer = None
    cancelled = threading.Event()
    try:
        if args.prepared_stack:
            clean, reason = clean_sample(health_table(lookback_s=120, run_dir=directory))
            if not clean:
                raise RuntimeError('Prepared stack no longer clean: ' + reason)
        else:
            command(['faultctl','reset','--timeout','90'], structured=True)
            check_demo_unchanged()
            require_clean(directory,360)
        detector = Detector()
        detector.prime_baseline(run_dir=directory)
        detector.poll(run_dir=directory, debounce=False)
        started = time.monotonic()
        injection = ['faultctl','inject',args.incident]
        if args.svc:
            injection += ['--svc',args.svc]
        command(injection, structured=True)
        timings['injection_s'] = round(time.monotonic()-started,3)
        alert = wait_for_alert(detector, run_dir=directory, timeout_s=90)
        if alert is None:
            raise RuntimeError('No alert within 90 seconds; no diagnosis or recovery claimed')
        path = write_alert(alert,directory)
        timings['inject_to_alert_s'] = round(time.monotonic()-started,3)
        command(['agent.run','--alert',str(path),'--incident-id',args.report_id,'--out',str(bundle/'report.json')])
        report = json.loads((bundle/'report.json').read_text(encoding='utf-8'))
        print((bundle/'report.md').read_text(encoding='utf-8'), flush=True)
        timings['inject_to_report_s'] = round(time.monotonic()-started,3)
        if report.get('proposed_actions'):
            service = ActionService(ROOT)
            if args.stop_after_seconds is not None:
                timer = threading.Thread(target=stop_after_execution,
                    args=(service, report['run_id'], args.stop_after_seconds, cancelled), daemon=True)
                timer.start()
            final = resume(report, {'decision':'reject'} if args.reject else None,
                           root=ROOT, service=service, operator=args.operator)
            save_bundle(final,bundle/'report.json',service)
            errors = validate_report(final,bundle_dir=bundle)
            if errors:
                raise RuntimeError('Report validation failed: '+'; '.join(errors[:5]))
            print(json.dumps({'status':final['status'],'report':str(bundle/'report.json')}),flush=True)
        else:
            print('No safe proposal; escalation is the result. No response was forced.',flush=True)
        timings['inject_to_finished_s'] = round(time.monotonic()-started,3)
    except (OSError, ValueError, RuntimeError) as exc:
        failed = True
        print(str(exc),flush=True)
    finally:
        cancelled.set()
        if timer:
            timer.join(2)
        if not args.defer_cleanup:
            try:
                command(['faultctl','reset','--timeout','90'],structured=True)
                check_demo_unchanged()
                require_clean(directory,360)
            except (OSError, ValueError, RuntimeError) as exc:
                failed = True
                print('Cleanup not verified: '+str(exc),flush=True)
        if (ROOT/'STOP').exists():
            print('STOP remains latched. Clear only after review with: python -m action_api clear-stop',flush=True)
        result = {'recorded_at':datetime.now(timezone.utc).isoformat(),'live':True,'timings':timings,'failed':failed}
        (directory/'hands-rehearsal.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        if bundle.is_dir():
            (bundle/'hands-rehearsal.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
