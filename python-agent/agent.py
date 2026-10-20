"""Minimal standalone ADK agent and single-task CLI."""
import argparse
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
import sys
import time

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.agents.run_config import RunConfig
from google.genai import types

from model_config import create_model
from tools.file_tools import WorkspaceFiles
from tools.skill_tools import SkillLibrary


@dataclass
class TaskResult:
    response: str = ""
    tool_calls: list[str] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    tool_requests: list[dict] = field(default_factory=list)


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
                                ("skill", "document", "path", "query", "start_line", "line_count")
                                if key in args)
            self.show(f"Calling {data['name']}({details})")
        elif kind == "tool_result":
            result = data["response"]
            if "error" in result:
                self.show(f"FAILED {data['name']}: {self.short(result['error'])}")
                return
            details = []
            for key in ("skill", "document", "written", "edited"):
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
            suffix = f" ({'; '.join(details)})" if details else ""
            self.show(f"OK {data['name']}{suffix}")
        elif kind == "final":
            self.show("Agent finished.")
        elif kind == "error":
            self.show(f"Agent stopped: {self.short(data['message'])}")


async def run_task(task: str, workspace: Path, max_calls: int = 8,
                   trace: str | None = None, progress: bool = True) -> TaskResult:
    display = _Progress(progress)
    library = SkillLibrary()
    files = WorkspaceFiles(workspace, read_only_roots=(library.root,))
    trace_file = files._path(trace) if trace else None
    if trace_file:
        trace_file.parent.mkdir(parents=True, exist_ok=True)

    def record(kind: str, data: dict):
        display.record(kind, data)
        if trace_file:
            with trace_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event": kind, **data}, ensure_ascii=False) + "\n")

    agent = LlmAgent(
        name="accelerator_agent",
        model=create_model(),
        instruction=(Path(__file__).parent / "prompts" / "sytem.md").read_text(),
        tools=[files.read_file, files.write_file, files.edit_file, files.list_files,
               library.list_skills, library.load_skill, library.read_skill_document],
        before_model_callback=display.before_model if progress else None,
        after_model_callback=display.after_model if progress else None,
    )
    runner = InMemoryRunner(agent=agent, app_name="accelerator_agent")
    result = TaskResult()
    heartbeat = None
    try:
        record("start", {"task": task, "model": str(agent.model.model), "max_calls": max_calls})
        display.show(f"Workspace: {files.root}")
        if progress:
            heartbeat = asyncio.create_task(display.heartbeat())
        session = await runner.session_service.create_session(
            app_name="accelerator_agent", user_id="local"
        )
        async for event in runner.run_async(
            user_id="local", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=task)]),
            run_config=RunConfig(max_llm_calls=max_calls),
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
        if not result.response:
            raise RuntimeError("Model returned no final text response")
        record("final", {"response": result.response})
        return result
    except BaseException as exc:
        record("error", {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        await runner.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", help="Natural-language task (quote as one argument)")
    parser.add_argument("--task-file", type=Path, help="Read a UTF-8 task supplied by the operator")
    parser.add_argument("--workspace", type=Path, default=Path("output/python-agent"))
    parser.add_argument("--max-calls", type=int, default=8)
    parser.add_argument("--trace", help="Append JSONL tool calls/results to a workspace-relative file")
    parser.add_argument("--quiet", action="store_true", help="Hide progress messages on stderr")
    args = parser.parse_args()
    if args.max_calls < 1:
        parser.error("--max-calls must be positive")
    if bool(args.task) == bool(args.task_file):
        parser.error("Provide exactly one task or --task-file")
    try:
        task = args.task_file.read_text(encoding="utf-8") if args.task_file else args.task
        result = asyncio.run(run_task(task, args.workspace, args.max_calls, args.trace,
                                     progress=not args.quiet))
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Agent failed: {exc}", file=sys.stderr)
        return 1
    print(result.response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
