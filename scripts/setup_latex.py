"""Install the locked LaTeX toolchain locally; no Python dependencies required."""

import hashlib
import gzip
import json
import platform
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(__file__).with_name("latex-toolchain.json")
INSTALL = ROOT / ".tools" / "tectonic"


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch_locked(spec, destination):
    subprocess.run(
        ["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "3",
         "--connect-timeout", "15", "--max-time", "120",
         "--output", str(destination), spec["url"]], check=True,
    )
    if sha256(destination) != spec["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {spec['url']}")


def verify_bundle(spec):
    """Check the versioned bundle's index and Tectonic SHA256SUM identity."""
    with tempfile.TemporaryDirectory(dir=INSTALL.parent) as temporary:
        index = Path(temporary) / "index.gz"
        fetch_locked({"url": spec["url"] + ".index.gz", "sha256": spec["index_sha256"]}, index)
        with gzip.open(index, "rt") as stream:
            entries = [line.split() for line in stream if line.startswith("SHA256SUM ")]
        if len(entries) != 1:
            raise ValueError("Bundle index must contain one SHA256SUM entry")
        _, offset, length = entries[0]
        offset, length = int(offset), int(length)
        identity = subprocess.check_output([
            "curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "60",
            "--range", f"{offset}-{offset + length - 1}", spec["url"],
        ], text=True).strip()
        if identity != spec["identity"]:
            raise ValueError("TeX bundle identity differs from the lock")


def install():
    lock = json.loads(CONFIG.read_text())
    host = f"{platform.system()}-{platform.machine()}"
    if host not in lock["platforms"]:
        raise ValueError(f"Unsupported platform {host}; add a verified release to {CONFIG}")
    if INSTALL.exists():
        raise ValueError(f"Installation already exists: {INSTALL}; preserve or move it before reinstalling")
    INSTALL.parent.mkdir(parents=True, exist_ok=True)
    verify_bundle(lock["bundle"])
    # Install atomically; interrupted downloads never look like a ready toolchain.
    with tempfile.TemporaryDirectory(dir=INSTALL.parent) as temporary:
        work = Path(temporary)
        ready = work / "ready"
        ready.mkdir()
        archive = work / "compiler.tar.gz"
        fetch_locked(lock["platforms"][host], archive)
        with tarfile.open(archive) as tar:
            member = tar.getmember("tectonic")
            if not member.isfile():
                raise ValueError("Compiler archive does not contain a regular executable")
            with tar.extractfile(member) as source, (ready / "tectonic").open("wb") as target:
                shutil.copyfileobj(source, target)
        executable = ready / "tectonic"
        executable.chmod(0o755)
        version = subprocess.check_output([str(executable), "--version"], text=True).strip()
        if version != f"Tectonic {lock['version']}":
            raise ValueError(f"Unexpected compiler version: {version}")
        (ready / "installed.json").write_text(json.dumps({
            "lock_sha256": sha256(CONFIG), "executable_sha256": sha256(executable),
            "platform": host, "version": version,
        }, indent=2) + "\n")
        ready.rename(INSTALL)
    print(f"Installed {version} in {INSTALL}")


if __name__ == "__main__":
    try:
        install()
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        raise SystemExit(str(error))
