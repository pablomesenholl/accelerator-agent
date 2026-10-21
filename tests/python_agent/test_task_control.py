"""Offline regression coverage for duplicate calls and token diagnostics."""
import io
import json
from contextlib import redirect_stderr
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python-agent'))
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.function_tool import FunctionTool
from google.genai import types
from agent import RepeatedToolCallError, _ToolLoopGuard, _execution_handoff, run_task
from types import SimpleNamespace


def read_page(path: str, start_line: int = 1):
    return {'path': path}


class LoopGuardTest(unittest.TestCase):
    def test_equivalent_default_arguments_stop_before_third_execution(self):
        guard = _ToolLoopGuard()
        tool = FunctionTool(read_page)
        self.assertIsNone(guard.before_tool(tool, {'path': 'guide.md'}, None))
        self.assertIsNone(guard.before_tool(tool, {'start_line': 1, 'path': 'guide.md'}, None))
        with self.assertRaisesRegex(RepeatedToolCallError, '3 consecutive identical'):
            guard.before_tool(tool, {'path': 'guide.md'}, None)

    def test_different_arguments_reset_the_consecutive_count(self):
        guard = _ToolLoopGuard()
        tool = FunctionTool(read_page)
        for start in [1, 1, 2, 2, 1, 1]:
            guard.before_tool(tool, {'path': 'guide.md', 'start_line': start}, None)

    def test_short_cycles_stop_before_third_repetition_completes(self):
        for period in (2, 3):
            with self.subTest(period=period):
                guard = _ToolLoopGuard()
                tools = [SimpleNamespace(name=f'inspect_{i}') for i in range(period)]
                for index in range(period * 3 - 1):
                    guard.before_tool(tools[index % period], {}, None)
                with self.assertRaisesRegex(RepeatedToolCallError, f'{period}-call pattern'):
                    guard.before_tool(tools[-1], {}, None)

    def test_polling_resets_cycle_history_but_submission_is_guarded(self):
        guard = _ToolLoopGuard()
        for _ in range(5):
            guard.before_tool(SimpleNamespace(name='read_file'), {'path': 'report'}, None)
            guard.before_tool(SimpleNamespace(name='get_opalx_job_status'), {}, None)
            guard.before_tool(SimpleNamespace(name='read_opalx_job_logs'), {}, None)
        tool = SimpleNamespace(name='submit_opalx_simulation')
        guard.before_tool(tool, {}, None)
        guard.before_tool(tool, {}, None)
        with self.assertRaises(RepeatedToolCallError):
            guard.before_tool(tool, {}, None)

    def test_changing_ranges_do_not_form_a_cycle(self):
        guard = _ToolLoopGuard()
        for start in range(1, 15):
            guard.before_tool(FunctionTool(read_page), {'path': 'guide', 'start_line': start}, None)
            guard.before_tool(SimpleNamespace(name='list_files'), {}, None)


class ExecutionHandoffTest(unittest.TestCase):
    def test_operator_configuration_is_explicit_including_disabled_or_failed(self):
        for enabled, status in [(True, 'PASS'), (False, 'PASS'), (True, 'FAIL')]:
            text = _execution_handoff(SimpleNamespace(allow_simulation=enabled, approval={
                'status': status, 'simulation': 'input', 'input_file': 'test{1}.in',
                'input_digest': 'digest'}))
            config = json.loads(text.splitlines()[3])
            self.assertEqual(config['submission_enabled'], enabled)
            self.assertEqual(config['report_status'], status)
            self.assertEqual(config['input_file'], 'test{1}.in')
            self.assertIn('does not validate inputs or bypass that gate', text)


class DiagnosticModel(BaseLlm):
    model: str = 'offline-diagnostics'
    repeat: bool = False
    emit_usage: bool = True

    async def generate_content_async(self, llm_request, stream=False):
        responded = any(part.function_response for content in llm_request.contents
                        for part in content.parts or [])
        if self.repeat:
            part = types.Part(function_call=types.FunctionCall(
                name='load_skill', args={'skill': 'lattice-generator'}))
        elif not responded:
            part = types.Part(function_call=types.FunctionCall(name='list_skills', args={}))
        else:
            part = types.Part(text='Done')
        usage = types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=10, total_token_count=110,
            cached_content_token_count=0) if self.emit_usage else None
        yield LlmResponse(content=types.Content(role='model', parts=[part]), usage_metadata=usage)


class TaskDiagnosticsTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_adk_loop_stops_and_trace_preserves_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('agent.create_model', return_value=DiagnosticModel(repeat=True)):
                with self.assertRaises(RepeatedToolCallError):
                    await run_task('Consult a skill', root, trace='trace.jsonl', progress=False)
            events = [json.loads(line) for line in (root/'trace.jsonl').read_text().splitlines()]
            results = [r['response'] for r in events if r['event'] == 'tool_result']
            self.assertEqual(len(results), 2)
            self.assertIn('content', results[0])
            self.assertNotIn('content', results[1])
            self.assertTrue(results[1]['already_loaded'])
            self.assertEqual(events[-1]['type'], 'RepeatedToolCallError')
            self.assertEqual(len([r for r in events if r['event'] == 'model_usage']), 3)

    async def test_usage_is_recorded_even_in_quiet_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with patch('agent.create_model', return_value=DiagnosticModel()), redirect_stderr(output):
                result = await run_task('List skills', root, trace='trace.jsonl', progress=False)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual([u['request'] for u in result.model_usage], [1, 2])
            self.assertTrue(result.model_usage[0]['available'])
            self.assertEqual(result.model_usage[0]['prompt_tokens'], 100)
            self.assertEqual(result.model_usage[0]['output_tokens'], 10)
            self.assertEqual(result.model_usage[0]['total_tokens'], 110)
            self.assertEqual(result.model_usage[0]['cached_tokens'], 0)
            self.assertIsNone(result.model_usage[0]['reasoning_tokens'])

    async def test_missing_usage_is_explicit_and_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch('agent.create_model', return_value=DiagnosticModel(emit_usage=False)), \
                    redirect_stderr(output):
                result = await run_task('List skills', Path(directory))
            self.assertIn('usage unavailable', output.getvalue())
            self.assertFalse(result.model_usage[0]['available'])
            self.assertIsNone(result.model_usage[0]['prompt_tokens'])


if __name__ == '__main__':
    unittest.main()
