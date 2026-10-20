"""Minimal standalone ADK agent and single-task CLI."""
import argparse
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
import sys

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


async def run_task(task: str, workspace: Path, max_calls: int = 8,
                   trace: str | None = None) -> TaskResult:
    library = SkillLibrary()
    files = WorkspaceFiles(workspace, read_only_roots=(library.root,))
    trace_file = files._path(trace) if trace else None
    if trace_file:
        trace_file.parent.mkdir(parents=True, exist_ok=True)

    def record(kind: str, data: dict):
        if trace_file:
            with trace_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event": kind, **data}, ensure_ascii=False) + "\n")

    agent = LlmAgent(
        name="accelerator_agent",
        model=create_model(),
        instruction=(Path(__file__).parent / "prompts" / "sytem.md").read_text(),
        tools=[files.read_file, files.write_file, files.edit_file, files.list_files,
               library.list_skills, library.load_skill, library.read_skill_document],
    )
    runner = InMemoryRunner(agent=agent, app_name="accelerator_agent")
    result = TaskResult()
    try:
        record("start", {"task": task, "model": str(agent.model.model), "max_calls": max_calls})
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
        await runner.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", help="Natural-language task (quote as one argument)")
    parser.add_argument("--task-file", type=Path, help="Read a UTF-8 task supplied by the operator")
    parser.add_argument("--workspace", type=Path, default=Path("output/python-agent"))
    parser.add_argument("--max-calls", type=int, default=8)
    parser.add_argument("--trace", help="Append JSONL tool calls/results to a workspace-relative file")
    args = parser.parse_args()
    if args.max_calls < 1:
        parser.error("--max-calls must be positive")
    if bool(args.task) == bool(args.task_file):
        parser.error("Provide exactly one task or --task-file")
    try:
        task = args.task_file.read_text(encoding="utf-8") if args.task_file else args.task
        result = asyncio.run(run_task(task, args.workspace, args.max_calls, args.trace))
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Agent failed: {exc}", file=sys.stderr)
        return 1
    print(result.response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
