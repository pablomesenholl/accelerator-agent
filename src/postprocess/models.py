"""Contracts for local OPALX data and derived quantities.

Arrays retain source names and dtypes. No conversion or physics inference happens
here. Constructors check structure; physical checks belong in validation.py.
Arrays and metadata are mutable and shared without copying. No file handles are
retained. Type annotations document the API; they are not runtime validation.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray


NumericArray = NDArray[np.number]


@dataclass
class FieldMetadata:
    """Original field metadata: None means unknown units, '1' dimensionless.

    Momentum normalization such as p/(mc) must remain explicit, not be labelled
    as a slope. Preserve original unit labels rather than silently converting.
    """

    unit: str | None = None
    description: str | None = None


@dataclass
class SourceMetadata:
    """Provenance and raw reader metadata, including original HDF5 attributes."""

    path: Path
    opalx_version: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass
class RunFiles:
    """Inventory with paths relative to root; multiple/absent outputs are valid.

    Unsupported formats belong in unhandled. Inventory alone makes no claim
    about simulation success. Inputs and derived artifacts are separate outputs
    of discovery, not simulation diagnostics.
    """

    root: Path
    statistics: list[Path] = field(default_factory=list)
    snapshots: list[Path] = field(default_factory=list)
    timings: list[Path] = field(default_factory=list)
    inputs: list[Path] = field(default_factory=list)
    derived: list[Path] = field(default_factory=list)
    unhandled: list[Path] = field(default_factory=list)


@dataclass
class TimingData:
    """Optional execution metadata, retaining timing.dat verbatim without parsing."""

    source: SourceMetadata
    text: str


def _check_columns(columns: dict[str, NumericArray]) -> None:
    """Require equally sized 1D real numeric arrays; allow empty/nonfinite data."""
    lengths = set()
    for name, array in columns.items():
        if not isinstance(array, np.ndarray):
            raise TypeError(f"Column {name!r} must be a NumPy array")
        if array.ndim != 1:
            raise ValueError(f"Column {name!r} must be one-dimensional")
        if array.dtype.kind not in "iuf":
            raise TypeError(f"Column {name!r} must contain real numeric data")
        lengths.add(len(array))
    if len(lengths) > 1:
        raise ValueError("Columns must have equal lengths")


@dataclass
class StatisticsTable:
    """SDDS columns without a fixed schema; s and t retain declared units.

    Header parameters belong in source.attributes. Missing fields metadata
    means unknown metadata, not dimensionless values.
    """

    columns: dict[str, NumericArray]
    source: SourceMetadata
    fields: dict[str, FieldMetadata] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check_columns(self.columns)

    @property
    def row_count(self) -> int:
        return len(next(iter(self.columns.values()))) if self.columns else 0


@dataclass
class ParticleSnapshot:
    """One materialized HDF5 dump, retaining optional particle datasets.

    step is the numeric dump ID, not necessarily the integration counter.
    Keep integration counters in source.attributes. s is path length in metres
    and time is seconds: readers convert explicitly and retain raw metadata.
    Neither is inferred from particle z. Frames and momentum conventions remain
    unknown until verified. source.attributes holds snapshot attributes; file
    attributes should be retained under its 'file_attributes' key.
    """

    step: int
    group_name: str
    columns: dict[str, NumericArray]
    source: SourceMetadata
    fields: dict[str, FieldMetadata] = field(default_factory=dict)
    s: float | None = None
    time: float | None = None
    coordinate_frame: str | None = None
    momentum_convention: str | None = None

    def __post_init__(self) -> None:
        _check_columns(self.columns)

    @property
    def particle_count(self) -> int:
        return len(next(iter(self.columns.values()))) if self.columns else 0


@dataclass
class ValidationIssue:
    """Machine-readable diagnostic with optional file, snapshot and field context."""

    code: str
    message: str
    severity: Literal["warning", "error"]
    source: Path | None = None
    step: int | None = None
    field_name: str | None = None


@dataclass
class ValidationReport:
    """Outcome relative to the checks performed, without repairing input data.

    is_valid means no error was found, not that all checks ran, that warnings
    are absent, or that simulation succeeded. Inspect checks and skipped too.
    """

    issues: list[ValidationIssue] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


@dataclass
class Quantity:
    """Calculated scalar or array, with unit and mathematical definition."""

    value: float | NumericArray
    unit: str | None
    definition: str


@dataclass
class CovarianceMatrix:
    """Centered population covariance (normalization N, rather than N - 1).

    Axis order is explicit; entry (i, j) has units units[i]*units[j]. Symmetry,
    finiteness and positive semidefiniteness belong to physical validation.
    """

    values: NumericArray
    coordinates: tuple[str, ...]
    units: tuple[str | None, ...]

    def __post_init__(self) -> None:
        n = len(self.coordinates)
        if not isinstance(self.values, np.ndarray):
            raise TypeError("Covariance values must be a NumPy array")
        if self.values.dtype.kind not in "iuf":
            raise TypeError("Covariance values must contain real numeric data")
        if self.values.shape != (n, n) or len(self.units) != n:
            raise ValueError("Covariance shape, coordinate order and units must agree")
        if len(set(self.coordinates)) != n:
            raise ValueError("Covariance coordinate names must be unique")


@dataclass
class AnalysisResult:
    """Calculated results, separate from OPALX's reported diagnostics.

    Failed observables are omitted and explained by issues. Zero emittance can
    be valid but cannot represent failure. partial means some requested values
    failed; failed means none could be computed. Assumptions describe weighting,
    frames and approximations. validate_analysis checks status consistency.
    """

    source: SourceMetadata
    status: Literal["success", "partial", "failed"]
    step: int | None = None
    quantities: dict[str, Quantity] = field(default_factory=dict)
    covariances: dict[str, CovarianceMatrix] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    # Known snapshot coordinates, retained for plotting without reinterpreting
    # raw reported attributes. None means unavailable; units are m and s.
    s: float | None = None
    time: float | None = None
