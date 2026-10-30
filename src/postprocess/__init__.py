"""Numerical postprocessing of local OPALX results."""

from .analysis import analyze_snapshot
from .export import results_to_dataframe, to_dataframe, to_summary, write_json, write_statistics_csv
from .readers import (
    discover_run, list_snapshots, read_closed_orbit, read_snapshot, read_stat,
    read_timing, select_file,
)
from .validation import (
    compare_diagnostics, validate_analysis, validate_run_files,
    validate_snapshot, validate_statistics, validate_timing,
    validate_closed_orbit,
)

__all__ = [
    "analyze_snapshot", "compare_diagnostics", "validate_analysis",
    "validate_run_files", "validate_snapshot", "validate_statistics", "validate_timing",
    "discover_run", "select_file", "read_stat", "list_snapshots", "read_snapshot", "read_timing",
    "to_summary", "to_dataframe", "results_to_dataframe", "write_json", "write_statistics_csv",
    "read_closed_orbit", "validate_closed_orbit",
]
