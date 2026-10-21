"""Opt-in real OPALX adapter smoke test using one pinned, reviewed fixture. No LLM."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / 'python-agent'))
from tools.magnus_tools import MagnusTools
from tools.file_tools import WorkspaceFiles


def checked(value):
    if 'error' in value:
        raise RuntimeError(value['error'])
    return value


async def exercise(root, execute, wait_seconds):
    files = WorkspaceFiles(root)
    report = {'success': False, 'workspace': str(files.root), 'llm_used': False,
              'stages': {'native_parser': 'SKIPPED_NOT_AVAILABLE'}}
    started = time.monotonic()

    def event(name, **data):
        elapsed = round(time.monotonic() - started, 2)
        row = {'event': name, 'elapsed_seconds': elapsed, **data}
        with files._path('events.jsonl').open('a') as stream:
            stream.write(json.dumps(row) + '\n')
        report['elapsed_seconds'] = elapsed
        files._path('report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'[{elapsed:6.1f}s] {name}: {json.dumps(data)}', flush=True)

    try:
        manifest = json.loads((Path(__file__).parent / 'fixtures/reviewed_fodo.json').read_text())
        names = {'input': 'input/FODO-no-spacecharge.in', 'specification': 'specification.md',
                 'review': 'review.md'}
        for kind, relative in names.items():
            source = REPOSITORY / manifest[kind]['path']
            payload = source.read_bytes()
            if hashlib.sha256(payload).hexdigest() != manifest[kind]['sha256']:
                raise ValueError(f'Reviewed {kind} changed: review it before updating the manifest')
            target = files._path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != payload:
                raise ValueError(f'Refusing to replace changed workspace file: {relative}')
            target.write_bytes(payload)
        inspector = MagnusTools(files.root)
        info = checked(await inspector.inspect_simulation_input('input', 'FODO-no-spacecharge.in'))
        approval = {**info, 'status': 'PASS', 'checks': manifest['checks'],
                    'evidence': {'review': 'review.md', 'specification': 'specification.md',
                                 'fixture': 'tests/python_agent/fixtures/reviewed_fodo.json'}}
        files._path('validation.json').write_text(json.dumps(approval, indent=2) + '\n')
        report['stages'].update(preparation='PASS', validation='PASS_UNDER_CURRENT_POLICY')
        report['input_digest'] = info['input_digest']
        event('fixture_prepared', input_digest=info['input_digest'])
        if not execute:
            report.update(prepared=True, message='Prepared only. Use --execute to submit or reconnect.')
            event('prepared_only')
            return 0
        inspection = checked(await inspector.inspect_opalx_backend())
        if not inspection['compatible']:
            raise ValueError('Registered OPALX blueprint is incompatible')
        report['stages']['backend_inspection'] = 'PASS'
        files._path('backend-schema.json').write_text(json.dumps(inspection, indent=2) + '\n')
        event('backend_inspected')
        tools = MagnusTools(files.root, True, 'validation.json')
        submitted = checked(await tools.submit_opalx_simulation('input', 'FODO-no-spacecharge.in'))
        job_id = submitted['job_id']
        report.update(job_id=job_id, record=submitted['record'])
        report['stages']['submission'] = 'PASS'
        event('job_recorded', job_id=job_id, reused=submitted['reused'])
        # A fresh client must reuse this job, not submit another one.
        resumed = MagnusTools(files.root, True, 'validation.json')
        same = checked(await resumed.submit_opalx_simulation('input', 'FODO-no-spacecharge.in'))
        if same['job_id'] != job_id or not same['reused']:
            raise RuntimeError('Duplicate-submission protection failed')
        report['stages']['reconnection'] = 'PASS'
        event('reconnected_without_resubmitting', job_id=job_id)
        deadline = time.monotonic() + wait_seconds
        while True:
            status = checked(await resumed.get_opalx_job_status(job_id))
            report['last_status'] = status
            event('job_status', job_id=job_id, status=status['status'])
            if status['terminal']:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Stopped waiting; backend job may continue. Resume with the same workspace.')
            await asyncio.sleep(min(5, max(0, deadline - time.monotonic())))
        logs = await resumed.read_opalx_job_logs(job_id, max_chars=6000)
        files._path('logs.json').write_text(json.dumps(logs, indent=2) + '\n')
        report['stages']['logs'] = 'PASS' if 'error' not in logs else 'FAIL'
        output = checked(await resumed.retrieve_opalx_outputs(job_id))
        report.update(output_path=output['output_path'], retrieval_result=output)
        report['stages']['retrieval'] = 'PASS'
        event('outputs_retrieved', output_path=output['output_path'])
        if not status['simulation_success']:
            raise RuntimeError(f'OPALX did not succeed: {status}')
        report['stages']['simulation'] = 'PASS'
        destination = files._path(output['output_path'])
        main = destination / 'FODO-no-spacecharge.in'
        if hashlib.sha256(main.read_bytes()).hexdigest() != manifest['input']['sha256']:
            raise RuntimeError('Retrieved input differs from the reviewed input')
        stat, h5 = destination/'FODO-no-spacecharge.stat', destination/'FODO-no-spacecharge.h5'
        if not stat.is_file() or stat.stat().st_size == 0 or not stat.read_bytes().startswith(b'SDDS1'):
            raise RuntimeError('Missing/empty/unrecognized statistics output')
        import h5py
        with h5py.File(h5) as data:
            steps = [k for k in data if k.startswith('Step#')]
            if not steps or not any('x' in data[k] and data[k]['x'].size > 0 for k in steps):
                raise RuntimeError('HDF5 has no nonempty particle snapshot')
        if 'error' in logs:
            raise RuntimeError(f'Log retrieval failed: {logs["error"]}')
        report.update(success=True, outputs={'stat_bytes': stat.stat().st_size,
                      'h5_bytes': h5.stat().st_size, 'particle_snapshots': len(steps)})
        report['stages']['output_checks'] = 'PASS'
        event('smoke_passed', **report['outputs'])
        return 0
    except BaseException as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        event('smoke_failed', error=report['error'])
        if isinstance(exc, (KeyboardInterrupt, asyncio.CancelledError)):
            raise
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Submit/reconnect to a real Magnus job')
    parser.add_argument('--workspace', type=Path, help='Reuse this workspace to resume the same job')
    parser.add_argument('--wait-seconds', type=float, default=600)
    args = parser.parse_args()
    if args.wait_seconds <= 0:
        parser.error('--wait-seconds must be positive')
    root = args.workspace or REPOSITORY / 'output/python-agent' / (
        'magnus-smoke-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    print(f'Workspace: {root.resolve()}', flush=True)
    try:
        return asyncio.run(exercise(root, args.execute, args.wait_seconds))
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main())
