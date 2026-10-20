# Standalone agent: file tools and skill discovery

This small Google ADK `LlmAgent` connects through LiteLLM to the existing local
Ollama server. Each CLI invocation creates a fresh in-memory session for one task.
The design borrows ColliderAgent's separation of orchestration, prompts, and
file tools, and its [skill structure](https://github.com/HET-AGI/ColliderAgent/blob/main/src/skills/feynrules-model-generator/SKILL.md):
frontmatter descriptions, workflow instructions, and linked references. The
read-only, progressive skill loader here is a new implementation for this project.

From the repository root:

```bash
uv sync --locked
.venv/bin/python python-agent/agent.py 'Create notes.txt describing a FODO cell.'
.venv/bin/python python-agent/agent.py 'Which skills can you use?' --trace discovery.jsonl
```

Output defaults to `output/python-agent`, relative to the current directory.
Use `--workspace output/my-task` for a separate workspace. Tools support UTF-8
read/write/edit and immediate directory listing; writes overwrite existing files.
No shell or Python execution tool is exposed. Skills, references, blueprints,
and OPALX execution code are not modified by this implementation.

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
not enable their backends. This phase can generate input files but has no native
validation, simulation, Magnus, or internet retrieval tool. If the local references
are insufficient, the agent must report that limitation. No physics instructions
are duplicated from the existing skills.

## Model configuration

Ollama must already be running. The default tag matches the installed
`qwen3.5:4b-q4_K_M`; no server startup or model download is performed, and no Google
or OpenAI API key is required. Overrides:

```bash
export OLLAMA_API_BASE=http://localhost:11434
export ACCELERATOR_AGENT_MODEL=ollama_chat/qwen3.5:4b-q4_K_M
export ACCELERATOR_AGENT_TIMEOUT=300
export ACCELERATOR_AGENT_MAX_TOKENS=2048
export ACCELERATOR_AGENT_CONTEXT=16384
export ACCELERATOR_AGENT_REASONING=none
```

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

Offline unit tests (the original live model test remains opt-in):

```bash
.venv/bin/python -m unittest discover -s tests/python_agent -v
RUN_OLLAMA_SMOKE=1 .venv/bin/python -m unittest discover -s tests/python_agent -v
```

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
needed. The long FODO test has **not** been run, per the staged testing request.
Autonomous reference following and complete generated lattice quality are still
unverified live.

For the longer FODO generation smoke test, run separately when ready:

```bash
.venv/bin/python tests/python_agent/smoke_skills.py fodo
```

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
logging within the workspace. Without it, no execution log is written.
`--task-file path/to/request.md` reads an operator-supplied UTF-8 task instead of a
positional string. The default request limit remains eight; use `--max-calls 24`
for a generation task requiring more document retrieval. Model/connection errors
and call-limit exhaustion exit nonzero. Tool failures are returned to the model.
A successful exit means the model returned a final response; inspect tool results
and generated files before treating its scientific claims as established.

The original Phase 1 live unit test uses a temporary directory and removes it;
the two skill smoke modes preserve artifacts. Generated output remains Git-ignored.
These tool boundaries are application-level checks, not an OS sandbox. Use a
private workspace without concurrent external writers that could race path checks.
Python/library caches use their normal locations; the workspace boundary governs
agent tools and optional trace output.

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

Python callers can use `run_task(..., progress=False)`. The existing trace format
and trace option are unchanged. Already-running processes keep their original
behavior; no restart is needed to let an existing FODO run finish.
