"""Opt-in Qwen/ADK execution smoke test using an existing reviewed FODO input."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / 'python-agent'))
from agent import run_task
from smoke_magnus import exercise as prepare_reviewed_fixture
from tools.file_tools import WorkspaceFiles


def records(root):
    trace = root / 'trace.jsonl'
    return [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []


def successful_results(events, name):
    return [r['response'] for r in events if r['event'] == 'tool_result'
            and r['name'] == name and 'error' not in r['response']]


async def exercise(root, max_calls):
    files = WorkspaceFiles(root)
    root = files.root
    started = time.monotonic()
    report = {'mode': 'qwen_execution', 'workspace': str(root), 'success': False,
              'native_parser': 'SKIPPED_NOT_AVAILABLE'}
    previous_events = len(records(root))
    try:
        # Reuse the hash-pinned review evidence, but copy the user-requested generator input.
        if await prepare_reviewed_fixture(root, False, 600) != 0:
            raise RuntimeError('Reviewed fixture preparation failed; inspect report.json')
        source = REPOSITORY / 'tests/lattice-generator/fodo-no-spacecharge/input/FODO-no-spacecharge.in'
        payload = source.read_bytes()
        target = files._path('input/FODO-no-spacecharge.in')
        if target.read_bytes() != payload:
            raise ValueError('Requested generator fixture does not match the pinned reviewed input')
        target.write_bytes(payload)
        report['input_source'] = str(source.relative_to(REPOSITORY))
        report['input_sha256'] = hashlib.sha256(payload).hexdigest()
        prior_jobs = {r['job_id'] for r in successful_results(records(root), 'submit_opalx_simulation')}
        task = (
            'Execute the already-reviewed FODO input through Magnus and retrieve its outputs. '
            'Use simulation="input" and input_file="FODO-no-spacecharge.in". '
            'The operator has enabled Magnus and submission and supplied validation.json at task start. '
            'The review is in review.md and the original specification is in specification.md. '
            'Discover and consult the opalx-simulator and magnus skills once each. '
            'Inspect the backend, submit the prepared input, check the returned job ID status, '
            'read a bounded portion of its logs, and retrieve the outputs when complete. '
            'Do not generate or edit the input, validation report, or physics parameters. '
            'Do not use shell commands or blueprint registration. '
            'Report the job ID, simulation return code, and retrieved output path. '
            'Do not claim completion without successful tool results.'
        )
        if prior_jobs:
            task += ' Existing recorded job IDs: ' + ', '.join(sorted(prior_jobs)) + '. Resume these; do not submit a new job.'
        files._path('task.md').write_text(task)
        result = await run_task(task, root, max_calls=max_calls, trace='trace.jsonl',
                                enable_magnus=True, allow_simulation=True,
                                validation_report='validation.json')
        files._path('response.txt').write_text(result.response)
        events = records(root)
        report['model'] = next((r['model'] for r in reversed(events[previous_events:])
                                if r['event'] == 'start'), None)
        assert successful_results(events, 'list_skills'), 'No successful skill discovery'
        loaded = {r.get('skill') for r in successful_results(events, 'load_skill') if r.get('content')}
        assert {'opalx-simulator', 'magnus'} <= loaded, 'Model did not load both execution skills'
        assert any(r.get('compatible') for r in successful_results(events, 'inspect_opalx_backend')), \
            'Model did not confirm the backend interface'
        submitted = successful_results(events, 'submit_opalx_simulation')
        jobs = {r['job_id'] for r in submitted}
        assert len(jobs) == 1, f'Expected one recorded execution job, got {jobs}'
        job_id = next(iter(jobs))
        assert any(r.get('job_id') == job_id for r in successful_results(events, 'get_opalx_job_status')), \
            'No successful model-driven status inspection'
        assert any(r.get('job_id') == job_id for r in successful_results(events, 'read_opalx_job_logs')), \
            'No successful model-driven log retrieval'
        retrieved = [r for r in successful_results(events, 'retrieve_opalx_outputs')
                     if r.get('job_id') == job_id and r.get('simulation_success')
                     and r.get('outputs_retrieved')]
        assert retrieved, 'No successful model-driven simulation/output retrieval'
        output = retrieved[-1]
        destination = files._path(output['output_path'])
        assert hashlib.sha256(target.read_bytes()).hexdigest() == report['input_sha256'], 'Input was modified'
        assert hashlib.sha256((destination/'FODO-no-spacecharge.in').read_bytes()).hexdigest() == report['input_sha256']
        stat = destination/'FODO-no-spacecharge.stat'
        assert stat.stat().st_size and stat.read_bytes().startswith(b'SDDS1'), 'Invalid statistics file'
        import h5py
        with h5py.File(destination/'FODO-no-spacecharge.h5') as data:
            steps = [k for k in data if k.startswith('Step#')]
            assert any('x' in data[k] and data[k]['x'].size for k in steps), 'No particle snapshots'
        report.update(success=True, job_id=job_id, output_path=output['output_path'],
                      returncode=output['returncode'], particle_snapshots=len(steps))
        return 0
    except BaseException as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt)):
            raise
        return 1
    finally:
        events = records(root)
        report['elapsed_seconds'] = round(time.monotonic()-started, 2)
        report['tool_calls'] = [r['name'] for r in events if r['event'] == 'tool_call']
        report['job_ids'] = sorted({r['job_id'] for r in successful_results(events, 'submit_opalx_simulation')})
        report['model_usage'] = [{k: v for k, v in r.items() if k != 'event'}
                                 for r in events if r['event'] == 'model_usage']
        files._path('qwen-report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', required=True,
                        help='Authorize the live model and simulation execution test')
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--max-calls', type=int, default=16)
    args = parser.parse_args()
    if args.max_calls < 1:
        parser.error('--max-calls must be positive')
    os.environ.setdefault('ACCELERATOR_AGENT_TIMEOUT', '1200')
    os.environ.setdefault('ACCELERATOR_AGENT_MAX_TOKENS', '512')
    root = args.workspace or REPOSITORY / 'output/python-agent' / (
        'qwen-execution-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    print(f'Workspace: {root.resolve()}', flush=True)
    try:
        return asyncio.run(exercise(root, args.max_calls))
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main())
