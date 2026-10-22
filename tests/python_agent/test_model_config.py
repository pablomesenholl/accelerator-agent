"""Configuration checks without provider requests or credentials."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python-agent'))
from model_config import ModelConfig, create_model
from agent import main


class ModelConfigTest(unittest.TestCase):
    def test_defaults_and_both_local_models(self):
        for model in ('ollama_chat/qwen3.5:2b', 'ollama_chat/qwen2.5-coder:3b', 'ollama/qwen3.5:2b'):
            config = ModelConfig.from_env({'ACCELERATOR_AGENT_MODEL': model})
            self.assertEqual(config.adapter_kwargs(), dict(
                model=model, api_base='http://localhost:11434', temperature=0,
                timeout=300, max_tokens=2048, num_ctx=16384,
                num_retries=0, reasoning_effort='none'))
        self.assertEqual(ModelConfig.from_env({}).model, 'ollama_chat/qwen3.5:2b')

    def test_overrides_and_endpoint_precedence(self):
        config = ModelConfig.from_env(dict(
            ACCELERATOR_AGENT_MODEL='ollama_chat/qwen2.5-coder:3b',
            OLLAMA_API_BASE='http://legacy:11434',
            ACCELERATOR_AGENT_API_BASE='http://custom:11434',
            ACCELERATOR_AGENT_TIMEOUT='12.5', ACCELERATOR_AGENT_MAX_TOKENS='256',
            ACCELERATOR_AGENT_CONTEXT='8192', ACCELERATOR_AGENT_REASONING='low'))
        self.assertEqual(config.api_base, 'http://custom:11434')
        self.assertEqual((config.timeout, config.max_tokens, config.context, config.reasoning),
                         (12.5, 256, 8192, 'low'))
        self.assertEqual(ModelConfig.from_env({'OLLAMA_API_BASE': 'http://legacy:11434'}).api_base,
                         'http://legacy:11434')

    def test_other_providers_do_not_inherit_ollama_settings(self):
        env = dict(ACCELERATOR_AGENT_MODEL='anthropic/claude-example', OLLAMA_API_BASE='invalid')
        config = ModelConfig.from_env(env)
        for key in ('api_base', 'api_key', 'num_ctx', 'reasoning_effort'):
            self.assertNotIn(key, config.adapter_kwargs())
        config = ModelConfig.from_env({**env, 'ACCELERATOR_AGENT_API_BASE': 'https://example.org/v1',
                                       'ACCELERATOR_AGENT_API_KEY': 'private-key',
                                       'ACCELERATOR_AGENT_REASONING': 'high'})
        self.assertEqual(config.adapter_kwargs()['api_key'], 'private-key')
        self.assertEqual(config.adapter_kwargs()['reasoning_effort'], 'high')
        self.assertNotIn('private-key', repr(config))
        self.assertNotIn('example.org', json.dumps(config.summary()))
        self.assertTrue(config.summary()['api_key_configured'])

    def test_invalid_environment_fails_before_adapter_construction(self):
        cases = {
            'MODEL': ['', ' ', 'ollama_chat/has space', 'ollama_chat/', '/missing-provider'],
            'TIMEOUT': ['0', '-1', 'nan', 'inf', 'bad'],
            'MAX_TOKENS': ['0', '-2', '1.5', 'bad'],
            'CONTEXT': ['0', '-2', '1.5', 'bad'],
            'REASONING': ['', 'yes'],
            'API_KEY': ['', ' '],
            'API_BASE': ['', 'ftp://host', 'http://', 'http://host:bad',
                         'https://user:private-key@host', 'https://host?key=private-key',
                         'https://host/#private-key'],
        }
        for suffix, values in cases.items():
            for value in values:
                with self.subTest(suffix=suffix, value=value), \
                        patch.dict(os.environ, {'ACCELERATOR_AGENT_' + suffix: value}, clear=True), \
                        patch('google.adk.models.lite_llm.LiteLlm') as adapter:
                    with self.assertRaises(ValueError) as error:
                        create_model()
                    adapter.assert_not_called()
                    self.assertNotIn('private-key', str(error.exception))

    def test_direct_config_validates_and_factory_forwards(self):
        for kwargs in ({'timeout': False}, {'max_tokens': 1.5}, {'context': 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ModelConfig(**kwargs)
        config = ModelConfig.from_env({})
        with patch('google.adk.models.lite_llm.LiteLlm') as adapter:
            self.assertIs(create_model(config), adapter.return_value)
            adapter.assert_called_once_with(**config.adapter_kwargs())

    def test_cli_summary_needs_no_task_or_provider_request(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch('sys.argv', ['agent.py', '--show-config']), \
                patch('agent.create_model') as factory, redirect_stdout(output):
            self.assertEqual(main(), 0)
        factory.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['model'], 'ollama_chat/qwen3.5:2b')
        with patch.dict(os.environ, {'ACCELERATOR_AGENT_TIMEOUT': 'bad'}, clear=True), \
                patch('sys.argv', ['agent.py', '--show-config']), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 2)
