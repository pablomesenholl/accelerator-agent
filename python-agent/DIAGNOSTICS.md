# Coder tool-use diagnostic (2026-10-21)

Plan: inspect the installed model/template and adapter settings; compare a tiny
read/write task through raw Ollama, LiteLLM, and the standalone ADK agent; inspect
response/history conversion offline. No FODO or Magnus runs were performed.

Installed: `qwen2.5-coder:3b`, 3.1B Q4_K_M, advertising tool support;
Ollama 0.40.6, LiteLLM 1.83.14, Google ADK 1.39.1. The adapter maps
`reasoning_effort=none` to `think=false`; no forced JSON response format was found
in the agent configuration. The installed chat template explicitly requests
`<tool_call>` tags rather than Markdown fences.

Reproduce the opt-in diagnostic (uses local Ollama):

```bash
ACCELERATOR_AGENT_MODEL=ollama_chat/qwen2.5-coder:3b \
.venv/bin/python tests/python_agent/diagnose_coder.py
```

Each path has at most four model requests, 128 output tokens/request, an 8,192
token context and a 180-second request timeout. Generated artifacts stay under
`output/python-agent/coder-diagnostic-*`. Raw Ollama/LiteLLM responses, responses
before ADK conversion, model metadata/template and per-path results are retained.
The ADK path uses the existing system prompt and larger tool set; this is an
integration comparison, not an identical-prompt model benchmark.

The first probe ambiguously mixed copying with following an instruction; its
content check is not reliable. It is retained in
`output/python-agent/coder-diagnostic-20261021T213044371430Z/`.

The corrected probe copies `source.txt` containing `HELLO` to `result.txt`:

| Path | Result | Seconds |
|---|---|---:|
| Raw Ollama | Fenced JSON in ordinary content; no native tool calls; guessed file contents | 15.60 |
| LiteLLM | Fenced JSON in ordinary content; no native tool calls; guessed file contents | 12.75 |
| ADK agent | Read and wrote the exact content successfully; final response was an empty JSON fence | 20.12 |

Corrected artifacts:
`output/python-agent/coder-diagnostic-20261021T213318167573Z/`.
The final empty fence is present in the captured LiteLLM response **before** ADK
conversion. It is not solely a display bug or context-window exhaustion: it also
occurs here at about 1,300 prompt tokens.

An offline replay (`history-conversion.json` in that directory) identified a
specific compatibility concern. ADK's inline-JSON fallback recovers the fenced
tool call but retains the empty fence as text. The next assistant message contains
both `content="```json\n\n```"` and `tool_calls`. The installed Ollama template
renders `.Content` preferentially and renders `.ToolCalls` only in its `else`
branch, hiding the recovered call from subsequent model history. Thus the model
can be shown empty fences where earlier tool calls should appear. The existing
fallback explains why ADK can execute calls that raw Ollama/LiteLLM do not expose
as native calls.

Conclusion: tool-format compliance is unreliable, and there is a concrete
ADK/template history mismatch that may reinforce empty responses. This does not
prove that the mismatch causes every FODO failure or that the model can generate
correct OPALX. Next, test a narrowly scoped removal of empty fence remnants only
when a recovered function call is present, preserving meaningful text and genuine
final responses. Validate that history offline and with this tiny probe before
another FODO attempt. No runtime/model/template fixes were made during diagnosis.

## Empty-fence fix

The agent's after-model callback now removes a text part consisting solely of an
empty JSON/unlabelled Markdown fence when the same completed response contains
a function call. This happens before ADK saves the response in session history.
Tool calls, meaningful text, thoughts, partial responses and genuine final
responses without calls are preserved. The fix changes no installed packages,
Ollama template, model defaults or physics instructions. It does not force native
tool-format compliance or guarantee complete OPALX generation.

Forty focused offline tests passed, including ADK inline-JSON parsing, outgoing
history conversion and an actual runner session. The diagnostic supports
`--modes adk` to repeat only the short end-to-end copy check; it also saves outgoing
assistant history for comparison with responses captured before ADK conversion.

Direct architecture reference: [ColliderAgent python-agent/agent.py](https://github.com/HET-AGI/ColliderAgent/blob/main/python-agent/agent.py),
particularly `_build_adk_agent`, `_build_system_prompt` and `run`. It uses
`LiteLlm` + `LlmAgent` + registered tools + `InMemoryRunner`, with explicit
reference-reading instructions before generation. Our implementation retains
that core pattern and its separation of reference retrieval and file writing.
The referenced agent has no corresponding empty-fence cleanup; its default API
configuration does not establish compatibility with this local coder model.
The callback is a local compatibility fix, not copied upstream functionality.

Live follow-up after the fix:
`output/python-agent/coder-diagnostic-20261021T215556390529Z/`.
The ADK-only probe passed in 94.62 s: `read_file`, `write_file`, one redundant
`write_file`, then a meaningful completion response. `result.txt` contained
exactly `HELLO`. Captured outgoing assistant history had `content=null` alongside
every tool call, confirming empty fences were removed before Ollama saw that
history. This single short probe supports the compatibility fix, but does not
establish reliable FODO generation or eliminate redundant calls. FODO was not rerun.
