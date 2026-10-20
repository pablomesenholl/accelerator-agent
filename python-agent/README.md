# Standalone agent: Phase 1

This is a small Google ADK `LlmAgent` using LiteLLM and the existing local
Ollama server. Following [ColliderAgent's Python agent](https://github.com/HET-AGI/ColliderAgent/tree/main/python-agent),
it separates model configuration, prompt, tools, and orchestration. Only file
tools are registered; skills and Magnus are not integrated in this phase.

From the repository root:

```bash
uv sync --locked
.venv/bin/python python-agent/agent.py 'Create notes.txt describing a FODO cell.'
.venv/bin/python python-agent/agent.py --workspace output/my-task 'Read notes.txt'
```

Each invocation creates a fresh in-memory session and accepts one quoted task.
The default workspace is `output/python-agent`, relative to the current directory.
The operator chooses the workspace; the model cannot change it. Tools support
UTF-8 read/write/edit and directory listing. Writes overwrite existing files.
No shell or Python execution tool is exposed. The default limit is eight model
calls per task; change it with `--max-calls`.

The default model matches the installed `qwen3.5:4b-q4_K_M` tag. Ollama must
already be running; no model download or server startup is performed. No Google
or OpenAI API key is needed. Override configuration when necessary:

```bash
export OLLAMA_API_BASE=http://localhost:11434
export ACCELERATOR_AGENT_MODEL=ollama_chat/qwen3.5:4b-q4_K_M
export ACCELERATOR_AGENT_TIMEOUT=300
```

LiteLLM uses Ollama's native chat endpoint, with thinking disabled for this small
file-tool workflow. See [LiteLLM's Ollama integration](https://docs.litellm.ai/docs/providers/ollama).
LiteLLM is constrained to the range used by Google ADK 1.39.1's own
extension/test dependencies. LiteLLM 1.106.0 failed tool calls with an MCP
`CacheableResult` import error in this environment. `uv.lock` pins exact versions;
update the constraint only after checking the live smoke test.

Connection failures, model errors, and call-limit exhaustion exit nonzero.
Tool failures are returned to the model as error results.

Run offline checks and the live tool-calling smoke test:

```bash
.venv/bin/python -m unittest discover -s tests/python_agent -v
RUN_OLLAMA_SMOKE=1 .venv/bin/python -m unittest discover -s tests/python_agent -v
```

The live test uses a temporary workspace and verifies actual ADK tool calls,
written file contents, and a successful read result; it fails if the model merely
claims success. It is skipped unless explicitly enabled and may take a few minutes
on CPU (each model request has a 300-second timeout and a 512-token response limit).

File tools reject absolute paths, parent traversal, symlinks, and hard-linked
files. Both reads and writes are confined. This is an application-level boundary,
not an OS sandbox: use a private workspace with no concurrent external filesystem
writers, since path checks cannot protect against another process racing to
replace files or directories. Dependency caches and temporary test files use
normal Python/library locations; the workspace boundary applies to agent tools.
