# Standalone accelerator Python agent (v0.1)

Phase 3 adds opt-in Magnus/OPALX tools and a direct, non-LLM CLI. See
[Magnus usage](MAGNUS.md) for submission gates, job records, and examples.
Phase 4 now provides validated model configuration, `--show-config`, persistent
run summaries, correlated traces, and lifecycle error reporting. Phase 4 is
complete for the roadmap's reusable-runtime scope, with offline integration
checks described below. The full autonomous physics workflow remains incomplete.
See [coder diagnostics](DIAGNOSTICS.md) for the small Ollama/LiteLLM/ADK comparison
and the identified tool-history compatibility concern.

This small Google ADK `LlmAgent` connects through LiteLLM to the existing local
Ollama server. Each CLI invocation creates a fresh in-memory session for one task.
The design borrows ColliderAgent's separation of orchestration, prompts, and
file tools, and its [skill structure](https://github.com/HET-AGI/ColliderAgent/blob/main/src/skills/feynrules-model-generator/SKILL.md):
frontmatter descriptions, workflow instructions, and linked references. The
read-only, progressive skill loader here is a new implementation for this project.
Like [ColliderAgent's Python agent](https://github.com/HET-AGI/ColliderAgent/blob/main/python-agent/agent.py),
the runtime uses `LiteLlm` → `LlmAgent` → registered tools → `InMemoryRunner`.
ColliderAgent also exposes domain validation and analysis tools; those capabilities
do not become available here merely by sharing its runner architecture.

From the repository root:

```bash
uv sync --locked
.venv/bin/python python-agent/agent.py --show-config
.venv/bin/python python-agent/agent.py 'Create notes.txt describing a FODO cell.'
.venv/bin/python python-agent/agent.py 'Which skills can you use?' --trace discovery.jsonl
```

Output defaults to `output/python-agent`, relative to the current directory.
Use `--workspace output/my-task` for a separate workspace. Tools support UTF-8
read/write/edit and immediate directory listing; writes overwrite existing files.
No shell or Python execution tool is exposed. Skills, references, blueprints,
and OPALX execution code are not modified by this implementation.

## Current capabilities and missing functionality

The first reusable runtime is implemented; a complete autonomous accelerator
study still needs additional physics capabilities and workflow verification.

| Capability | Current state |
| --- | --- |
| Model configuration, CLI, file tools, skill/reference loading | Implemented; real CLI/ADK/LiteLLM wiring checked offline. |
| Run summaries, traces, progress, errors, request/loop limits | Implemented and checked with scripted success/failure cases. |
| Lattice generation | Instructions and file-writing path implemented; successful complete model-generated OPALX input remains unverified. Scripted fixture writing does not establish physics generation. |
| Validation and approval | Operator supplies reviewed evidence for submission. No standalone deterministic validation engine or native parser-only OPALX tool is exposed. Loading `lattice-validator` supplies instructions, not a validator implementation. |
| Magnus/OPALX submission, status/logs, output retrieval | Implemented with opt-in gates and durable job records; fake-backend integration passes. The earlier direct real-backend smoke passed; reliable model-driven execution remains unverified. |
| Scientific result analysis | Missing. `tools/result_tools.py` is a placeholder, with no exposed SDDS/HDF5 reader, optics/emittance analysis, or plotting tool. Downloading output is not analysis. |

The crucial implementation follow-ups for an autonomous physics workflow are
parser-only OPALX validation and its backend/tool integration, structured
validation/review handling, and bounded result-reading/analysis tools. Input
generation, validation, simulation, and analysis should continue as separate
stages. Model-driven generation and execution need independent verification when
live testing resumes. No successful full physics study is claimed by phase 4.

Long-running chat persistence, context compaction, automatic repair/optimization,
and internet retrieval are also absent. They are extensions to the current
single-task design; session-history persistence differs from the job-ID reconnect
support already present. Remote-provider/model compatibility remains subject to
provider-specific live verification.

## Progressive skill loading

The model has three additional ADK tools:

| Tool | Result |
| --- | --- |
| `list_skills()` | Skill directory names and frontmatter descriptions, without workflow text. |
| `load_skill(skill)` | Selected `SKILL.md` instructions and available documentation paths. |
| `read_skill_document(skill, document, start_line, line_count, query)` | A bounded page or literal search results from a selected skill's document. |

The library discovers immediate subdirectories of `src/skills/` relative to the
code location, independent of the CLI's current directory. No skill names or
physics recipes are hard-coded in the loader. Frontmatter supports plain or
quoted `name`/`description` fields and indented literal/folded descriptions;
it is a small metadata reader, not a general YAML parser. Malformed skills appear
as catalog errors without hiding valid skills.

The model first discovers a relevant skill, loads its instructions, and retrieves
needed references. Skill text is returned as tool data rather than interpolated
into ADK's instruction template, so OPALX braces remain literal. Full instructions
are capped at 32,000 characters; oversized instructions can be continued through
`read_skill_document`. Reference pages are capped at 120 lines and 6,000 characters
(default 80 lines). Lines are 1-based; use `next_line` to continue. A single line
exceeding the character limit produces an explicit error rather than losing text.
Search returns at most 20 matching line numbers and snippets (240 characters each);
use `start_line` to continue searching, then retrieve relevant ranges. For example:

```text
read_skill_document("lattice-generator", "references/opalx-input-reference.md", query="Tracking")
read_skill_document("lattice-generator", "references/opalx-input-reference.md", start_line=427, line_count=40)
```

Documentation retrieval accepts regular UTF-8 `.md`, `.txt`, and `.rst` files
within the selected skill. Traversal, absolute paths, symlinks, and hard links are
rejected. To read another skill, select it explicitly. Documentation access is
read-only; workspace tools also reject the skill tree even when the operator
selects a workspace containing `src/skills/`. A workspace inside that tree is
rejected before creating directories.

Other skills, including lattice-validator, opalx-simulator, and magnus, are
already discoverable through the same interface. Loading their instructions does
not enable their backends. Native parser validation and internet retrieval remain
unavailable. Magnus tools require `--enable-magnus`, and simulation submission
requires additional operator enablement and reviewed evidence (see MAGNUS.md).
If the local references
are insufficient, the agent must report that limitation. No physics instructions
are duplicated from the existing skills.

## Model configuration

The default is `ollama_chat/qwen3.5:2b`, with Ollama already running at
`http://localhost:11434`. No server startup, model download, or API key is required
for local Ollama. Existing environment overrides remain supported:

```bash
export OLLAMA_API_BASE=http://localhost:11434
export ACCELERATOR_AGENT_MODEL=ollama_chat/qwen3.5:2b
export ACCELERATOR_AGENT_TIMEOUT=300
export ACCELERATOR_AGENT_MAX_TOKENS=2048
export ACCELERATOR_AGENT_CONTEXT=16384
export ACCELERATOR_AGENT_REASONING=none
```

Switch models without changing agent code:

```bash
ACCELERATOR_AGENT_MODEL=ollama_chat/qwen2.5-coder:3b \
.venv/bin/python python-agent/agent.py 'Create notes.txt containing HELLO, then read it back.'
.venv/bin/python python-agent/agent.py --show-config
```

`--show-config` validates settings and prints JSON without requiring a task,
creating a workspace, or calling a model. It prints the model, limits, applicable
reasoning/context settings, and booleans indicating explicit endpoint/key
configuration. Endpoint and credential values are omitted. The key flag describes
only `ACCELERATOR_AGENT_API_KEY`; it does not inspect provider-native credentials.

| Environment variable | Behavior |
| --- | --- |
| `ACCELERATOR_AGENT_MODEL` | Nonempty LiteLLM model identifier without whitespace; use an explicit provider prefix when switching providers. |
| `ACCELERATOR_AGENT_API_BASE` | Optional HTTP(S) endpoint; takes precedence over `OLLAMA_API_BASE`. Credentials, query strings, and fragments in URLs are rejected. |
| `OLLAMA_API_BASE` | Legacy endpoint override, used only for `ollama/` or `ollama_chat/` models; defaults to `http://localhost:11434`. |
| `ACCELERATOR_AGENT_API_KEY` | Optional nonempty credential forwarded to LiteLLM. Otherwise LiteLLM uses its provider-native credential configuration. |
| `ACCELERATOR_AGENT_TIMEOUT` | Finite positive seconds per model request; default `300`. |
| `ACCELERATOR_AGENT_MAX_TOKENS` | Positive integer response limit; default `2048`. |
| `ACCELERATOR_AGENT_CONTEXT` | Positive integer Ollama context size; default `16384`. Validated for all configurations, forwarded only to Ollama. |
| `ACCELERATOR_AGENT_REASONING` | `none`, `minimal`, `low`, `medium`, `high`, or `xhigh`. Defaults to `none` for Ollama and is omitted for other providers unless explicitly set. |

An empty explicitly set value is an error. Numeric and endpoint errors fail before
LiteLLM construction. Temperature stays fixed at zero and automatic retries remain
disabled. Validation checks configuration structure, not server availability,
installed model tags, credentials, or a model's support for particular parameters.
Reasoning values must also be supported by the selected provider/model.

For another LiteLLM provider, set its model identifier and provider-native
credentials, or supply the generic API key/endpoint overrides. Ollama context and
the default reasoning setting are not sent to that provider; unset an explicit
`ACCELERATOR_AGENT_REASONING` override if it should use provider defaults.
Remote-provider argument construction and the real adapter's scripted tool round
trip are covered offline; no remote-provider live test has been performed.
Settings are read from the process environment, with no
automatic `.env` loading. Python callers can use `ModelConfig.from_env(mapping)`
and `create_model(config)`; the existing no-argument `create_model()` still works.

Thinking remains disabled by default. In the installed LiteLLM Ollama adapter,
`reasoning_effort="none"` maps to `think=false`; `low`, `medium`, or `high` maps
to `think=true` for this model family. You can try `ACCELERATOR_AGENT_REASONING=low`
later for comparison. Thinking is not required for tool calls; it may help complex
reasoning, at extra CPU cost. The earlier Phase 1 tool test passed without it.
See [Ollama thinking controls](https://docs.ollama.com/capabilities/thinking) and
[tool calling](https://docs.ollama.com/capabilities/tool-calling).

The response budget was raised from 512 to 2,048 tokens to accommodate complete
input files, and the Ollama context is explicitly set to 16,384 tokens to fit
skill instructions and selected references. Both settings can increase memory
use and runtime. Retrieval is bounded per call, but the session history is not
compacted: too many document pages can still exceed the context. For a larger
study, increase context explicitly if RAM permits.

LiteLLM is constrained to ADK 1.39.1's extension/test compatibility range.
LiteLLM 1.106.0 failed tool calls with an MCP `CacheableResult` import error in
this environment. `uv.lock` pins exact versions. Step 2 adds no dependencies.

## Tests and traces

The offline suite includes unit, scripted ADK/LiteLLM, and CLI subprocess checks.
Use the explicit environment below to keep the original live model test disabled,
even if `RUN_OLLAMA_SMOKE` was inherited from another shell task:

```bash
timeout 180 env -u RUN_OLLAMA_SMOKE LITELLM_LOCAL_MODEL_COST_MAP=True \
.venv/bin/python -m unittest discover -s tests/python_agent -v
```

Phase 4 completion check (2026-10-22): **77 offline tests passed, one live test
skipped** (78 discovered; about eight seconds of test execution). Five new
integration tests cover multiple model selectors, separate execution/reconnection
sessions, provider failure, submission denial, and subprocess entrypoints.
The suite ran outside the sandbox because of the previously observed ADK
thread/event-loop stall. No live model, remote provider, Magnus, or OPALX requests
were made for this completion step.

Run only the final offline integration checks:

```bash
timeout 180 env -u RUN_OLLAMA_SMOKE LITELLM_LOCAL_MODEL_COST_MAP=True \
.venv/bin/python -m unittest discover -s tests/python_agent -p test_integration.py -v
```

| Phase 4 acceptance criterion | Evidence |
| --- | --- |
| Switch models without agent-code edits | Validated environment configuration; actual adapter tool round trips for both local model identifiers and an OpenAI-compatible fixture identifier. All provider responses are scripted. |
| Basic logging and durable run records | Unique summaries, UTC timing, usage/counts, correlated appended traces, and running/completed/failed/cancelled lifecycle tests. |
| Consistent errors | Configuration/input/startup/session/model/cleanup/recording failures, redaction, request exhaustion, and preservation of original exceptions. |
| Reusable CLI and workflow integration | Task-file invocation outside the repository directory, skill/reference retrieval, generated fixture write/read, fake reviewed submission, and a fresh session reconnecting without resubmission. |
| Documentation and reproducible checks | Configuration/usage/error semantics, bounded offline suite, capability limits, and roadmap completion status documented. |

[test_integration.py](../tests/python_agent/test_integration.py) replaces
`LiteLLMClient.acompletion` with deterministic native provider responses, retaining
the actual model factory, LiteLLM conversion, ADK runner, and tools. Network
connections in the scripted CLI runs are rejected. Subprocess checks exercise the
real entrypoint's help, configuration inspection, validation failure, and missing
task-file behavior from a different working directory, with a 30-second limit per
process. Magnus uses the existing fake backend; its synthetic input/review fixtures
are not OPALX models or scientific validation evidence. These tests establish
integration, not whether a real model can choose correct tools or physics syntax.

Live checks remain separate and opt-in. The following command contacts Ollama:

```bash
RUN_OLLAMA_SMOKE=1 .venv/bin/python -m unittest discover -s tests/python_agent -v
```

Phase 4 configuration verification (2026-10-22): 58 offline tests passed, including
six configuration tests; one live test was skipped. The suite stalled inside the
sandbox but passed outside it in about three seconds of test execution. Separate
local Ollama file-tool tests passed for `qwen3.5:2b` (101 seconds, three model
requests) and `qwen2.5-coder:3b` (119 seconds, four requests, including a redundant
read). Both wrote exactly `TOOL_OK`, read it back, and returned final text. Each
used a temporary workspace that was deleted afterward. Reproduce for either model:

```bash
RUN_OLLAMA_SMOKE=1 LITELLM_LOCAL_MODEL_COST_MAP=True \
ACCELERATOR_AGENT_MODEL=ollama_chat/qwen2.5-coder:3b \
ACCELERATOR_AGENT_TIMEOUT=180 ACCELERATOR_AGENT_MAX_TOKENS=128 \
ACCELERATOR_AGENT_CONTEXT=8192 PYTHONPATH=tests/python_agent \
.venv/bin/python -m unittest test_agent.OllamaSmokeTest -v
```

These results verify basic configuration and file-tool use. FODO generation,
validation, and model-driven simulation were not tested by this change.

Start with the small live skill-discovery smoke test:

```bash
.venv/bin/python tests/python_agent/smoke_skills.py discovery
```

It checks that Qwen actually calls `list_skills` and receives a catalog containing
lattice-generator. It intentionally does not load full instructions or references,
so it is not proof of successful lattice generation. Offline tests separately
cover full instruction loading, reference search/paging, and path restrictions.
For this small mode only, unset token/context overrides default to 512 and 4,096
respectively, keeping the first CPU check comparable to Phase 1. FODO uses the
larger normal agent defaults.

Local verification on 2026-10-20: ten offline unit tests passed; the original
Phase 1 live test was skipped in that run. The discovery smoke test passed with
an actual `list_skills` call in about 274 seconds. It returned descriptions for
lattice-generator, lattice-validator, magnus, and opalx-simulator; no full skill
instructions or references were accessed by the model. The successful artifacts
are in `output/python-agent/discovery-20261020T154825383426Z/`. An earlier discovery
attempt using the larger context/response defaults timed out at 300 seconds with
no tool call; its report is in `output/python-agent/discovery-20261020T154205178564Z/`.
These observations do not isolate the cause of the latency. CPU speed and larger
contexts remain practical limitations; increase `ACCELERATOR_AGENT_TIMEOUT` if
needed. This historical discovery check preceded the later failed FODO attempts
recorded in the roadmap. Successful complete lattice generation remains unverified.

For the longer FODO generation smoke test, run separately when ready:

```bash
.venv/bin/python tests/python_agent/smoke_skills.py fodo
```

FODO mode defaults to a 1,200-second (20-minute) timeout per model request,
allowing more CPU inference time than the previous 600-second attempt. This is
not a whole-run time limit. An explicit `ACCELERATOR_AGENT_TIMEOUT` overrides it;
the general agent and discovery timeout defaults remain unchanged.

This passes the existing benchmark request from
`tests/lattice-generator/fodo-no-spacecharge/input-prompt.md` to the agent.
Only the output location is overridden to stay inside the new workspace.
The harness never reads the existing benchmark `.in` file or uses it as a template.
It checks for discovery, successful instruction loading, actual reference-content
retrieval, and a nonempty generated `.in` file. It does **not** certify completeness,
OPALX syntax, or physics correctness. Those require a separate validation stage.

Both modes create a unique persistent directory under `output/python-agent/`
containing `task.md`, `trace.jsonl`, `report.json`, and, on a completed model run,
`response.txt`. Generated inputs also remain there. Reports list document accesses
and errors, including on failed runs. Trace records include tool arguments/results,
so you can inspect which skill, reference, query, and line range were accessed.
The FODO mode permits 24 model requests, so CPU runtime can be substantial.

For ordinary CLI tasks, `--trace trace.jsonl` enables the same append-only event
logging within the workspace. A compact run summary is always written, even
without `--trace`; detailed event payloads remain opt-in.
`--task-file path/to/request.md` reads an operator-supplied UTF-8 task instead of a
positional string. The default request limit remains eight; use `--max-calls 24`
for a generation task requiring more document retrieval. Model/connection errors
and call-limit exhaustion exit nonzero. Tool failures are returned to the model.
A successful exit means the model returned a final response, runner cleanup
completed, and the run summary was written; inspect tool results
and generated files before treating its scientific claims as established.

The original Phase 1 live unit test uses a temporary directory and removes it;
the two skill smoke modes preserve artifacts. Generated output remains Git-ignored.
These tool boundaries are application-level checks, not an OS sandbox. Use a
private workspace without concurrent external writers that could race path checks.
Python/library caches use their normal locations; the workspace boundary governs
agent tools and optional trace output.

## Run summaries and errors

Each `run_task` invocation writes a unique
`<workspace>/.agent-runs/<run_id>.json`, starting before configuration and model
setup. Summaries have `schema_version: 1` and contain:

- Run/session IDs, UTC start/end timestamps, elapsed seconds, status, and stage.
- Safe model configuration, model name, request limit, and execution flags.
- Attempted model-request count, emitted tool-call count, tool-error count, and
  per-response token usage (unavailable counts remain null).
- A structured terminal error and any additional runner-cleanup errors.

Task text, final response text, and tool payloads are not copied into summary
fields. `TaskResult` retains its existing response/tool/usage fields and adds
`run_id` and the absolute `record_path`. Summaries are replaced atomically and
updated at model-request and event checkpoints. The agent file tools and trace
destinations cannot access the reserved `.agent-runs/` tree. Existing Magnus job
records and submission gates keep their separate behavior.

| Status | Meaning |
| --- | --- |
| `running` | Initialized; a terminal outcome has not been recorded. |
| `completed` | Final text was returned, cleanup succeeded, and recording succeeded. Tool errors may still have occurred; inspect `tool_error_count` and optional trace. |
| `failed` | Configuration, input, setup, execution, cleanup, or recording failed. |
| `cancelled` | A caught cancellation or keyboard interrupt ended the run. |

`completed` describes the agent lifecycle. It does not certify generated lattice
syntax, physics correctness, or a successful simulation. Backend outcomes remain
in the Magnus tool results and job records. A killed process, power loss, or
unwritable filesystem may leave the last summary at `running`; records do not
automatically resume tasks or jobs. If the workspace is invalid or initial record
creation fails, no summary can be written and the CLI reports that limitation.

Optional JSONL trace events keep their existing names and payload fields, adding
`run_id`, UTC `timestamp`, and `elapsed_seconds`. Multiple runs can append to one
trace and be grouped by run ID. Early setup failures may have an `error` event
without a preceding `start`. Traces retain task text, tool arguments/results,
and final responses. Environment values whose names end in `_API_KEY`, `_TOKEN`,
`_SECRET`, or `_API_BASE` are redacted from recorded strings; HTTP(S) URLs are
also removed from terminal error messages. This is targeted redaction, not a
general filter for sensitive text in prompts, files, or tool results.

Errors contain `type`, `category`, `stage`, and `message`. Stages distinguish
configuration, task input, startup, session creation, execution, cleanup, and
recording. Recognized timeouts, connection/authentication/rate-limit errors,
request-limit exhaustion, and repeated tool calls have specific categories;
other errors retain their exception type and lifecycle stage. Python callers
receive the original exception with `run_record_path` and `run_error` attributes
when a record was initialized. Cleanup or diagnostic-write failures do not
replace an earlier exception; cleanup errors are saved separately, and recording
failures are attached as exception notes.

The CLI prints a concise error and record path on stderr. Exit codes are `0` for
completion, `1` for runtime failure, `130` for a keyboard interrupt, and `2` for
argument/config-inspection errors. Argument-parser failures and `--show-config`
do not start a run or create records. `--quiet` hides progress but keeps summaries
and terminal failure diagnostics. Successful final text remains on stdout.

The existing CLI command creates records automatically:

```bash
.venv/bin/python python-agent/agent.py --workspace output/my-task \
  --task-file request.md --trace trace.jsonl
```

Python callers can also use
`run_task(None, workspace, task_file=Path("request.md"))`; task-file read errors
are then included in the same lifecycle record.

For programmatic use from the repository root:

```python
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path("python-agent").resolve()))
from agent import run_task

result = asyncio.run(run_task(
    "Write notes.txt containing HELLO, then read it back.",
    Path("output/my-task"), trace="trace.jsonl",
))
print(result.response)
print(result.record_path)
```

Verification on 2026-10-22: 72 offline tests passed and one live Ollama test was
skipped, including 14 new lifecycle tests. Scripted ADK models cover correlated
traces, running/completed summaries, startup/session/input failures, timeout
redaction, tool errors, record protection, cancellation, request limits, cleanup,
and recording failures. The suite ran outside the sandbox because of the known
sandboxed ADK test stall. No live model requests, FODO generation, validation, or
simulations were performed for this change.

## Readable terminal progress

New runs print progress to stderr by default, independently of optional JSONL
tracing. This is shared by the CLI and smoke tests through `run_task`:

```text
[   0.1s] Model request 1: waiting for response...
[  30.1s] Still waiting for model response 1 (30s)
[  42.3s] Model response 1 received (42.2s)
[  42.3s] Calling list_skills()
[  42.4s] OK list_skills (4 skills)
```

The display shows model request durations, a waiting heartbeat every 30 seconds,
tool names, selected path/search arguments, returned line ranges, and tool errors.
It summarizes documents and generated files without printing their contents.
It does not stream tokens, reveal internal reasoning, or indicate a percentage
complete. A waiting heartbeat only indicates that a model response is pending;
it cannot prove that inference is advancing.

The final CLI response stays on stdout. Hide progress with:

```bash
.venv/bin/python python-agent/agent.py --quiet 'List the available skills.'
```

Python callers can use `run_task(..., progress=False)`. The trace option remains
available, with additive run-ID and timing metadata. Already-running processes keep their original
behavior; no restart is needed to let an existing FODO run finish.

## Avoiding repeated calls and diagnosing context growth

Within each task, the first successful `load_skill` returns instructions as before.
Subsequent loads of the same skill return `already_loaded: true`, the document
manifest, pagination metadata, and a short next-step reminder, without another
copy of the instructions. Failed loads are not remembered. A new task starts
fresh. Explicit bounded instruction/reference retrieval remains available through
`read_skill_document`; no source skills are changed or summarized by the loader.

The system prompt directs the model to discover, load once, search/read relevant
reference sections, then generate files. After a successful skill load that lists
references, a per-task callback adds an explicit handoff to subsequent model
requests: use `read_skill_document` with the returned skill/document paths, search
relevant topics, then retrieve bounded content before generation. Workspace file
tools cannot read these reference paths. The handoff clears once nonempty content
from a listed reference is returned; search matches and failed reads do not clear
it. Skills without references get no extra handoff. This is guidance, not tool
restriction or proof that all necessary documentation was read. No physics syntax
or benchmark templates are embedded in the handoff.

The FODO smoke also enables `run_task(require_file_output=True)`. After reference
retrieval, an explicit generation reminder stays active until a successful
nonempty `write_file` (or successful `edit_file`). If the model finishes without
such a write, the agent continues once in the same session, reusing documentation
and the remaining original model-request budget. The trace records a
`continuation` event with the premature response. A second finish without a write
fails explicitly. This checks file-tool progress, not file completeness or OPALX
validity; the smoke's `.in` checks still apply. Other tasks retain their default
behavior. No live model verification has been performed for this follow-up.

A per-task guard stops before executing
the third consecutive tool call with the same name and arguments. Default arguments
and argument key order are normalized, so omitting a default does not evade it.
It also detects exact two-call and three-call patterns repeated three times,
including alternating file reads/listings. Changing retrieval ranges still allows
progress. Read-only Magnus status/log polling resets the history and is exempt;
submission is never exempt. The error is named
`RepeatedToolCallError`, appears in the trace/report, and causes a nonzero exit.
The two earlier calls may have executed; this is an early-stop diagnostic, not a
rollback or an attempt to automatically restart the model. Longer or changing
patterns are not detected, and the overall model-request limit still applies.

Completed model responses now produce `model_usage` trace events and token-count
progress messages. `TaskResult.model_usage` and smoke-test `report.json` also retain
these entries, including in quiet mode. Fields are `request`, `available`,
`prompt_tokens`, `output_tokens`, `total_tokens`, `cached_tokens`, and
`reasoning_tokens`. Missing counts are null rather than estimated; missing usage
is explicitly marked unavailable. Counts reflect what the installed provider/ADK
adapter reports, not an independent tokenizer measurement. A timed-out request
may produce no response usage. These records can reveal input growth but cannot
alone prove whether Ollama truncated history or why a request timed out.

The change prevents duplicate skill instructions from accumulating. It does not
compact older reference pages, guarantee that the model follows the workflow, or
establish successful FODO generation. All 24 Python-agent tests passed on
2026-10-21 in about 107 seconds, including the new regression tests and the live
Qwen 2B file-tool test with token reporting. The FODO test was not run.
