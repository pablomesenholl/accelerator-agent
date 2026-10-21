"""Offline coverage for empty fence remnants left by ADK's inline-tool parser."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python-agent'))
from agent import _remove_empty_tool_fences, run_task
from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import (
    _get_completion_inputs, _model_response_to_generate_content_response)
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from litellm import ModelResponse


def parsed_call():
    return _model_response_to_generate_content_response(ModelResponse(
        model='diagnostic', choices=[{'finish_reason': 'stop', 'message': {
            'role': 'assistant', 'content': '```json\n' + json.dumps({
                'name': 'list_files', 'arguments': {}}) + '\n```'}}]))


class FenceModel(BaseLlm):
    model: str = 'offline-fences'

    async def generate_content_async(self, llm_request, stream=False):
        if any(p.function_response for c in llm_request.contents for p in c.parts or []):
            for content in llm_request.contents:
                if content.role == 'model':
                    assert not any(p.text == '```json\n\n```' for p in content.parts or [])
            yield LlmResponse(content=types.Content(role='model', parts=[types.Part(text='Done')]))
        else:
            yield parsed_call()


class ToolFenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_actual_conversion_history_preserves_call_without_fence(self):
        original = parsed_call()
        cleaned = _remove_empty_tool_fences(original)
        self.assertEqual(original.content.parts[0].text, '```json\n\n```')
        call = cleaned.content.parts[0].function_call
        self.assertEqual(call.name, 'list_files')
        reply = types.Content(role='user', parts=[types.Part(function_response=
            types.FunctionResponse(id=call.id, name=call.name, response={'entries': []}))])
        messages, *_ = await _get_completion_inputs(LlmRequest(
            contents=[cleaned.content, reply], config=types.GenerateContentConfig()),
            'ollama_chat/qwen2.5-coder:3b')
        self.assertFalse(messages[0].get('content'))
        self.assertEqual(messages[0]['tool_calls'][0]['function']['name'], 'list_files')

    async def test_callback_cleans_real_adk_session_history(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('agent.create_model', return_value=FenceModel()):
                result = await run_task('List files', Path(directory), progress=False)
        self.assertEqual(result.tool_calls, ['list_files'])
        self.assertEqual(result.response, 'Done')

    def test_final_responses_meaningful_text_and_thoughts_are_unchanged(self):
        for text, thought, with_call in [
            ('```json\n\n```', False, False), ('Explanation\n```json\n\n```', False, True),
            ('```json\n{}\n```', False, True), ('```json\n\n```', True, True)]:
            parts = [types.Part(text=text, thought=thought)]
            if with_call:
                parts.append(types.Part(function_call=types.FunctionCall(name='list_files', args={})))
            response = LlmResponse(content=types.Content(role='model', parts=parts))
            self.assertIsNone(_remove_empty_tool_fences(response))

    def test_partial_response_is_not_modified(self):
        response = parsed_call()
        response.partial = True
        self.assertIsNone(_remove_empty_tool_fences(response))
