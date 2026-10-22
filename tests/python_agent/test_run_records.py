"""Scripted ADK lifecycle checks; no model or Magnus requests."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python-agent'))
from agent import main, run_task
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from run_records import RUN_DIRECTORY, RunRecord


class RecordModel(BaseLlm):
    model: str = 'offline-records'
    mode: str = 'success'
    checkpoint: str | None = None

    async def generate_content_async(self, llm_request, stream=False):
        if self.checkpoint:
            current = summaries(Path(self.checkpoint))[0]
            assert current['status'] == 'running'
            assert current['stage'] == 'execution'
            assert current['session_id']
            assert current['model_requests'] > 0
        if self.mode == 'timeout':
            raise TimeoutError('private-key at https://private-host/v1?token=secret')
        if self.mode == 'cancel':
            raise asyncio.CancelledError('cancel fixture')
        count = sum(bool(p.function_response) for c in llm_request.contents for p in c.parts or [])
        if self.mode == 'empty':
            part = types.Part(text='')
        elif count and self.mode != 'limit':
            part = types.Part(text='PRIVATE_FINAL')
        else:
            path = ('../blocked' if self.mode == 'tool_error' else
                    f'{RUN_DIRECTORY}/attempt.json' if self.mode == 'protected' else f'note-{count}.txt')
            part = types.Part(function_call=types.FunctionCall(
                name='write_file', args={'path': path, 'content': 'PRIVATE_CONTENT'}))
        yield LlmResponse(content=types.Content(role='model', parts=[part]),
                          usage_metadata=types.GenerateContentResponseUsageMetadata(
                              prompt_token_count=20, candidates_token_count=5, total_token_count=25))


def summaries(root):
    return [json.loads(path.read_text()) for path in sorted((root / RUN_DIRECTORY).glob('*.json'))]


class RunRecordsTest(unittest.IsolatedAsyncioTestCase):
    async def test_success_unique_records_and_correlated_append_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('agent.create_model', side_effect=lambda config: RecordModel(checkpoint=str(root))):
                first = await run_task('PRIVATE_TASK', root, trace='trace.jsonl', progress=False)
            with patch('agent.create_model', return_value=RecordModel()):
                second = await run_task('Second task', root, trace='trace.jsonl', progress=False)
            self.assertNotEqual(first.run_id, second.run_id)
            self.assertTrue(Path(first.record_path).is_file())
            for summary in summaries(root):
                self.assertEqual(summary['status'], 'completed')
                self.assertEqual(summary['model_requests'], 2)
                self.assertEqual(summary['tool_calls'], 1)
                self.assertEqual(summary['tool_error_count'], 0)
                self.assertEqual(len(summary['model_usage']), 2)
                self.assertTrue(summary['session_id'])
                self.assertIsNone(summary['error'])
                self.assertGreaterEqual(summary['elapsed_seconds'], 0)
                self.assertLessEqual(summary['started_at'], summary['finished_at'])
                self.assertNotIn('PRIVATE_', json.dumps(summary))
            events = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
            self.assertEqual({e['run_id'] for e in events}, {first.run_id, second.run_id})
            self.assertTrue(all(e['timestamp'] and e['elapsed_seconds'] >= 0 for e in events))
            self.assertEqual(sum(e['event'] == 'final' for e in events), 2)

    async def test_configuration_task_input_and_startup_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {'ACCELERATOR_AGENT_TIMEOUT': 'invalid'}):
                with self.assertRaises(ValueError) as error:
                    await run_task('Task', root, progress=False)
            self.assertTrue(Path(error.exception.run_record_path).exists())
            self.assertEqual(summaries(root)[0]['error']['stage'], 'configuration')
            with self.assertRaises(FileNotFoundError):
                await run_task(None, root, task_file=root / 'missing.md', progress=False)
            with patch('agent.create_model', side_effect=RuntimeError('constructor fixture')):
                with self.assertRaisesRegex(RuntimeError, 'constructor fixture'):
                    await run_task('Task', root, progress=False)
            self.assertEqual({r['error']['stage'] for r in summaries(root)},
                             {'configuration', 'task_input', 'startup'})
            self.assertTrue(all(r['status'] == 'failed' for r in summaries(root)))

    async def test_timeout_is_redacted_and_original_exception_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('agent.create_model', return_value=RecordModel(mode='timeout')), \
                    patch.dict(os.environ, {'ACCELERATOR_AGENT_API_KEY': 'private-key'}), \
                    redirect_stderr(io.StringIO()) as output:
                with self.assertRaises(TimeoutError) as error:
                    await run_task('Task', root, trace='trace.jsonl')
            self.assertIn('private-key', str(error.exception))
            summary = summaries(root)[0]
            self.assertEqual(summary['error']['category'], 'timeout')
            for text in (json.dumps(summary), (root / 'trace.jsonl').read_text(), output.getvalue()):
                self.assertNotIn('private-key', text)
                self.assertNotIn('private-host', text)
            self.assertFalse(any(t.get_coro().__qualname__ == '_Progress.heartbeat'
                                 for t in asyncio.all_tasks()))

    async def test_tool_errors_and_record_write_protection(self):
        for mode in ('tool_error', 'protected'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch('agent.create_model', return_value=RecordModel(mode=mode)):
                    result = await run_task('Task', root, progress=False)
                self.assertIn('error', result.tool_results[0]['response'])
                summary = summaries(root)[0]
                self.assertEqual(summary['status'], 'completed')
                self.assertEqual(summary['tool_error_count'], 1)
                self.assertFalse((root / RUN_DIRECTORY / 'attempt.json').exists())

    async def test_cancellation_empty_response_and_request_limit(self):
        for mode, category in [('cancel', 'cancelled'), ('empty', 'execution'), ('limit', 'request_limit')]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch('agent.create_model', return_value=RecordModel(mode=mode)):
                    with self.assertRaises(BaseException):
                        await run_task('Task', root, max_calls=1, progress=False)
                summary = summaries(root)[0]
                self.assertEqual(summary['error']['category'], category)
                self.assertEqual(summary['status'], 'cancelled' if mode == 'cancel' else 'failed')

    async def test_cleanup_errors_preserve_primary_and_prevent_false_completion(self):
        for mode in ('success', 'timeout'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch('agent.create_model', return_value=RecordModel(mode=mode)), \
                        patch('agent.InMemoryRunner.close', new=AsyncMock(side_effect=RuntimeError('close fixture'))):
                    expected = TimeoutError if mode == 'timeout' else RuntimeError
                    with self.assertRaises(expected):
                        await run_task('Task', root, trace='trace.jsonl', progress=False)
                summary = summaries(root)[0]
                self.assertEqual(summary['status'], 'failed')
                self.assertEqual(summary['cleanup_errors'][0]['stage'], 'cleanup')
                self.assertEqual(summary['error']['category'], 'timeout' if mode == 'timeout' else 'cleanup')
                self.assertNotIn('"event": "final"', (root / 'trace.jsonl').read_text())

    async def test_recording_failure_does_not_replace_original_exception(self):
        original = RunRecord.save

        def fail_during_error(record):
            if record.data['status'] == 'failed':
                raise OSError('record write fixture')
            return original(record)

        with tempfile.TemporaryDirectory() as directory:
            with patch('agent.create_model', return_value=RecordModel(mode='timeout')), \
                    patch.object(RunRecord, 'save', fail_during_error):
                with self.assertRaises(TimeoutError) as error:
                    await run_task('Task', Path(directory), progress=False)
            self.assertTrue(any('Could not finalize' in note for note in error.exception.__notes__))

    async def test_trace_cannot_overwrite_records_or_escape_workspace(self):
        for trace in ('../trace.jsonl', f'{RUN_DIRECTORY}/overwrite.jsonl', '.magnus-jobs/trace.jsonl'):
            with self.subTest(trace=trace), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(ValueError):
                    await run_task('Task', root, trace=trace, progress=False)
                self.assertEqual(summaries(root)[0]['status'], 'failed')

    async def test_session_creation_failure_closes_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('agent.create_model', return_value=RecordModel()), \
                    patch('google.adk.sessions.in_memory_session_service.InMemorySessionService.create_session',
                          new=AsyncMock(side_effect=RuntimeError('session fixture'))), \
                    patch('agent.InMemoryRunner.close', new=AsyncMock()) as close:
                with self.assertRaisesRegex(RuntimeError, 'session fixture'):
                    await run_task('Task', root, progress=False)
            close.assert_awaited_once()
            summary = summaries(root)[0]
            self.assertEqual(summary['error']['stage'], 'session')
            self.assertEqual(summary['model_requests'], 0)

    async def test_failure_to_write_completion_is_not_reported_as_success(self):
        original = RunRecord.save

        def fail_completion(record):
            if record.data['status'] == 'completed':
                raise OSError('completion write fixture')
            return original(record)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('agent.create_model', return_value=RecordModel()), \
                    patch.object(RunRecord, 'save', fail_completion):
                with self.assertRaisesRegex(OSError, 'completion write fixture'):
                    await run_task('Task', root, trace='trace.jsonl', progress=False)
            self.assertEqual(summaries(root)[0]['status'], 'failed')
            self.assertEqual(summaries(root)[0]['error']['category'], 'recording')
            events = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1]['event'], 'error')
            self.assertNotIn('final', [e['event'] for e in events])

    async def test_trace_write_failure_is_reported_without_losing_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'trace-directory').mkdir()
            with self.assertRaises(IsADirectoryError) as error:
                await run_task('Task', root, trace='trace-directory', progress=False)
            self.assertTrue(any('Could not append error trace' in note
                                for note in error.exception.__notes__))
            self.assertEqual(summaries(root)[0]['status'], 'failed')

    async def test_symlinked_record_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'workspace'
            outside = Path(directory) / 'outside'
            root.mkdir()
            outside.mkdir()
            (root / RUN_DIRECTORY).symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'Symbolic links'):
                await run_task('Task', root, progress=False)
            self.assertEqual(list(outside.iterdir()), [])


class RunRecordCliTest(unittest.TestCase):
    def test_missing_task_file_is_recorded_and_cli_returns_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            out, err = io.StringIO(), io.StringIO()
            with patch.object(sys, 'argv', ['agent.py', '--task-file', f'{directory}/missing.md',
                                           '--workspace', directory, '--quiet']), \
                    redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(main(), 1)
            self.assertEqual(out.getvalue(), '')
            self.assertIn('task_input/FileNotFoundError', err.getvalue())
            self.assertIn('Run record:', err.getvalue())
            self.assertEqual(summaries(Path(directory))[0]['error']['stage'], 'task_input')

    def test_unusable_workspace_has_diagnostic_without_record(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / 'file'
            workspace.write_text('preserve')
            out, err = io.StringIO(), io.StringIO()
            with patch.object(sys, 'argv', ['agent.py', 'Task', '--workspace', str(workspace)]), \
                    redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(main(), 1)
            self.assertIn('FileExistsError', err.getvalue())
            self.assertIn('Run record unavailable', err.getvalue())
            self.assertEqual(workspace.read_text(), 'preserve')
