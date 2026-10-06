# scripts/run_opalx_simulation.py
# Executed by Magnus blueprint `opalx-simulation`.

import argparse
import json
import os
import shlex
import shutil
import subprocess
import traceback
from pathlib import Path

import magnus


RUN_DIR_NAME = ".opalx_run"


def _download_simulation(file_secret: str, staging_dir: Path) -> Path:
    """
    Download the simulation FileSecret while preserving its original name.

    The secret may represent either:
      - a single file, or
      - a directory containing the OPALX input and auxiliary files.

    magnus.download_file() automatically restores directory secrets.
    """
    staging_dir.mkdir(parents=True, exist_ok=False)

    previous_cwd = Path.cwd()

    try:
        os.chdir(staging_dir)

        # No target_path is supplied deliberately:
        # Magnus therefore restores the original file/directory name.
        received_path = magnus.download_file(file_secret)

        received_path = Path(received_path).resolve()

    finally:
        os.chdir(previous_cwd)

    if not received_path.exists():
        raise RuntimeError(
            f"Downloaded simulation path does not exist: {received_path}"
        )

    return received_path


def _get_simulation_root(received_path: Path) -> Path:
    """
    Determine the directory from which OPALX should be launched.

    Directory upload:
        received_path = .../my_simulation/
        simulation_root = .../my_simulation/

    Single-file upload:
        received_path = .../fodo.in
        simulation_root = parent directory
    """
    if received_path.is_dir():
        return received_path.resolve()

    if received_path.is_file():
        return received_path.parent.resolve()

    raise RuntimeError(
        f"Downloaded simulation is neither a file nor a directory: "
        f"{received_path}"
    )


def _resolve_input_file(
    simulation_root: Path,
    input_file: str,
    received_path: Path,
) -> Path:
    """
    Resolve and validate the OPALX input file.

    The input path must remain inside the simulation directory.
    """
    relative_input = Path(input_file)

    if relative_input.is_absolute():
        raise ValueError(
            "input_file must be a relative path inside the simulation bundle."
        )

    root = simulation_root.resolve()
    candidate = (root / relative_input).resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError(
            f"input_file escapes the simulation directory: {input_file}"
        )

    if not candidate.is_file():
        raise FileNotFoundError(
            f"OPALX input file not found: {input_file}"
        )

    # For a single-file upload, input_file should identify that uploaded file.
    if received_path.is_file():
        if candidate != received_path.resolve():
            raise ValueError(
                "For a single-file simulation upload, input_file must match "
                f"the uploaded file name '{received_path.name}'."
            )

    return candidate


def _run_opalx(
    simulation_root: Path,
    input_path: Path,
) -> dict:
    """
    Run OPALX and return a small execution summary.

    stdout/stderr are intentionally inherited so they appear directly
    in the Magnus job logs.
    """
    relative_input = input_path.relative_to(simulation_root)

    command = [
        "opalx",
        str(relative_input),
        "--info",
        "2",
    ]

    print("================ OPALX Simulation ================")
    print(f"Working directory: {simulation_root}")
    print(f"Input file:        {relative_input}")
    print(f"Command:           {' '.join(command)}")
    print("==================================================")
    print()

    process_result = subprocess.run(
        command,
        cwd=simulation_root,
        stdin=subprocess.DEVNULL,
    )

    success = process_result.returncode == 0

    if success:
        message = "OPALX simulation completed successfully."
    else:
        message = (
            "OPALX simulation failed with "
            f"return code {process_result.returncode}."
        )

    return {
        "success": success,
        "message": message,
        "returncode": process_result.returncode,
        "input_file": str(relative_input),
    }


def _publish_output(
    simulation_root: Path,
    target_path: str,
) -> str:
    """
    Upload the complete simulation directory and configure Magnus
    to download it after the job.
    """
    file_secret = magnus.custody_file(str(simulation_root))

    action_path = os.environ.get("MAGNUS_ACTION")
    if action_path is None:
        raise RuntimeError(
            "Environment variable MAGNUS_ACTION is not set."
        )

    # Quote values because MAGNUS_ACTION is interpreted as a command.
    action = (
        f"magnus receive {shlex.quote(file_secret)} "
        f"--output {shlex.quote(target_path)}"
    )

    Path(action_path).write_text(
        action,
        encoding="utf-8",
    )

    return file_secret


def _write_result(result: dict) -> None:
    """
    Write the structured result consumed by Magnus.
    """
    result_path = os.environ.get("MAGNUS_RESULT")

    if result_path is None:
        raise RuntimeError(
            "Environment variable MAGNUS_RESULT is not set."
        )

    Path(result_path).write_text(
        json.dumps(result, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run an OPALX simulation inside a Magnus job."
    )

    parser.add_argument(
        "--input_secret",
        type=str,
        required=True,
        help="Magnus FileSecret containing the OPALX simulation input.",
    )

    parser.add_argument(
        "--input_file",
        type=str,
        required=True,
        help="Relative path of the OPALX input file inside the simulation bundle.",
    )

    parser.add_argument(
        "--target_path",
        type=str,
        required=True,
        help="Client-side output path used by Magnus when downloading results.",
    )

    args = parser.parse_args()

    result = {
        "success": False,
        "message": "OPALX simulation did not complete.",
    }

    simulation_root = None
    simulation_prepared = False

    try:
        run_dir = Path(RUN_DIR_NAME).resolve()

        # Jobs are normally isolated, but removing a stale runner directory
        # makes local/debug execution deterministic as well.
        if run_dir.exists():
            shutil.rmtree(run_dir)

        staging_dir = run_dir / "input"

        received_path = _download_simulation(
            file_secret=args.input_secret,
            staging_dir=staging_dir,
        )

        print(f"Downloaded simulation input to: {received_path}")

        simulation_root = _get_simulation_root(received_path)

        input_path = _resolve_input_file(
            simulation_root=simulation_root,
            input_file=args.input_file,
            received_path=received_path,
        )

        simulation_prepared = True

        result = _run_opalx(
            simulation_root=simulation_root,
            input_path=input_path,
        )

    except Exception as error:
        traceback.print_exc()

        result = {
            "success": False,
            "message": f"OPALX simulation runner crashed: {error}",
            "traceback": traceback.format_exc(),
        }

    # Preserve the simulation directory even when OPALX itself fails.
    if (
        simulation_prepared
        and simulation_root is not None
        and simulation_root.exists()
    ):
        try:
            file_secret = _publish_output(
                simulation_root=simulation_root,
                target_path=args.target_path,
            )

            result["output_secret"] = file_secret
            result["output_path"] = args.target_path

        except Exception as error:
            traceback.print_exc()

            result["output_upload_error"] = str(error)

            if result.get("success"):
                result["success"] = False
                result["message"] = (
                    "OPALX simulation succeeded, but uploading the "
                    "simulation results failed."
                )

    print()
    print("================ OPALX Result =================")
    print(json.dumps(result, ensure_ascii=False, indent=4))
    print("===============================================")

    _write_result(result)


if __name__ == "__main__":
    main()