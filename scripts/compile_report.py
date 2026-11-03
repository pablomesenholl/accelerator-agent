"""Compile existing report sources with the project's installed LaTeX toolchain."""

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from setup_latex import CONFIG, INSTALL, sha256, verify_bundle


def compile_report(source, outdir, offline=False):
    source = Path(source).resolve(strict=True)
    outdir = Path(outdir).resolve()
    if source.suffix != ".tex":
        raise ValueError("Report source must be a .tex file")
    executable = INSTALL / "tectonic"
    stamp = json.loads((INSTALL / "installed.json").read_text())
    if stamp["lock_sha256"] != sha256(CONFIG) or stamp["executable_sha256"] != sha256(executable):
        raise ValueError("Toolchain differs from the lock; reinstall with scripts/setup_latex.py")
    lock = json.loads(CONFIG.read_text())
    if not offline:
        verify_bundle(lock["bundle"])
    command = [str(executable), "--bundle", lock["bundle"]["url"],
               "--untrusted", "--keep-logs", "--keep-intermediates", "--print",
               "--outdir", str(outdir), str(source)]
    if offline:
        command.append("--only-cached")
    # A fresh build directory also prevents stale PDFs from appearing successful.
    outdir.mkdir(parents=True, exist_ok=False)
    record = {
        "source": str(source), "source_sha256": sha256(source),
        "command": command, "cwd": str(source.parent),
        "toolchain": lock, "installation": stamp, "offline": offline,
        "started_utc": datetime.now(timezone.utc).isoformat(), "status": "failed",
    }
    try:
        # Keep fetched resources and generated format caches inside the project.
        environment = dict(os.environ, XDG_CACHE_HOME=str(INSTALL / "cache"))
        with (outdir / "compile.log").open("w") as log:
            result = subprocess.run(command, cwd=source.parent, env=environment,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=600)
        record["returncode"] = result.returncode
        pdf = outdir / source.with_suffix(".pdf").name
        if result.returncode != 0 or not pdf.is_file():
            raise ValueError(f"Compilation failed; see {outdir / 'compile.log'}")
        record["status"] = "completed"
        record["pdf"] = str(pdf)
        record["pdf_sha256"] = sha256(pdf)
        return pdf
    except Exception as error:
        record["error"] = str(error)
        raise
    finally:
        (outdir / "build.json").write_text(json.dumps(record, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--outdir", type=Path, required=True, help="New build directory (must not exist)")
    parser.add_argument("--offline", action="store_true", help="Use only previously cached TeX resources")
    args = parser.parse_args()
    try:
        print(compile_report(args.source, args.outdir, args.offline))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\nIf the compiler is missing, run .venv/bin/python scripts/setup_latex.py\n")


if __name__ == "__main__":
    main()
