"""Lossless text access to optional OPALX execution timing diagnostics."""

from pathlib import Path

from ..models import SourceMetadata, TimingData


def read_timing(path: str | Path) -> TimingData:
    """Retain UTF-8 timing text verbatim, without inferring units or success.

    Timing tables are execution metadata, not beam observables. Multiple table
    sections and repeated timer labels make a flattened numerical table lossy;
    structured parsing is deferred until the output format is established.
    Missing files raise FileNotFoundError; callers may use discovery to decide
    whether this optional diagnostic exists.
    """
    path = Path(path).resolve()
    return TimingData(source=SourceMetadata(path), text=path.read_bytes().decode("utf-8"))
