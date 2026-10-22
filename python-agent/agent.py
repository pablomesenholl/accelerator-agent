"""Minimal standalone ADK agent and single-task CLI."""
import argparse
import asyncio
import inspect
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
import sys
import time

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.agents.run_config import RunConfig
from google.genai import types

from model_config import ModelConfig, create_model
from tools.file_tools import WorkspaceFiles
from tools.skill_tools import DEFAULT_SKILLS_ROOT, SkillLibrary
from run_records import RUN_DIRECTORY, RunRecord, diagnostic_message, utc_now
from tools.magnus_tools import JOB_DIRECTORY, MagnusTools


@dataclass
class TaskResult:
    response: str = ""
    tool_calls: list[str] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    tool_requests: list[dict] = field(default_factory=list)
    model_usage: list[dict] = field(default_factory=list)
    run_id: str = ""
    record_path: str = ""


class RepeatedToolCallError(RuntimeError):
    """A task stopped because identical tool calls were not making progress."""


def _remove_empty_tool_fences(llm_response):
    """Remove ADK inline-tool parser remnants before they enter session history."""
    if llm_response.partial or not llm_response.content:
        return None
    parts = llm_response.content.parts or []
    if not any(part.function_call for part in parts):
        return None
    kept = [part for part in parts if not (
        part.text is not None and not part.thought
        and re.fullmatch(r'\s*```(?:json)?[ \t]*\r?\n\s*```\s*',
                         part.text, flags=re.IGNORECASE))]
    if len(kept) == len(parts):
        return None
    return llm_response.model_copy(update={
        'content': llm_response.content.model_copy(update={'parts': kept})})


class _ToolLoopGuard:
    def __init__(self, limit: int = 3):
        self.limit = limit
        self.previous = None
        self.count = 0
        self.history = []

    def before_tool(self, tool, args, tool_context):
        if tool.name in {'get_opalx_job_status', 'read_opalx_job_logs'}:
            # Bounded read-only polling is legitimate; never exempt submission.
            self.previous, self.count = None, 0
            self.history.clear()
            return
        normalized = args
        if hasattr(tool, "func"):
            try:
                bound = inspect.signature(tool.func).bind(**args)
                bound.apply_defaults()
                normalized = bound.arguments
            except (TypeError, ValueError):
                pass  # ADK will report missing/invalid arguments if execution proceeds.
        signature = json.dumps([tool.name, normalized], sort_keys=True, default=str)
        self.count = self.count + 1 if signature == self.previous else 1
        self.previous = signature
        self.history.append(signature)
        self.history = self.history[-3 * self.limit:]
        if self.count >= self.limit:
            raise RepeatedToolCallError(
                f"Stopped before executing {tool.name}: {self.count} consecutive identical "
                "tool calls. Reuse previous results or change the retrieval query/range. "
                "Inspect the trace before retrying."
            )
        for period in (2, 3):
            if len(self.history) >= period * self.limit:
                recent = self.history[-period * self.limit:]
                if recent == recent[:period] * self.limit:
                    raise RepeatedToolCallError(
                        f"Stopped before executing {tool.name}: a {period}-call pattern "
                        f"repeated {self.limit} times. Reuse previous results and advance "
                        "the workflow. Inspect the trace before retrying."
                    )


def _execution_handoff(magnus: MagnusTools) -> str:
    """Expose operator configuration already snapshotted by the submission gate."""
    approval = magnus.approval or {}
    configuration = {
        'submission_enabled': magnus.allow_simulation,
        'report_status': approval.get('status'),
        **{key: approval.get(key) for key in ('simulation', 'input_file', 'input_digest')},
    }
    return (
        '\n\nExecution handoff (operator configuration):\n'
        + json.dumps(configuration, ensure_ascii=False)
        + '\nThe report is already preloaded by the adapter. Repeated file reads or '
        'directory listings do not authorize execution. If execution is requested, '
        'submission is enabled, and report_status is PASS: consult opalx-simulator '
        'and magnus once, then call inspect_opalx_backend. If compatible, call '
        'submit_opalx_simulation with the exact simulation and input_file above. '
        'The tool must still verify all report checks and the current input digest; '
        'this handoff does not validate inputs or bypass that gate. Otherwise report '
        'the missing approval and do not submit. Keep the returned job ID, inspect '
        'status/logs, and retrieve outputs when complete. Stop on gate errors and '
        'report them; do not edit the input or approval to bypass them.'
    )


class _SkillHandoff:
    """Per-task guidance from successful skill loads to bounded reference reads."""

    def __init__(self, require_file_output=False):
        self.pending = {}
        self.retrieved = set()
        self.require_file_output = require_file_output
        self.file_written = False

    def after_tool(self, tool, args, tool_context, tool_response):
        if not isinstance(tool_response, dict) or 'error' in tool_response:
            return
        if tool.name in {'write_file', 'edit_file'} and (
                tool_response.get('written') or tool_response.get('edited')):
            if tool.name == 'edit_file' or args.get('content', '').strip():
                self.file_written = True
        skill = tool_response.get('skill')
        if tool.name == 'load_skill' and skill and skill not in self.retrieved:
            documents = [p for p in tool_response.get('documents', []) if p != 'SKILL.md']
            if documents:
                self.pending[skill] = documents
        elif (tool.name == 'read_skill_document' and skill in self.pending
              and tool_response.get('document') in self.pending[skill]
              and tool_response.get('content', '').strip()):
            self.pending.pop(skill)
            self.retrieved.add(skill)

    def before_model(self, callback_context, llm_request):
        if self.pending:
            llm_request.append_instructions([
                'Skill-to-reference handoff: instructions are already loaded. '
                'Next, use read_skill_document with the skill and document path '
                'listed below. Search for a relevant topic, then read a bounded '
                'line range containing the required syntax. Search matches alone '
                'are not retrieved instructions. Continue truncated SKILL.md first '
                'if needed. Do not reload the skill or look for these documents '
                'with workspace read_file/list_files. Retrieve relevant reference '
                'content before generating domain files. After retrieval, follow '
                'the skill and proceed with the requested task; more sections may '
                'still be needed. Pending references: '
                + json.dumps(self.pending, ensure_ascii=False)
            ])
        if self.require_file_output and self.retrieved and not self.file_written:
            llm_request.append_instructions([
                'Reference-to-generation handoff: the requested file-generation task '
                'is still unfinished. A reference page is not the whole document; '
                'follow next_line or search/read other relevant sections as needed. '
                'Then use write_file/edit_file to produce the requested workspace '
                'files following the skill. Do not finish with an empty code block '
                'or a promise to write files. Report actual paths and limitations. '
                'If blocked, explain the specific missing information honestly.'
            ])


class _Progress:
    """Concise terminal status; never print prompts, file contents, or reasoning."""

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.started = time.monotonic()
        self.waiting_since = None
        self.model_calls = 0

    @staticmethod
    def short(value) -> str:
        return " ".join(str(value).split())[:180]

    def show(self, message: str):
        if self.enabled:
            elapsed = time.monotonic() - self.started
            print(f"[{elapsed:6.1f}s] {message}", file=sys.stderr, flush=True)

    def before_model(self, callback_context, llm_request):
        self.model_calls += 1
        self.waiting_since = time.monotonic()
        self.show(f"Model request {self.model_calls}: waiting for response...")

    def after_model(self, callback_context, llm_response):
        if self.waiting_since is not None:
            duration = time.monotonic() - self.waiting_since
            self.show(f"Model response {self.model_calls} received ({duration:.1f}s)")
            self.waiting_since = None

    async def heartbeat(self):
        while True:
            await asyncio.sleep(30)
            if self.waiting_since is not None:
                elapsed = time.monotonic() - self.waiting_since
                self.show(f"Still waiting for model response {self.model_calls} ({elapsed:.0f}s)")

    def record(self, kind: str, data: dict):
        if kind == "start":
            self.show(f"Starting task with {self.short(data['model'])}")
        elif kind == "tool_call":
            args = data["args"]
            details = ", ".join(f"{key}={self.short(args[key])}" for key in
                                ("skill", "document", "path", "query", "start_line", "line_count",
                                 "simulation", "input_file", "job_id", "page")
                                if key in args)
            self.show(f"Calling {data['name']}({details})")
        elif kind == "tool_result":
            result = data["response"]
            if "error" in result:
                self.show(f"FAILED {data['name']}: {self.short(result['error'])}")
                return
            details = []
            for key in ("skill", "document", "written", "edited", "job_id", "status", "output_path"):
                if key in result:
                    details.append(f"{key}={self.short(result[key])}")
            for key in ("skills", "entries", "matches"):
                if key in result:
                    details.append(f"{len(result[key])} {key}")
            if "content" in result:
                count = len(result["content"].splitlines())
                if "start_line" in result and count:
                    start = result["start_line"]
                    details.append(f"lines {start}-{start + count - 1}")
                else:
                    details.append(f"{count} lines retrieved")
            if result.get("next_line") is not None:
                details.append(f"next_line={result['next_line']}")
            if result.get("already_loaded"):
                details.append("already loaded; full instructions omitted")
            suffix = f" ({'; '.join(details)})" if details else ""
            self.show(f"OK {data['name']}{suffix}")
        elif kind == "model_usage":
            if data["available"]:
                counts = ", ".join(f"{key}={data[key] if data[key] is not None else 'unknown'}"
                                   for key in ("prompt_tokens", "output_tokens", "total_tokens"))
                self.show(f"Tokens for request {data['request']}: {counts}")
            else:
                self.show(f"Tokens for request {data['request']}: usage unavailable")
        elif kind == "final":
            self.show("Agent finished.")
        elif kind == "error":
            self.show(f"Agent stopped: {self.short(data['message'])}")


async def run_task(task: str | None, workspace: Path, max_calls: int = 8,
                   trace: str | None = None, progress: bool = True,
                   enable_magnus: bool = False, allow_simulation: bool = False,
                   validation_report: str | None = None,
                   require_file_output: bool = False,
                   task_file: Path | None = None) -> TaskResult:
    # A record cannot be written until the workspace itself is safe and writable.
    files = WorkspaceFiles(workspace, read_only_roots=(DEFAULT_SKILLS_ROOT,))
    run = RunRecord(files, max_calls=max_calls, enable_magnus=enable_magnus,
                    allow_simulation=allow_simulation, require_file_output=require_file_output)
    display = _Progress(progress)
    run.runner = None
    heartbeat = None
    trace_file = None
    primary = None
    result = None

    def record(kind, data):
        if kind == "model_usage":
            run.data["model_usage"].append(data)
        elif kind == "tool_call":
            run.data["tool_calls"] += 1
        elif kind == "tool_result" and "error" in data["response"]:
            run.data["tool_error_count"] += 1
        run.data["model_requests"] = display.model_calls
        data = run.redact(data)
        display.record(kind, data)
        if trace_file:
            with trace_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event": kind, **data, "run_id": run.run_id,
                                         "timestamp": utc_now(),
                                         "elapsed_seconds": round(time.monotonic() - run.started, 3)},
                                        ensure_ascii=False) + "\n")
        run.save()

    try:
        # Validate trace paths against the same protected trees as the agent tools.
        protected = WorkspaceFiles(workspace, read_only_roots=(DEFAULT_SKILLS_ROOT,
                                    files.root / JOB_DIRECTORY, files.root / RUN_DIRECTORY))
        trace_file = protected._path(trace) if trace else None
        if trace_file:
            trace_file.parent.mkdir(parents=True, exist_ok=True)
        run.data["stage"] = "configuration"
        config = ModelConfig.from_env()
        run.data["configuration"] = config.summary()
        run.data["model"] = config.model
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 1:
            raise ValueError("max_calls must be a positive integer")
        if allow_simulation and (not enable_magnus or not validation_report):
            raise ValueError('Simulation requires enable_magnus and validation_report')
        run.data["stage"] = "task_input"
        if task_file is not None:
            if task is not None:
                raise ValueError("Provide exactly one task or task_file")
            task = task_file.read_text(encoding="utf-8")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("Task must be nonempty text")
        run.data["stage"] = "startup"
        record("start", {"task": task, "model": config.model, "max_calls": max_calls})
        display.show(f"Workspace: {files.root}")
        display.show(f"Run record: {run.path}")
        if progress:
            heartbeat = asyncio.create_task(display.heartbeat())
        result = await _execute_task(task, workspace, max_calls, enable_magnus,
                                     allow_simulation, validation_report, require_file_output,
                                     config, run, display, record)
    except BaseException as exc:
        primary = exc
        failure = run.error(exc, run.data["stage"])
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        if run.runner is not None:
            try:
                await run.runner.close()
            except BaseException as exc:
                cleanup = run.error(exc, "cleanup")
                run.data["cleanup_errors"].append(cleanup)
                if primary is None:
                    primary, failure = exc, cleanup
        run.data["model_requests"] = display.model_calls

    if primary is not None:
        # Keep the original Python exception even if diagnostics cannot be written.
        run.data["stage"] = failure["stage"]
        primary.run_record_path = str(run.path)
        primary.run_error = failure
        try:
            record("error", failure)
        except Exception as exc:
            primary.add_note("Could not append error trace: " + run.error(exc, "recording")["message"])
        try:
            run.finish(failure)
        except Exception as exc:
            primary.add_note("Could not finalize run record: " + run.error(exc, "recording")["message"])
            display.show("Could not finalize run record; its status may still be running.")
        raise primary
    # Completion is recorded only after runner cleanup succeeds.
    run.data["stage"] = "completed"
    try:
        run.finish()
        record("final", {"response": result.response})
    except Exception as exc:
        failure = run.error(exc, "recording")
        run.data["stage"] = "recording"
        exc.run_record_path, exc.run_error = str(run.path), failure
        try:
            run.finish(failure)
        except Exception as write_error:
            exc.add_note("Could not finalize run record: " + run.error(write_error, "recording")["message"])
        try:
            record("error", failure)
        except Exception as write_error:
            exc.add_note("Could not append error trace: " + run.error(write_error, "recording")["message"])
        raise
    return result


async def _execute_task(task, workspace, max_calls, enable_magnus, allow_simulation,
                        validation_report, require_file_output, config, run, display, record):
    library = SkillLibrary()
    files = WorkspaceFiles(workspace, read_only_roots=(library.root,
                           workspace.expanduser().resolve() / JOB_DIRECTORY,
                           workspace.expanduser().resolve() / RUN_DIRECTORY))
    tools = [files.read_file, files.write_file, files.edit_file, files.list_files,
             library.list_skills, library.load_skill, library.read_skill_document]
    instruction = (Path(__file__).parent / "prompts" / "sytem.md").read_text()
    if enable_magnus:
        magnus = MagnusTools(files.root, allow_simulation, validation_report)
        instruction += _execution_handoff(magnus)
        tools.extend([magnus.inspect_opalx_backend, magnus.inspect_simulation_input,
                      magnus.submit_opalx_simulation, magnus.get_opalx_job_status,
                      magnus.read_opalx_job_logs, magnus.retrieve_opalx_outputs])
    result = TaskResult(run_id=run.run_id, record_path=str(run.path))
    guard = _ToolLoopGuard()
    handoff = _SkillHandoff(require_file_output)

    def before_model(callback_context, llm_request):
        display.before_model(callback_context, llm_request)
        run.data["model_requests"] = display.model_calls
        run.save()

    def after_model(callback_context, llm_response):
        display.after_model(callback_context, llm_response)
        if llm_response.partial:
            return
        metadata = llm_response.usage_metadata
        counts = {name: getattr(metadata, field, None) for name, field in (
            ("prompt_tokens", "prompt_token_count"),
            ("output_tokens", "candidates_token_count"),
            ("total_tokens", "total_token_count"),
            ("cached_tokens", "cached_content_token_count"),
            ("reasoning_tokens", "thoughts_token_count"),
        )}
        usage = {"request": display.model_calls,
                 "available": any(value is not None for value in counts.values()),
                 **counts}
        result.model_usage.append(usage)
        record("model_usage", usage)
        return _remove_empty_tool_fences(llm_response)

    agent = LlmAgent(
        name="accelerator_agent",
        model=create_model(config),
        # A provider preserves literal braces in operator paths/JSON: ADK must
        # not interpret them as session-state placeholders.
        instruction=lambda ctx: instruction,
        tools=tools,
        before_model_callback=[before_model, handoff.before_model],
        after_model_callback=after_model,
        before_tool_callback=guard.before_tool,
        after_tool_callback=handoff.after_tool,
    )
    runner = InMemoryRunner(agent=agent, app_name="accelerator_agent")
    run.runner = runner
    run.data["model"] = str(agent.model.model)
    run.data["stage"] = "session"
    session = await runner.session_service.create_session(
        app_name="accelerator_agent", user_id="local"
    )
    run.data["session_id"] = session.id
    run.data["stage"] = "execution"
    run.save()
    message = task
    for attempt in range(2):
        result.response = ""
        async for event in runner.run_async(
            user_id="local", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
            run_config=RunConfig(max_llm_calls=max_calls - display.model_calls),
        ):
            if event.error_code:
                raise RuntimeError(event.error_message or event.error_code)
            for call in event.get_function_calls():
                result.tool_calls.append(call.name)
                request = {"name": call.name, "args": call.args or {}}
                result.tool_requests.append(request)
                record("tool_call", request)
            for response in event.get_function_responses():
                entry = {"name": response.name, "response": response.response}
                result.tool_results.append(entry)
                record("tool_result", entry)
            if event.is_final_response() and event.content:
                result.response = "\n".join(
                    part.text for part in event.content.parts or []
                    if part.text and not part.thought
                )
        if not require_file_output or handoff.file_written:
            break
        if attempt == 1 or display.model_calls >= max_calls:
            raise RuntimeError("File-generation task ended without a successful nonempty file write")
        record("continuation", {"reason": "No successful nonempty file write", "attempt": 1,
                                "response": result.response})
        display.show("No generated file; continuing once within the remaining model-request budget.")
        message = (
            "The original file-generation task is unfinished: no successful nonempty "
            "workspace file write was recorded. Continue from the existing skill/reference "
            "results. Retrieve missing relevant sections, then write the requested files. "
            "Do not restart discovery or reload skills. If blocked, explain the specific "
            "reason; do not invent syntax. This is the only automatic continuation."
        )
    if not result.response:
        raise RuntimeError("Model returned no final text response")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", help="Natural-language task (quote as one argument)")
    parser.add_argument("--task-file", type=Path, help="Read a UTF-8 task supplied by the operator")
    parser.add_argument("--workspace", type=Path, default=Path("output/python-agent"))
    parser.add_argument("--max-calls", type=int, default=8)
    parser.add_argument("--trace", help="Append JSONL tool calls/results to a workspace-relative file")
    parser.add_argument("--quiet", action="store_true", help="Hide progress messages on stderr")
    parser.add_argument("--show-config", action="store_true", help="Validate and print model settings without calling a model")
    parser.add_argument('--enable-magnus', action='store_true', help='Expose Magnus tools')
    parser.add_argument('--allow-simulation', action='store_true', help='Allow reviewed input submission')
    parser.add_argument('--validation-report', help='Operator PASS report, relative to workspace')
    args = parser.parse_args()
    if args.show_config:
        try:
            print(json.dumps(ModelConfig.from_env().summary(), indent=2))
        except ValueError as exc:
            parser.error(str(exc))
        return 0
    if args.max_calls < 1:
        parser.error("--max-calls must be positive")
    if bool(args.task) == bool(args.task_file):
        parser.error("Provide exactly one task or --task-file")
    if args.allow_simulation and (not args.enable_magnus or not args.validation_report):
        parser.error('--allow-simulation requires --enable-magnus and --validation-report')
    try:
        result = asyncio.run(run_task(args.task, args.workspace, args.max_calls, args.trace,
                                     progress=not args.quiet, enable_magnus=args.enable_magnus,
                                     allow_simulation=args.allow_simulation,
                                     validation_report=args.validation_report,
                                     task_file=args.task_file))
    except (Exception, KeyboardInterrupt) as exc:
        error = getattr(exc, "run_error", None)
        if error:
            print(f"Agent failed [{error['category']}/{error['type']}]: {error['message']}", file=sys.stderr)
        else:
            print(f"Agent failed [{type(exc).__name__}]: {diagnostic_message(exc)}", file=sys.stderr)
            print("Run record unavailable: workspace or record initialization failed.", file=sys.stderr)
        for note in getattr(exc, '__notes__', []):
            print(diagnostic_message(note), file=sys.stderr)
        if getattr(exc, "run_record_path", None):
            print(f"Run record: {exc.run_record_path}", file=sys.stderr)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1
    print(result.response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
