"""Opt-in live skill smoke tests; keep artifacts and traces for inspection."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / 'python-agent'))
from agent import run_task


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['discovery', 'fodo'], nargs='?', default='discovery')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    workspace = REPOSITORY / 'output/python-agent' / f'{args.mode}-{stamp}'
    workspace.mkdir(parents=True)
    if args.mode == 'discovery':
        # Keep the first CPU check small; explicit operator overrides still win.
        os.environ.setdefault('ACCELERATOR_AGENT_MAX_TOKENS', '512')
        os.environ.setdefault('ACCELERATOR_AGENT_CONTEXT', '4096')
        task = ('List the skills available to you using the discovery tool, then report their names. '
                'This is only a discovery check: do not load full instructions, read references, '
                'create input files, or execute anything.')
        max_calls = 4
    else:
        # Allow longer CPU inference for skill/reference-heavy generation requests.
        os.environ.setdefault('ACCELERATOR_AGENT_TIMEOUT', '1200')
        # Only the benchmark request is supplied; no existing benchmark output is read.
        task = (REPOSITORY / 'tests/lattice-generator/fodo-no-spacecharge/input-prompt.md').read_text()
        task += ('\n\nOperator output-location override for this test: use fodo/input/ inside '
                 'your workspace instead of the directory of the original prompt. Preserve all '
                 'physics parameters. Consult the existing skill and relevant local references. '
                 'Generate inputs only; do not validate or simulate. Report limitations honestly.')
        max_calls = 24
    (workspace / 'task.md').write_text(task)
    print(f'Workspace: {workspace}', flush=True)
    started = time.monotonic()
    report = {'mode': args.mode, 'workspace': str(workspace), 'success': False}
    try:
        result = asyncio.run(run_task(task, workspace, max_calls, trace='trace.jsonl'))
        (workspace / 'response.txt').write_text(result.response)
        assert 'list_skills' in result.tool_calls, 'Model did not invoke discovery'
        catalogs = [item['response'] for item in result.tool_results if item['name'] == 'list_skills']
        assert any(any(s['name'] == 'lattice-generator' for s in c.get('skills', [])) for c in catalogs), \
            'Discovery did not return lattice-generator'
        if args.mode == 'fodo':
            assert any(item['name'] == 'load_skill' and
                       item['response'].get('skill') == 'lattice-generator' and
                       item['response'].get('content') for item in result.tool_results), \
                'Model did not load lattice-generator instructions'
            assert any(item['name'] == 'read_skill_document' and
                       item['response'].get('skill') == 'lattice-generator' and
                       item['response'].get('document', '').startswith('references/') and
                       item['response'].get('content') for item in result.tool_results), \
                'Model did not retrieve reference content'
            generated = [p for p in workspace.rglob('*.in') if p.stat().st_size]
            report['generated_inputs'] = [str(p.relative_to(workspace)) for p in generated]
            assert generated, 'No nonempty .in file generated'
            # This is a workflow smoke test, not OPALX syntax or physics validation.
        report['success'] = True
    except (Exception, KeyboardInterrupt) as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        trace = workspace / 'trace.jsonl'
        records = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        report['model'] = next((r['model'] for r in reversed(records)
                                if r['event'] == 'start'), None)
        report['tool_calls'] = [r['name'] for r in records if r['event'] == 'tool_call']
        report['model_usage'] = [{k: v for k, v in r.items() if k != 'event'}
                                 for r in records if r['event'] == 'model_usage']
        report['documentation_accesses'] = [
            {key: r['response'].get(key) for key in
             ('skill', 'document', 'start_line', 'next_line', 'total_lines')}
            for r in records if r['event'] == 'tool_result' and r['name'] in
            {'load_skill', 'read_skill_document'} and 'error' not in r['response']]
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        (workspace / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
