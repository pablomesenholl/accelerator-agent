"""Execute parser-only OPALX validation for the opalx-validation blueprint."""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import traceback
from pathlib import Path

from run_opalx_simulation import (
    _download_simulation,
    _get_simulation_root,
    _resolve_input_file,
    _write_result,
)


SUCCESS_MESSAGE = "Syntax validation succeeded (simulation commands skipped)."
TIMEOUT_SECONDS = 60


def _result(input_file: str) -> dict:
    """The status describes native syntax validation, not physical validity."""
    return {
        "success": False,
        "status": "INCONCLUSIVE",
        "mode": "parse-only",
        "input_file": input_file,
        "input_digest": None,
        "command": None,
        "opalx_version": None,
        "opalx_revision": None,
        "returncode": None,
        "diagnostics": "",
        "message": "OPALX syntax validation did not complete.",
    }


def _input_digest(root: Path, input_file: str) -> str:
    """SHA-256 of the selected input path and sorted bundle file hashes."""
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            files.append([path.relative_to(root).as_posix(), digest])
    return hashlib.sha256(json.dumps([input_file, files]).encode()).hexdigest()


def _status(returncode: int | None, output: str) -> str:
    # Statement-reading errors are rethrown as user errors by Main.cpp.
    parser_sources = ("OpalParser::", "TrackParser::", "IfStatement", "WhileStatement",
                      "CompoundStatement")
    parser_error = "*** Parse error detected by function" in output or any(
        f'*** User error detected by function "{source}' in output
        for source in parser_sources
    )
    succeeded = SUCCESS_MESSAGE in output.splitlines()
    if returncode == 0 and succeeded and not parser_error:
        return "PASS"
    if returncode is not None and returncode > 0 and parser_error and not succeeded:
        return "FAIL"
    return "INCONCLUSIVE"


def _run_opalx(simulation_root: Path, input_path: Path) -> dict:
    relative_input = input_path.relative_to(simulation_root)
    command = ["opalx", "--parse-only", "--input", str(relative_input), "--info", "2"]
    result = _result(str(relative_input))
    result.update(command=command, input_digest=_input_digest(simulation_root, str(relative_input)))
    print(f"OPALX parser-only command: {command}", flush=True)
    try:
        process = subprocess.run(
            command,
            cwd=simulation_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        result.update(returncode=process.returncode, diagnostics=process.stdout)
        result["status"] = _status(process.returncode, process.stdout)
        result["success"] = result["status"] == "PASS"
        result["message"] = (
            "OPALX syntax validation succeeded."
            if result["success"] else "OPALX reported an input syntax error."
            if result["status"] == "FAIL" else "OPALX syntax validation could not be established."
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        result["diagnostics"] = output.decode(errors="replace") if isinstance(output, bytes) else output
        result["message"] = f"OPALX parser-only validation timed out after {TIMEOUT_SECONDS} seconds."
    except OSError as error:
        result.update(message="OPALX parser-only process could not start.", diagnostics=str(error))

    output = result["diagnostics"]
    print(output, end="", flush=True)
    version = re.search(r"\bOPALX\b[^\n]*\bVersion\s+(\S+)", output)
    revision = re.search(r"\bgit rev\.\s*([0-9a-fA-F]{7,40})\b", output)
    result["opalx_version"] = version.group(1) if version else None
    result["opalx_revision"] = revision.group(1) if revision else None
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate OPALX syntax without simulation.")
    parser.add_argument("--input_secret", required=True, help="Magnus input FileSecret.")
    parser.add_argument("--input_file", required=True, help="Input path inside the bundle.")
    args = parser.parse_args()
    result = _result(args.input_file)

    try:
        with tempfile.TemporaryDirectory(prefix=".opalx_validation_", dir=Path.cwd()) as work:
            received_path = _download_simulation(args.input_secret, Path(work) / "input")
            simulation_root = _get_simulation_root(received_path)
            input_path = _resolve_input_file(simulation_root, args.input_file, received_path)
            result = _run_opalx(simulation_root, input_path)
    except Exception as error:
        traceback.print_exc()
        result.update(
            success=False,
            status="INCONCLUSIVE",
            message="OPALX validation runner failed.",
            diagnostics=f"{result['diagnostics']}\n{type(error).__name__}: {error}".lstrip("\n"),
        )

    _write_result(result)


if __name__ == "__main__":
    main()
