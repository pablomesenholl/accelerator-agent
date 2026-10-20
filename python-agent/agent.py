"""Minimal standalone ADK agent and single-task CLI."""
import argparse
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import sys

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.agents.run_config import RunConfig
from google.genai import types

from model_config import create_model
from tools.file_tools import WorkspaceFiles


@dataclass
class TaskResult:
    response: str = ""
    tool_calls: list[str] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)


async def run_task(task: str, workspace: Path, max_calls: int = 8) -> TaskResult:
    files = WorkspaceFiles(workspace)
    agent = LlmAgent(
        name="accelerator_agent",
        model=create_model(),
        instruction=(Path(__file__).parent / "prompts" / "sytem.md").read_text(),
        tools=[files.read_file, files.write_file, files.edit_file, files.list_files],
    )
    runner = InMemoryRunner(agent=agent, app_name="accelerator_agent")
    result = TaskResult()
    try:
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
            for response in event.get_function_responses():
                result.tool_results.append({"name": response.name, "response": response.response})
            if event.is_final_response() and event.content:
                result.response = "\n".join(
                    part.text for part in event.content.parts or []
                    if part.text and not part.thought
                )
        if not result.response:
            raise RuntimeError("Model returned no final text response")
        return result
    finally:
        await runner.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", help="Natural-language task (quote as one argument)")
    parser.add_argument("--workspace", type=Path, default=Path("output/python-agent"))
    parser.add_argument("--max-calls", type=int, default=8)
    args = parser.parse_args()
    if args.max_calls < 1:
        parser.error("--max-calls must be positive")
    try:
        result = asyncio.run(run_task(args.task, args.workspace, args.max_calls))
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Agent failed: {exc}", file=sys.stderr)
        return 1
    print(result.response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
