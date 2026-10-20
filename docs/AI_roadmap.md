# Roadmap ond overview for AI implementations for accelerator-agent

## Models to explore

- Apertus 8B, 70B
- Qwen3.8-27B;
- smaller Qwen3 models, especially 0.6B, 4B, 8B, and 14B;
- one or two coder models, such as Qwen2.5-Coder 7B/14B or Qwen3-Coder-30B-A3B;
- Gemma 3 models as another comparison family
- current existing local model (ollama): qwen3.5:4b-q4_K_M

## Infrastructure to run models

- Openrouter
- CSCS inference service (for Apertus specifically)
- Ollama
- Google ADK (agent controller)
- LiteLLM (model connector)

## Plan

1. get a minimal python-agent running, using google adk and LiteLLM to connect to existing models, e.g. local qwen3.5:4b (ollama) -> give it basic file tools
2. integrate existing skills to python-agent, such that model can e.g. use lattice genertor to produce a .in file
3. integrate a tool for the python-agent to use magnus and oplax, such that model can try to run simulations
4. make agent reusable: model configuration, basic logging, error handling, documentation and simple integration tests -> models can be switched without modifying the agent code

## Progress (2026-10-20)

- Step 1 is implemented in `python-agent/`: Google ADK + LiteLLM connect to
  local Ollama model `qwen3.5:4b-q4_K_M`, with workspace-confined read, write,
  edit, and list tools. See `python-agent/README.md` for usage.
- Verification: two offline file-tool checks and the live Qwen tool-calling
  smoke test passed (three tests total; about 108 seconds). The live test uses
  a temporary directory which is deleted afterward, so it leaves no files in
  `output/python-agent/`. Normal CLI runs use that persistent workspace.
- A separate CLI demonstration also completed successfully and left
  `output/python-agent/smoke.txt` containing exactly `TOOL_OK` for inspection.
- Step 2 implementation: generic read-only skill discovery, instruction loading,
  and bounded reference search/paging are available through ADK tools. Existing
  skills and references are unchanged. Ten offline unit tests pass; the original
  live file-tool test remains opt-in. Live Qwen discovery passed (about 274 s)
  using the small test's 4,096-token context and 512-token response limits.
  An initial run with the larger defaults timed out after 300 s with no tool call.
  Both reports are preserved under `output/python-agent/discovery-20261020T*`.
  The successful test accessed all four catalog descriptions, but deliberately
  loaded no full instructions or references. Live reference following remains
  unverified; offline instruction and reference retrieval checks pass.
- A separate FODO smoke harness uses only the existing benchmark prompt and
  preserves inputs, tool-access traces, and a report under `output/python-agent/`.
  The user's FODO run retrieved instructions and reference pages but timed out
  on a model request after 600 s (about 34 minutes total); no `.in` file was
  generated. Its report is in `output/python-agent/fodo-20261020T160305898794Z/`.
  Successful complete lattice generation has not yet been established.
- Step 3 has not started. Some configuration, error handling, and test basics
  exist, but the broader step 4 remains future work. Thinking remains off by
  default; response/context limits are configurable for documentation and inputs.
- Use this roadmap to track progress across development sessions.
- Follow-up: shared readable stderr progress in `agent.py` shows model waiting
  times, tool calls/results, and errors, with a 30-second heartbeat and `--quiet`.
  Offline ADK tests cover callbacks, output summaries, quiet mode, and cleanup;
  no extra Ollama requests were made while the user's FODO run was active.
  Sixteen offline checks passed; the live Ollama test was not rerun for this change.
