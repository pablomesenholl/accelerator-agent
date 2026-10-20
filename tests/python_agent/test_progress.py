"""Offline ADK runs verifying readable progress without calling Ollama."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python-agent'))
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from agent import _Progress, main, run_task


class OfflineModel(BaseLlm):
    model: str = 'offline-progress-test'
    fail: bool = False

    async def generate_content_async(self, llm_request, stream=False):
        if self.fail:
            raise RuntimeError('Offline model failure')
        tool_returned = any(part.function_response for content in llm_request.contents
                            for part in content.parts or [])
        part = (types.Part(text='Done') if tool_returned else types.Part(
            function_call=types.FunctionCall(name='list_skills', args={})))
        yield LlmResponse(content=types.Content(role='model', parts=[part]))


class ProgressTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_adk_callbacks_tool_progress_and_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch('agent.create_model', return_value=OfflineModel()), redirect_stderr(output):
                result = await run_task('List available skills', Path(directory), trace='trace.jsonl')
            text = output.getvalue()
            self.assertIn('Model request 1: waiting', text)
            self.assertIn('Model response 1 received', text)
            self.assertIn('Calling list_skills()', text)
            self.assertIn('OK list_skills', text)
            self.assertIn('Model request 2: waiting', text)
            self.assertIn('Agent finished.', text)
            self.assertEqual(result.response, 'Done')
            self.assertEqual(result.tool_calls, ['list_skills'])
            events = [json.loads(line) for line in (Path(directory)/'trace.jsonl').read_text().splitlines()]
            self.assertEqual([event['event'] for event in events],
                             ['start', 'tool_call', 'tool_result', 'final'])
            self.assertFalse(any(task.get_coro().__qualname__ == '_Progress.heartbeat'
                                 for task in asyncio.all_tasks()))

    async def test_quiet_preserves_result_without_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch('agent.create_model', return_value=OfflineModel()), redirect_stderr(output):
                result = await run_task('List skills', Path(directory), progress=False)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(result.response, 'Done')

    async def test_error_is_visible_and_heartbeat_is_cleaned_up(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch('agent.create_model', return_value=OfflineModel(fail=True)), redirect_stderr(output):
                with self.assertRaisesRegex(RuntimeError, 'Offline model failure'):
                    await run_task('Fail', Path(directory))
            self.assertIn('Agent stopped: Offline model failure', output.getvalue())
            self.assertFalse(any(task.get_coro().__qualname__ == '_Progress.heartbeat'
                                 for task in asyncio.all_tasks()))

    async def test_waiting_heartbeat_uses_elapsed_time(self):
        output = io.StringIO()
        display = _Progress(True)
        waits = 0

        async def simulated_sleep(seconds):
            nonlocal waits
            self.assertEqual(seconds, 30)
            waits += 1
            if waits == 2:
                raise asyncio.CancelledError

        with redirect_stderr(output), patch('agent.time.monotonic', return_value=100):
            display.before_model(None, None)
        with redirect_stderr(output), patch('agent.time.monotonic', return_value=130), \
                patch('agent.asyncio.sleep', side_effect=simulated_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await display.heartbeat()
        self.assertIn('Still waiting for model response 1 (30s)', output.getvalue())

    async def test_summaries_include_paths_ranges_and_errors_without_contents(self):
        output = io.StringIO()
        display = _Progress(True)
        with redirect_stderr(output):
            display.record('tool_call', {'name': 'write_file', 'args': {
                'path': 'fodo/input.in', 'content': 'PRIVATE_FILE_CONTENT'}})
            display.record('tool_result', {'name': 'read_skill_document', 'response': {
                'skill': 'example', 'document': 'references/guide.md',
                'start_line': 40, 'content': 'PRIVATE_DOC_CONTENT\nsecond line', 'next_line': 42}})
            display.record('tool_result', {'name': 'write_file', 'response': {'written': 'fodo/input.in'}})
            display.record('tool_result', {'name': 'read_file', 'response': {'error': 'Not found'}})
        text = output.getvalue()
        self.assertIn('path=fodo/input.in', text)
        self.assertIn('lines 40-41', text)
        self.assertIn('next_line=42', text)
        self.assertIn('written=fodo/input.in', text)
        self.assertIn('FAILED read_file: Not found', text)
        self.assertNotIn('PRIVATE_FILE_CONTENT', text)
        self.assertNotIn('PRIVATE_DOC_CONTENT', text)


class ProgressCliTest(unittest.TestCase):
    def test_quiet_cli_keeps_final_response_on_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            output, errors = io.StringIO(), io.StringIO()
            with patch('agent.create_model', return_value=OfflineModel()), \
                    patch.object(sys, 'argv', ['agent.py', 'List skills', '--workspace', directory, '--quiet']), \
                    redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main(), 0)
            self.assertEqual(output.getvalue(), 'Done\n')
            self.assertEqual(errors.getvalue(), '')


if __name__ == '__main__':
    unittest.main()
