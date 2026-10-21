"""Opt-in tiny Ollama/LiteLLM/ADK comparison; no physics or backend execution."""
import asyncio
import argparse
from datetime import datetime, timezone
import json
import importlib.metadata
import os
from pathlib import Path
import sys
import time
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python-agent'))
from agent import run_task
from tools.file_tools import WorkspaceFiles
from model_config import create_model
import litellm

MODEL = os.getenv('ACCELERATOR_AGENT_MODEL', 'ollama_chat/qwen2.5-coder:3b')
BASE = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
TASK = ('Use read_file to read source.txt, then use write_file to copy its exact contents '
        'to result.txt. Read first; do not guess the contents. Do not consult skills: '
        'this is a plain text file-copy task. Finally report the written path.')
SYSTEM = 'Use the supplied file tools to complete the requested task. Do not invent tool results.'
TOOLS = [{'type': 'function', 'function': {'name': name, 'description': description,
          'parameters': {'type': 'object', 'properties': {
              key: {'type': 'string'} for key in keys}, 'required': keys}}}
         for name, description, keys in [
             ('read_file', 'Read a workspace-relative text file.', ['path']),
             ('write_file', 'Write a workspace-relative text file.', ['path', 'content'])]]


def post(endpoint, payload):
    request = urllib.request.Request(BASE + endpoint, data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modes', nargs='+', choices=('ollama', 'litellm', 'adk'),
                        default=['ollama', 'litellm', 'adk'])
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root = ROOT / 'output/python-agent' / f'coder-diagnostic-{stamp}'
    root.mkdir(parents=True)
    print(f'Workspace: {root}', flush=True)
    report = {'model': MODEL, 'task': TASK, 'cases': {}, 'versions': {
        package: importlib.metadata.version(package) for package in ('google-adk', 'litellm')}}
    metadata = post('/api/show', {'model': MODEL.removeprefix('ollama_chat/')})
    (root/'model.json').write_text(json.dumps(metadata, indent=2))
    with urllib.request.urlopen(BASE + '/api/version', timeout=10) as response:
        report['ollama_version'] = json.load(response)
    for mode in args.modes:
        workspace = root / mode
        files = WorkspaceFiles(workspace)
        files.write_file('source.txt', 'HELLO')
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': TASK}]
        case = {'responses': []}
        report['cases'][mode] = case
        started = time.monotonic()
        print(f'Starting {mode}', flush=True)
        try:
            if mode == 'adk':
                os.environ['ACCELERATOR_AGENT_MODEL'] = MODEL
                os.environ['ACCELERATOR_AGENT_TIMEOUT'] = '180'
                os.environ['ACCELERATOR_AGENT_MAX_TOKENS'] = '128'
                os.environ['ACCELERATOR_AGENT_CONTEXT'] = '8192'
                model = create_model()
                original = model.llm_client.acompletion

                async def capture(**kwargs):
                    case.setdefault('assistant_history', []).append([
                        dict(message) for message in kwargs['messages']
                        if message.get('role') == 'assistant'])
                    response = await original(**kwargs)
                    case['responses'].append(response.model_dump(exclude_none=True))
                    return response

                with patch('agent.create_model', return_value=model), \
                        patch.object(model.llm_client, 'acompletion', new=capture):
                    result = asyncio.run(run_task(TASK, workspace, max_calls=4,
                                                 trace='trace.jsonl', require_file_output=True))
                case['response'] = result.response
                case['tool_calls'] = result.tool_calls
            else:
                for turn in range(4):
                    print(f'{mode}: request {turn + 1}', flush=True)
                    if mode == 'ollama':
                        payload = {'model': MODEL.removeprefix('ollama_chat/'),
                                   'messages': messages, 'tools': TOOLS, 'stream': False,
                                   'think': False, 'options': {'temperature': 0,
                                                             'num_predict': 128, 'num_ctx': 8192}}
                        response = post('/api/chat', payload)
                        message = response['message']
                    else:
                        response = litellm.completion(model=MODEL, api_base=BASE,
                            messages=messages, tools=TOOLS, temperature=0, max_tokens=128,
                            num_ctx=8192, reasoning_effort='none', timeout=180, num_retries=0)
                        response = response.model_dump(exclude_none=True)
                        message = response['choices'][0]['message']
                    case['responses'].append(response)
                    messages.append(message)
                    calls = message.get('tool_calls', [])
                    if not calls:
                        break
                    for call in calls:
                        function = call['function']
                        arguments = function['arguments']
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)
                        if function['name'] not in {'read_file', 'write_file'}:
                            raise ValueError('Unexpected tool')
                        output = getattr(files, function['name'])(**arguments)
                        reply = {'role': 'tool', 'content': json.dumps(output)}
                        if mode == 'litellm':
                            reply['tool_call_id'] = call['id']
                        else:
                            reply['tool_name'] = function['name']
                        messages.append(reply)
            target = workspace/'result.txt'
            case['success'] = target.exists() and target.read_text() == 'HELLO'
        except Exception as exc:
            case.update(success=False, error=f'{type(exc).__name__}: {exc}')
        case['elapsed_seconds'] = round(time.monotonic() - started, 2)
        (root/'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'{mode}: success={case["success"]} ({case["elapsed_seconds"]}s)', flush=True)
    return 0 if all(case['success'] for case in report['cases'].values()) else 1


if __name__ == '__main__':
    sys.exit(main())
