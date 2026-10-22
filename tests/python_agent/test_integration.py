"""Offline CLI integration through real LiteLLM/ADK; provider and Magnus are fakes.

Synthetic input text and synthetic approvals are wiring fixtures, never physics
validation. Subprocess checks and the suite runner impose explicit time bounds.
"""
from contextlib import chdir, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python-agent'))
from agent import main
from google.adk.models.lite_llm import LiteLLMClient
from litellm import ModelResponse
from tools.magnus_tools import MagnusTools
from test_magnus import FakeBackend

FIXTURE_TEXT = 'Offline integration fixture; not executable OPALX input.\n'
DOCUMENT = 'references/opalx-input-reference.md'
GENERATION = [
    ('list_skills', {}),
    ('load_skill', {'skill': 'lattice-generator'}),
    ('read_skill_document', {'skill': 'lattice-generator', 'document': DOCUMENT,
                             'start_line': 1, 'line_count': 8}),
    ('write_file', {'path': 'input/synthetic.in', 'content': FIXTURE_TEXT}),
    ('read_file', {'path': 'input/synthetic.in'}),
]


def environment(**overrides):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('ACCELERATOR_AGENT_')
           and key not in {'OLLAMA_API_BASE', 'RUN_OLLAMA_SMOKE'}}
    return {**env, 'LITELLM_LOCAL_MODEL_COST_MAP': 'True', **overrides}


def records(root):
    return [json.loads(path.read_text()) for path in (root / '.agent-runs').glob('*.json')]


class ScriptedProvider:
    """Return native provider tool calls after inspecting real converted history."""
    def __init__(self, case, sequence, model, magnus=False, allow_errors=False):
        self.case, self.sequence, self.model = case, sequence, model
        self.magnus, self.allow_errors = magnus, allow_errors
        self.requests = []

    async def complete(self, **kwargs):
        self.requests.append(kwargs)
        self.case.assertEqual(kwargs['model'], self.model)
        names = {tool['function']['name'] for tool in kwargs['tools']}
        self.case.assertEqual('submit_opalx_simulation' in names, self.magnus)
        replies = [json.loads(m['content']) for m in kwargs['messages'] if m['role'] == 'tool']
        if not self.allow_errors:
            for reply in replies:
                self.case.assertNotIn('error', reply)
        if replies and self.sequence[0][0] == 'list_skills':
            self.case.assertIn('lattice-generator', [s['name'] for s in replies[0]['skills']])
            if len(replies) >= 2:
                self.case.assertTrue(replies[1]['content'])
                self.case.assertIn(DOCUMENT, replies[1]['documents'])
            if len(replies) >= 3:
                self.case.assertTrue(replies[2]['content'])
        index = len(replies)
        if index < len(self.sequence):
            name, args = self.sequence[index]
            self.case.assertIn(name, names)
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': f'offline-{index}', 'type': 'function',
                'function': {'name': name, 'arguments': json.dumps(args)}}]}
            finish = 'tool_calls'
        else:
            message = {'role': 'assistant', 'content': 'OFFLINE_COMPLETE'}
            finish = 'stop'
        return ModelResponse(model=self.model, choices=[{'index': 0, 'finish_reason': finish,
                                                        'message': message}],
                             usage={'prompt_tokens': 100, 'completion_tokens': 10, 'total_tokens': 110})


class CliIntegrationTest(unittest.TestCase):
    def invoke(self, cwd, env, args, provider):
        out, err = io.StringIO(), io.StringIO()
        with chdir(cwd), patch.dict(os.environ, env, clear=True), \
                patch.object(sys, 'argv', ['agent.py', *args]), \
                patch.object(LiteLLMClient, 'acompletion', new=AsyncMock(side_effect=provider.complete)), \
                patch('socket.socket.connect', side_effect=AssertionError('Unexpected network connection')), \
                redirect_stdout(out), redirect_stderr(err):
            code = main()
        return code, out.getvalue(), err.getvalue()

    def test_real_adapter_skill_file_task_and_records_for_model_switching(self):
        for model in ('ollama_chat/qwen3.5:2b', 'ollama_chat/qwen2.5-coder:3b',
                      'openai/offline-integration-fixture'):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as directory:
                cwd = Path(directory)
                (cwd / 'request.md').write_text('Exercise the offline fixture workflow; no physics claims.')
                env = environment(ACCELERATOR_AGENT_MODEL=model,
                                  ACCELERATOR_AGENT_API_BASE='http://provider.invalid/v1',
                                  ACCELERATOR_AGENT_API_KEY='integration-private-key')
                provider = ScriptedProvider(self, GENERATION, model)
                with patch('tools.magnus_tools.MagnusBackend', side_effect=AssertionError('Magnus disabled')):
                    code, out, err = self.invoke(cwd, env, [
                        '--task-file', 'request.md', '--workspace', 'workspace',
                        '--trace', 'trace.jsonl', '--quiet'], provider)
                self.assertEqual(code, 0, err)
                self.assertEqual(out, 'OFFLINE_COMPLETE\n')
                self.assertEqual(err, '')
                root = cwd / 'workspace'
                self.assertEqual((root / 'input/synthetic.in').read_text(), FIXTURE_TEXT)
                summary, = records(root)
                self.assertEqual(summary['status'], 'completed')
                self.assertEqual(summary['configuration']['model'], model)
                self.assertEqual(summary['model_requests'], len(GENERATION) + 1)
                self.assertEqual(len(summary['model_usage']), len(provider.requests))
                self.assertEqual(summary['tool_error_count'], 0)
                trace = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
                self.assertEqual([e['name'] for e in trace if e['event'] == 'tool_call'],
                                 [name for name, _ in GENERATION])
                self.assertTrue(all(e['run_id'] == summary['run_id'] for e in trace))
                for request in provider.requests:
                    self.assertEqual(request['api_base'], 'http://provider.invalid/v1')
                    self.assertEqual(request['api_key'], 'integration-private-key')
                    self.assertEqual(request['num_retries'], 0)
                    if model.startswith('ollama_chat/'):
                        self.assertEqual(request['num_ctx'], 16384)
                        self.assertEqual(request['reasoning_effort'], 'none')
                    else:
                        self.assertNotIn('num_ctx', request)
                        self.assertNotIn('reasoning_effort', request)
                self.assertNotIn('integration-private-key', json.dumps(summary))

    def test_reviewed_submission_and_reconnect_across_cli_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            root = cwd / 'workspace'
            (root / 'input').mkdir(parents=True)
            (root / 'input/synthetic.in').write_text(FIXTURE_TEXT)
            backend = FakeBackend()
            inspector = MagnusTools(root, backend=backend)
            # Synthetic operator evidence only; this does not validate OPALX.
            approval = {**inspector._input('input', 'synthetic.in'), 'status': 'PASS', 'checks': {
                'structure': 'PASS', 'specification': 'PASS', 'physics': 'PASS',
                'native_parser': 'SKIPPED_NOT_AVAILABLE'}}
            (root / 'review.json').write_text(json.dumps(approval))
            backend.result['input_file'] = 'synthetic.in'
            model = 'ollama_chat/qwen3.5:2b'
            env = environment(ACCELERATOR_AGENT_MODEL=model)
            submit = [('inspect_opalx_backend', {}), ('submit_opalx_simulation', {
                'simulation': 'input', 'input_file': 'synthetic.in'})]
            resume = [('get_opalx_job_status', {'job_id': 'job-123'}),
                      ('read_opalx_job_logs', {'job_id': 'job-123'}),
                      ('retrieve_opalx_outputs', {'job_id': 'job-123'})]
            with patch('tools.magnus_tools.MagnusBackend', return_value=backend):
                for sequence, flags in [(submit, ['--allow-simulation', '--validation-report', 'review.json']),
                                        (resume, [])]:
                    provider = ScriptedProvider(self, sequence, model, magnus=True)
                    code, out, err = self.invoke(cwd, env, [
                        'Exercise the fake backend only.', '--workspace', 'workspace',
                        '--enable-magnus', '--trace', 'trace.jsonl', '--quiet', *flags], provider)
                    self.assertEqual(code, 0, err)
                    self.assertEqual(out, 'OFFLINE_COMPLETE\n')
            summaries = records(root)
            self.assertEqual(len(summaries), 2)
            self.assertEqual(len({r['session_id'] for r in summaries}), 2)
            self.assertTrue(all(r['status'] == 'completed' for r in summaries))
            self.assertEqual(sum(c[0] == 'launch_blueprint' for c in backend.calls), 1)
            self.assertEqual(backend.downloads, 1)
            self.assertEqual((root / 'input/synthetic.in').read_text(), FIXTURE_TEXT)
            self.assertEqual(len(list(root.glob('magnus-results/*/result.stat'))), 1)

    def test_missing_review_blocks_submission_without_backend_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            (cwd / 'workspace/input').mkdir(parents=True)
            (cwd / 'workspace/input/synthetic.in').write_text(FIXTURE_TEXT)
            backend = FakeBackend()
            model = 'ollama_chat/qwen3.5:2b'
            provider = ScriptedProvider(self, [('submit_opalx_simulation', {
                'simulation': 'input', 'input_file': 'synthetic.in'})], model,
                magnus=True, allow_errors=True)
            with patch('tools.magnus_tools.MagnusBackend', return_value=backend):
                code, _, err = self.invoke(cwd, environment(ACCELERATOR_AGENT_MODEL=model), [
                    'Attempt fixture submission.', '--workspace', 'workspace',
                    '--enable-magnus', '--quiet'], provider)
            self.assertEqual(code, 0, err)  # Lifecycle completed; the tool refused submission.
            summary, = records(cwd / 'workspace')
            self.assertEqual(summary['tool_error_count'], 1)
            self.assertEqual(backend.calls, [])

    def test_provider_failure_through_real_adapter_has_cli_record_and_redaction(self):
        class FailingProvider:
            async def complete(self, **kwargs):
                raise ConnectionError('integration-private-key at https://provider.invalid/v1')

        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            code, out, err = self.invoke(cwd, environment(
                ACCELERATOR_AGENT_API_KEY='integration-private-key'), [
                'Fixture task', '--workspace', 'workspace', '--trace', 'trace.jsonl', '--quiet'],
                FailingProvider())
            self.assertEqual(code, 1)
            self.assertEqual(out, '')
            summary, = records(cwd / 'workspace')
            self.assertEqual(summary['status'], 'failed')
            self.assertEqual(summary['error']['category'], 'connection')
            self.assertIn(summary['run_id'], err)
            self.assertNotIn('integration-private-key', err)
            self.assertNotIn('provider.invalid', err)


class CliProcessTest(unittest.TestCase):
    def test_entrypoint_from_other_directory_without_model_or_backend(self):
        cases = [(['--help'], {}, 0),
                 (['--show-config'], {'ACCELERATOR_AGENT_MODEL': 'openai/offline-fixture'}, 0),
                 (['--show-config'], {'ACCELERATOR_AGENT_TIMEOUT': 'bad'}, 2),
                 (['--task-file', 'missing.md', '--workspace', 'workspace', '--quiet'], {}, 1)]
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            for args, overrides, expected in cases:
                with self.subTest(args=args):
                    result = subprocess.run([sys.executable, str(ROOT / 'python-agent/agent.py'), *args],
                                            cwd=cwd, env=environment(**overrides), capture_output=True,
                                            text=True, timeout=30)
                    self.assertEqual(result.returncode, expected, result.stderr)
                    if args == ['--show-config'] and expected == 0:
                        config = json.loads(result.stdout)
                        self.assertEqual(config['model'], 'openai/offline-fixture')
                        self.assertFalse(config['api_base_configured'])
                    if expected in (0, 2):
                        self.assertFalse((cwd / 'workspace').exists())
            summary, = records(cwd / 'workspace')
            self.assertEqual(summary['error']['stage'], 'task_input')


if __name__ == '__main__':
    unittest.main()
