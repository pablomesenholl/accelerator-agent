# Roadmap ond overview for AI implementations for accelerator-agent

## Models to explore

- Apertus 8B, 70B
- Qwen3.8-27B;
- smaller Qwen3 models, especially 0.6B, 4B, 8B, and 14B;
- one or two coder models, such as Qwen2.5-Coder 7B/14B or Qwen3-Coder-30B-A3B;
- Gemma 3 models as another comparison family
- current existing local model (ollama): qwen3.5:2b

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
- Step 3 now has an opt-in Magnus adapter and direct CLI, with nonblocking
  submission, durable job IDs, bounded status/log queries, and controlled output
  retrieval. Submission requires an operator-supplied matching PASS report.
  Existing skills, blueprints, execution scripts, and dependencies are unchanged.
  37 offline tests passed; the live Qwen test was skipped. The registered blueprint
  schema was checked through the new adapter and is compatible. A real non-LLM
  integration smoke test then passed in about 39 s (job `bab44fba338aa7d6`):
  upload/submission, reconnect/deduplication, status/logs, OPALX execution (code 0),
  controlled download, and readable statistics/HDF5 outputs all completed.
  Artifacts: `output/python-agent/magnus-smoke-20261021T174437370282Z/`.
  Backend integration is verified. The Qwen 2B execution attempt then failed after
  490 s: both execution skills loaded, but the model alternated validation-file
  reads and input listings and never invoked a backend tool or submitted a job.
  Report: `output/python-agent/qwen-execution-20261021T175348993433Z/qwen-report.json`.
  The focused Phase 3 suite now has 15 passing offline tests, including actual ADK
  tool exposure/execution with a fake backend and scripted model. Reliable Qwen
  execution remains unverified; native parser-only validation remains skipped.
  Follow-up: short repeating inspection cycles now stop early, and a system
  handoff exposes preloaded operator approval/input paths and the backend sequence.
  Submission gates are unchanged. Thirty focused offline checks passed; Qwen was
  not rerun, so model-driven execution remains the next manual verification.
  See `python-agent/MAGNUS.md` for usage and remaining limits.
- Some configuration, error handling, and test basics
  exist, but the broader step 4 remains future work. Thinking remains off by
  default; response/context limits are configurable for documentation and inputs.
- Use this roadmap to track progress across development sessions.
- 2026-10-21: the 2B FODO attempt repeatedly loaded the identical generator skill
  four times and timed out on request 6; no references or `.in` files were produced
  (`output/python-agent/fodo-20261021T163303376847Z/`). The user-selected 2B model
  configuration is preserved.
- Follow-up implementation: per-task load-once skill reminders, a guard stopping
  before the third consecutive identical tool call, clearer retrieval/generation
  instructions, and per-response token-usage records in traces and smoke reports.
  Verification: all 24 Python-agent tests passed in about 107 seconds, including
  the new regression tests and the live Qwen 2B temporary-file write/read test.
  The live test reported token counts for all three model responses. No FODO test
  or simulation was run.
- Follow-up: shared readable stderr progress in `agent.py` shows model waiting
  times, tool calls/results, and errors, with a 30-second heartbeat and `--quiet`.
  Offline ADK tests cover callbacks, output summaries, quiet mode, and cleanup;
  no extra Ollama requests were made while the user's FODO run was active.
  Sixteen offline checks passed; the live Ollama test was not rerun for this change.
- FODO smoke timeout now defaults to 1,200 seconds per model request, with explicit
  environment overrides preserved. This timeout-only adjustment has not been
  verified through another live FODO run.
