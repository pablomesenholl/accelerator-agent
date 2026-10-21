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
from agent import RepeatedToolCallError, _ToolLoopGuard, _SkillHandoff, _execution_handoff, run_task
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


class SkillHandoffTest(unittest.TestCase):
    def test_reference_content_advances_but_search_errors_and_reloads_do_not(self):
        handoff = _SkillHandoff()
        load = SimpleNamespace(name='load_skill')
        read = SimpleNamespace(name='read_skill_document')
        metadata = {'skill': 'example', 'documents': ['SKILL.md', 'references/syntax.md']}
        handoff.after_tool(load, {}, None, metadata)
        for response in ({'error': 'missing'},
                         {'skill': 'example', 'document': 'references/syntax.md', 'matches': []},
                         {'skill': 'example', 'document': 'SKILL.md', 'content': 'instructions'}):
            handoff.after_tool(read, {}, None, response)
            self.assertIn('example', handoff.pending)
        handoff.after_tool(read, {}, None, {
            'skill': 'example', 'document': 'references/syntax.md', 'content': 'syntax'})
        handoff.after_tool(load, {}, None, {**metadata, 'already_loaded': True})
        self.assertEqual(handoff.pending, {})

    def test_no_reference_or_failed_load_does_not_create_handoff(self):
        handoff = _SkillHandoff()
        for response in ({'error': 'missing'}, {'skill': 'plain', 'documents': ['SKILL.md']}):
            handoff.after_tool(SimpleNamespace(name='load_skill'), {}, None, response)
        self.assertEqual(handoff.pending, {})


class ReferenceModel(BaseLlm):
    model: str = 'offline-reference-handoff'

    async def generate_content_async(self, llm_request, stream=False):
        count = sum(bool(p.function_response) for c in llm_request.contents for p in c.parts or [])
        instructions = llm_request.config.system_instruction or ''
        if count == 1:
            assert 'Skill-to-reference handoff' in instructions
            assert 'references/opalx-input-reference.md' in instructions
            part = types.Part(function_call=types.FunctionCall(name='read_skill_document', args={
                'skill': 'lattice-generator', 'document': 'references/opalx-input-reference.md',
                'start_line': 1, 'line_count': 20}))
        elif count == 0:
            assert 'Skill-to-reference handoff' not in instructions
            part = types.Part(function_call=types.FunctionCall(
                name='load_skill', args={'skill': 'lattice-generator'}))
        else:
            assert 'Skill-to-reference handoff' not in instructions
            part = types.Part(text='Done')
        yield LlmResponse(content=types.Content(role='model', parts=[part]))


class GenerationModel(BaseLlm):
    model: str = 'offline-generation-handoff'
    produce_file: bool = True

    async def generate_content_async(self, llm_request, stream=False):
        responses = [p.function_response for c in llm_request.contents for p in c.parts or []
                     if p.function_response]
        count = len(responses)
        continuation = any('only automatic continuation' in (p.text or '')
                           for c in llm_request.contents for p in c.parts or [])
        instructions = llm_request.config.system_instruction or ''
        if count == 0:
            part = types.Part(function_call=types.FunctionCall(
                name='load_skill', args={'skill': 'lattice-generator'}))
        elif count == 1:
            part = types.Part(function_call=types.FunctionCall(name='read_skill_document', args={
                'skill': 'lattice-generator', 'document': 'references/opalx-input-reference.md',
                'line_count': 20}))
        elif count == 2:
            assert 'Reference-to-generation handoff' in instructions
            if continuation and self.produce_file:
                part = types.Part(function_call=types.FunctionCall(name='write_file', args={
                    'path': 'example.in', 'content': 'offline fixture;'}))
            else:
                part = types.Part(text='```json\n\n```')
        else:
            assert 'Reference-to-generation handoff' not in instructions
            part = types.Part(text='Created example.in')
        yield LlmResponse(content=types.Content(role='model', parts=[part]))


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
    async def test_generation_continues_once_using_existing_session_and_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('agent.create_model', return_value=GenerationModel()):
                result = await run_task('Generate input', root, trace='trace.jsonl',
                                        progress=False, require_file_output=True)
            self.assertEqual((root/'example.in').read_text(), 'offline fixture;')
            events = [json.loads(line) for line in (root/'trace.jsonl').read_text().splitlines()]
            self.assertEqual(sum(e['event'] == 'continuation' for e in events), 1)
            self.assertEqual(result.response, 'Created example.in')
            self.assertEqual(result.tool_calls.count('load_skill'), 1)

    async def test_generation_without_writes_stops_after_one_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('agent.create_model', return_value=GenerationModel(produce_file=False)):
                with self.assertRaisesRegex(RuntimeError, 'without a successful nonempty'):
                    await run_task('Generate input', Path(directory), progress=False,
                                   require_file_output=True)

    async def test_generation_does_not_continue_when_request_budget_is_exhausted(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('agent.create_model', return_value=GenerationModel()):
                with self.assertRaisesRegex(RuntimeError, 'without a successful nonempty'):
                    await run_task('Generate input', Path(directory), max_calls=3,
                                   progress=False, require_file_output=True)

    async def test_adk_request_receives_then_clears_reference_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('agent.create_model', return_value=ReferenceModel()):
                result = await run_task('Consult documentation', Path(directory), progress=False)
        self.assertEqual(result.tool_calls, ['load_skill', 'read_skill_document'])
        self.assertEqual(result.response, 'Done')

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
