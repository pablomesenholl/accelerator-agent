"""Numerical postprocessing of local OPALX results."""

from .analysis import analyze_snapshot
from .validation import (
    compare_diagnostics, validate_analysis, validate_run_files,
    validate_snapshot, validate_statistics, validate_timing,
)

__all__ = [
    "analyze_snapshot", "compare_diagnostics", "validate_analysis",
    "validate_run_files", "validate_snapshot", "validate_statistics", "validate_timing",
]
