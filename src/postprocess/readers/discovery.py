"""Inventory local run files without opening diagnostics or inferring success."""

from os.path import abspath
from pathlib import Path
from typing import Literal

from ..models import RunFiles


OutputKind = Literal["statistics", "snapshots", "timings"]


class AmbiguousOutputError(ValueError):
    """More than one candidate exists and the caller must select a file."""


def _raise_walk_error(error: OSError) -> None:
    raise error


def discover_run(
    root: str | Path,
    *,
    derived_directories: tuple[str, ...] = ("analysis", "plots"),
) -> RunFiles:
    """Recursively inventory a directory, returning sorted root-relative paths.

    Classification uses names only, not contents. .stat and .h5/.hdf5 files are
    candidates for future readers, not confirmed compatible diagnostics. .in
    files are inputs and timing.dat is execution metadata. Other formats,
    including JSON and auxiliary .dat/.sdds files, remain unhandled.

    Files below directory components named in derived_directories are derived
    artifacts, even if their extensions resemble simulation outputs. Names are
    case-sensitive for directories; extensions and timing.dat are case-insensitive.
    Pass () to disable this convention or supply project-specific names.

    Symlinks are inventoried as unhandled and never traversed. Filesystem errors
    propagate rather than producing an apparently complete, partial inventory.
    No outputs are required; an empty directory is a valid inventory.
    """
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"Run root is not a directory: {root}")

    inventory = RunFiles(root=root)
    paths = []
    for directory, _, filenames in root.walk(on_error=_raise_walk_error):
        paths.extend(directory / name for name in filenames)

    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if path.is_symlink():
            inventory.unhandled.append(relative)
        elif any(part in derived_directories for part in relative.parts[:-1]):
            inventory.derived.append(relative)
        elif path.suffix.lower() == ".in":
            inventory.inputs.append(relative)
        elif path.suffix.lower() == ".stat":
            inventory.statistics.append(relative)
        elif path.suffix.lower() in (".h5", ".hdf5"):
            inventory.snapshots.append(relative)
        elif path.name.lower() == "timing.dat":
            inventory.timings.append(relative)
        else:
            inventory.unhandled.append(relative)
    return inventory


def select_file(
    inventory: RunFiles,
    kind: OutputKind,
    path: str | Path | None = None,
) -> Path | None:
    """Select a root-relative candidate; never pair files by basename implicitly.

    Without path, return the sole candidate or None if absent; multiple files
    raise AmbiguousOutputError listing the choices. An explicit path must name
    an inventoried candidate of the requested kind. It can be absolute inside
    the run root or relative to that root. This selects from the inventory; it
    does not recheck file existence or validate file contents.
    """
    if kind not in ("statistics", "snapshots", "timings"):
        raise ValueError(f"Unsupported output kind: {kind!r}")
    candidates = getattr(inventory, kind)
    if path is not None:
        requested = Path(path)
        root = inventory.root.resolve()
        absolute = Path(abspath(root / requested))
        if not absolute.is_relative_to(root) or not absolute.resolve().is_relative_to(root):
            raise ValueError(f"Selected file is outside the run root: {path}")
        relative = absolute.relative_to(root)
        if relative not in candidates:
            raise ValueError(f"Not an inventoried {kind} candidate: {path}")
        return relative
    if len(candidates) > 1:
        choices = ", ".join(p.as_posix() for p in candidates)
        raise AmbiguousOutputError(f"Multiple {kind} candidates; select a path: {choices}")
    return candidates[0] if candidates else None
