# Roadmap and overview for AI implementations for accelerator-agent

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

## Current status (2026-10-22)

**Phase 4 is complete within the scope above.** The reusable v0.1 runtime has
validated model configuration, progress/logging, persistent run summaries,
structured lifecycle errors, usage documentation, and deterministic integration
checks. The final offline suite discovered 78 tests: 77 passed and one opt-in live
test was skipped. No live Qwen or backend testing was performed for this final step.

This completes the first runtime baseline, not a full autonomous physics agent.
The Python agent still lacks these crucial capabilities:

- Native parser-only OPALX validation and its backend/tool integration. Validation
  instructions are discoverable, but submission uses operator-supplied matching
  review evidence; there is no deterministic validator implementing those checks.
- Scientific output readers and analysis tools for SDDS/HDF5, beam/optics metrics,
  and plots. `python-agent/tools/result_tools.py` is still a placeholder.

Successful complete model-generated OPALX inputs and reliable model-driven
simulation remain unverified. These are distinct workflow-verification gaps;
scripted fixture generation and fake-backend success do not resolve them. The
earlier direct real-backend smoke verifies the execution adapter only.
Persistent conversation resume, context compaction, automatic repair/optimization,
and internet retrieval are additional extensions outside this phase's scope.

The next implementation priorities are the validation handoff and result-analysis
capabilities, followed by independent end-to-end verification of the separate
generation, validation, simulation, and analysis stages. Local-model feasibility
and a ColliderAgent comparison remain a separate future experiment. Phase 4 is
not contingent on that experiment. See
[the Python-agent guide](../python-agent/README.md) for completion evidence,
offline commands, and capability limits. The entries below retain development
history and their historical verification counts.

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
- Step 4 is now complete for its reusable-runtime scope, including validated model
  configuration, run records/errors, documentation, and offline integration
  checks (see the 2026-10-22 entries below). Thinking remains off by
  default; response/context limits are configurable for documentation and inputs.
- Use this roadmap to track progress across development sessions.
- Coder diagnostic: raw Ollama/LiteLLM returned fenced tool JSON as text; ADK's
  fallback successfully copied a tiny file but ended with empty JSON. Offline
  replay found empty fence remnants accompanying recovered tool calls, while the
  installed Ollama template prioritizes text and hides those calls in history.
  This is a concrete compatibility concern, not proof of the sole FODO cause.
  See `python-agent/DIAGNOSTICS.md`; runtime fixes and FODO retesting remain pending.
- Empty-fence compatibility fix now removes only empty fence text accompanying
  function calls before ADK stores history. Forty focused offline tests passed.
  The short live coder copy probe passed with a meaningful final response; captured
  outgoing history confirmed no fence remnants (one redundant write remained).
  ColliderAgent's Python implementation was consulted directly; the core ADK /
  LiteLLM / tools / runner architecture is retained. FODO verification is pending.
- Generation follow-up: added a generic skill-to-reference handoff to model
  requests after loading a skill with associated documents. It points to bounded
  retrieval through `read_skill_document` and clears after reference content is
  returned. No tool restrictions or physics templates were added. Live model
  verification remains pending; this does not establish generation correctness.
- Generation follow-up now keeps a post-reference generation reminder and enables
  one same-session continuation for the FODO smoke if no successful file write
  occurred. The original request budget remains in force; a second premature
  finish fails. Thirty-six focused offline tests passed, including continuation
  success, bounded failure and budget exhaustion. Qwen was not rerun.
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
- 2026-10-22, Phase 4 configuration: immutable validated settings preserve the
  user's `ollama_chat/qwen3.5:2b` default and existing environment overrides.
  Generic API endpoint/key overrides support provider switching; Ollama context
  and default reasoning are sent only to Ollama. Numeric limits, reasoning values,
  and endpoint structure are checked before adapter construction. `--show-config`
  prints settings without endpoint/key values or a model request. No dependencies,
  skills, blueprints, or backend execution code changed. Documentation describes
  precedence, provider-native credentials, validation limits, and reproduction.
  Verification: 58 offline tests passed and one live test was skipped, including
  six new configuration tests. The sandboxed suite timed out at 180 seconds in a
  scripted ADK test; outside the sandbox all tests completed in about three seconds
  of test execution. Python's sandboxed Ollama connection was explicitly denied;
  live checks were run outside the sandbox. Separate temporary-workspace file-tool
  checks passed for `qwen3.5:2b` (101 seconds, three requests) and
  `qwen2.5-coder:3b` (119 seconds, four requests, one redundant read), using a
  180-second request timeout, 128 output tokens, and an 8,192-token context.
  This establishes basic model switching and file-tool use, not FODO generation
  or reliable model-driven simulation. Remote providers were tested only through
  offline argument checks. At this checkpoint, consistent run records and
  startup/error reporting were the next Phase 4 work; comparison with ColliderAgent on small local
  models remains a separate follow-up.
- 2026-10-22, Phase 4 run records/errors: every initialized task now has an
  atomically replaced `.agent-runs/<run_id>.json` summary within its workspace,
  with safe configuration, UTC timing, session ID, request/tool counts, usage,
  terminal status, structured errors, and separate cleanup failures. Running
  checkpoints are saved before waiting for model responses. Optional JSONL traces
  retain existing events and gain run IDs and timing metadata. Agent file tools
  and trace destinations cannot access the run-record tree. Task-file reads,
  configuration, setup/session creation, execution, and cleanup share one error
  lifecycle; original Python exceptions are preserved and CLI failures report a
  category/type and record path. Configured credential values are redacted from
  recorded strings and URLs from terminal errors. Summaries omit task/response
  text and tool payload fields; detailed traces remain opt-in. Completion requires
  final text, successful cleanup, and successful recording, and does not imply
  physics or backend success. Invalid/unwritable workspaces may prevent recording;
  hard termination may leave a running checkpoint. No automatic retries or resume
  behavior were added. Verification: 72 offline tests passed, one live test
  skipped, including 14 new lifecycle tests; tests ran outside the sandbox due to
  the previously observed scripted ADK stall. No live models, FODO generation,
  validation, or simulations were run. Existing configuration work, skills,
  blueprints, dependencies, backend scripts, and Magnus submission gates were
  preserved. At this checkpoint, remaining Phase 4 work was a final integration/documentation review;
  reliable small-model physics workflows and the ColliderAgent local-model
  comparison remain separately unverified.
- 2026-10-22, Phase 4 integration/documentation completion: consulted
  [ColliderAgent's runtime](https://github.com/HET-AGI/ColliderAgent/blob/main/python-agent/agent.py)
  and [pipeline test](https://github.com/HET-AGI/ColliderAgent/blob/main/python-agent/tests/test_e2e_pipeline.py).
  Its ADK/LiteLLM/tool/runner pattern is retained; its domain validation and
  analysis capabilities are not implemented here merely through skill discovery.
  Added five offline integration tests through the actual CLI, model factory,
  LiteLLM conversion, ADK runner, skills, workspace files, and run records. Provider
  responses are scripted at the transport boundary and socket connections are
  rejected during those runs. Tests cover both local model selectors and an
  OpenAI-compatible fixture selector, provider failure/redaction, denied
  submission, and approved fake-backend submission followed by a fresh session's
  status/log/retrieval without a second launch. Real CLI subprocess checks from
  another directory cover help, configuration, invalid settings, and task-file
  failure, with per-process timeouts. Synthetic inputs and review reports are
  wiring fixtures only. No runtime defects requiring changes were found.
  Verification: 77 offline tests passed, one live test skipped (78 total; about
  eight seconds of test execution), outside the sandbox due to the known ADK
  thread/event-loop limitation. No live Qwen, remote-provider, Magnus, or OPALX
  calls, blueprint registrations, or dependency changes were made. Documentation
  was updated after testing, including current defaults, offline commands,
  completion criteria, and missing capabilities. Phase 4 is complete; the current
  status section above records the remaining work for a full physics assistant.
