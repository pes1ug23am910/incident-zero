"""Correct retained approval presentation using the immutable bundled audit log.

This migration never edits audit entries or evidence snapshots. Legacy `human`
labels alone do not prove a human decision. Known automated browser runs must be
identified explicitly by the operator, with their retained acceptance record.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from reports.render import render_report


def migrate_bundle(path: Path, *, automated_browser=False):
    path = Path(path)
    report = json.loads(path.read_text(encoding='utf-8'))
    original = deepcopy(report)
    log_path = path.parent / 'action-log.jsonl'
    entries = [json.loads(line) for line in log_path.read_text(encoding='utf-8').splitlines() if line.strip()] if log_path.exists() else []
    entries = [entry for entry in entries if entry.get('report_id') == report['run_id']]
    events = [entry for entry in entries if entry.get('event') in {'approval_granted', 'approval_rejected'}]
    rehearsal_path = path.parent / 'hands-rehearsal.json'
    rehearsal = json.loads(rehearsal_path.read_text(encoding='utf-8')) if rehearsal_path.exists() else {}
    synthetic = any('SYNTHETIC MOCK' in item for item in report.get('limitations', []))
    synthetic |= 'mock' in report.get('agent', {}).get('model', '').lower()

    def metadata(entry):
        browser = any(item.get('event') == 'ui_approval' for item in entries)
        if automated_browser:
            if not browser:
                raise ValueError('Automated-browser migration requires a retained ui_approval event')
            mode, surface = 'test', 'browser'
        elif entry.get('mode') == 'test' or rehearsal.get('approval_path') == 'test_auto' or synthetic:
            mode, surface = 'test', entry.get('surface', 'test')
        elif entry.get('mode') == 'live' and entry.get('surface') in {'cli', 'browser'}:
            mode, surface = 'live', entry['surface']
        elif entry.get('event') == 'approval_rejected' and rehearsal.get('rejection_immutability') is not None:
            mode, surface = 'live', 'cli'
        else:
            # Do not turn the old, unverified `human` label into new evidence.
            mode, surface = None, 'browser' if browser else None
        token_id = 'sha256:' + entry['token_digest'] if entry.get('token_digest') else None
        return {'mode': mode, 'surface': surface, 'token_id': token_id,
                'approved_by': 'test harness' if mode == 'test' else entry.get('approved_by', entry.get('actor'))}

    approval = report['approval']
    if approval.get('approved') is not None:
        kind = 'approval_granted' if approval['approved'] else 'approval_rejected'
        matches = [event for event in events if event['event'] == kind]
        if not matches:
            raise ValueError(f'{path}: decided approval has no matching audit event')
        event = matches[-1]
        approval.update(metadata(event))
        if approval.get('approved'):
            approval['token'] = approval['token_id']
        for history, event in zip(report.get('action_history', []), events):
            history['decision'].update(metadata(event))
            if event['event'] == 'approval_granted':
                history['decision']['token'] = history['decision']['token_id']
        note = 'Historical approval provenance was corrected from the retained action log; the original audit entries and evidence snapshots are unchanged. Prompt-shown time was not recorded, so requested_at retains its original value.'
        if automated_browser:
            note += ' This browser approval was driven by an automated acceptance driver, not a human operator.'
        if rehearsal.get('rejection_immutability') is not None:
            note += ' Rejection was supplied by the explicit CLI reject option, not a typed response.'
        report.setdefault('limitations', [])
        if note not in report['limitations']:
            report['limitations'].append(note)
        if rehearsal and approval.get('surface'):
            corrected = deepcopy(rehearsal)
            corrected['approval_surface'] = approval['surface']
            corrected['approval_mode'] = approval['mode']
            if corrected.get('rejection_immutability') is not None:
                corrected['approval_path'] = 'cli_reject_flag'
            if corrected != rehearsal:
                rehearsal_path.write_text(json.dumps(corrected, indent=2) + '\n', encoding='utf-8')
    else:
        for field in ('surface', 'mode', 'token_id'):
            approval.setdefault(field, None)
    changed = report != original
    if changed:
        path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    rendered = render_report(report)
    md_path = path.with_suffix('.md')
    if not md_path.exists() or md_path.read_text(encoding='utf-8') != rendered:
        md_path.write_text(rendered, encoding='utf-8')
    return {'bundle': path.parent.name, 'changed': changed,
            'surface': approval.get('surface'), 'mode': approval.get('mode'),
            'approved': approval.get('approved'), 'token_id': approval.get('token_id')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--automated-browser', action='append', default=[])
    args = parser.parse_args(argv)
    for path in sorted(args.root.glob('*/report.json')):
        print(json.dumps(migrate_bundle(path, automated_browser=path.parent.name in args.automated_browser)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
