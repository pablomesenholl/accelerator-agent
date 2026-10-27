"""Nonmutating validation of local files, loaded data and beam calculations.

Parsing remains a reader responsibility. These checks also handle mutated model
arrays. Passing checks does not certify simulation success or physical accuracy.
"""

from pathlib import Path

import numpy as np

from .models import (
    AnalysisResult, CovarianceMatrix, ParticleSnapshot, RunFiles, StatisticsTable, TimingData,
    ValidationIssue, ValidationReport,
)


_AXES = ("x", "px", "y", "py", "z", "pz")
_LENGTH = {"m": 1., "cm": 1e-2, "mm": 1e-3}
_TIME = {"s": 1., "ns": 1e-9, "us": 1e-6, "ps": 1e-12}
_NORMALIZED = {"p/(mc)", "#beta#gamma"}


def _issue(report, source, code, message, field=None, severity="error", step=None):
    report.issues.append(ValidationIssue(code, message, severity, source, step, field))


def _unit(data, name):
    metadata = data.fields.get(name)
    return metadata.unit if metadata else None


def _normalized(snapshot, name):
    return snapshot.momentum_convention in (None, "p/(mc)") and (
        _unit(snapshot, name) in _NORMALIZED or
        (snapshot.momentum_convention == "p/(mc)" and _unit(snapshot, name) in (None, "1"))
    )


def _arrays(data, report, required):
    source, step = data.source.path, getattr(data, "step", None)
    valid, lengths = {}, set()
    for name in required:
        if name not in data.columns:
            _issue(report, source, "missing_field", "Required field is absent", name, step=step)
    for name, array in data.columns.items():
        if not isinstance(array, np.ndarray) or array.ndim != 1 or array.dtype.kind not in "iuf":
            _issue(report, source, "invalid_dimensions", "Expected a 1D real numeric array", name, step=step)
            continue
        lengths.add(len(array))
        if not len(array):
            _issue(report, source, "empty_data", "Array contains no records", name, step=step)
        elif not np.all(np.isfinite(array)):
            _issue(report, source, "nonfinite_data", "Array contains NaN or infinity", name, step=step)
        else:
            valid[name] = array
    if not data.columns:
        _issue(report, source, "empty_data", "No columns available", step=step)
    if len(lengths) > 1:
        _issue(report, source, "inconsistent_dimensions", "Column lengths disagree", step=step)
    report.checks.append("required fields, numeric dimensions, lengths and finiteness")
    return valid


def validate_run_files(files: RunFiles, *, required=("statistics", "snapshots")) -> ValidationReport:
    """Check inventoried paths; optional timing and unsupported artifacts may be absent.

    Multiple candidates warn and require explicit selection before loading.
    Presence is not parsing/physics validation. Paths must stay inside the root.
    """
    kinds = ("statistics", "snapshots", "timings")
    if any(kind not in kinds for kind in required):
        raise ValueError("Required categories must be statistics, snapshots or timings")
    report = ValidationReport()
    root = Path(files.root).resolve()
    if not root.is_dir():
        _issue(report, root, "missing_directory", "Run root is absent or not a directory")
    for kind in kinds:
        paths = getattr(files, kind)
        if not paths:
            if kind in required:
                _issue(report, root, "missing_output", f"No {kind} output was discovered", kind)
            else:
                report.skipped.append(f"Optional {kind} output is absent")
        if len(paths) > 1:
            _issue(report, root, "multiple_candidates", "Select a file explicitly before reading", kind, "warning")
        for relative in paths:
            relative = Path(relative)
            path = root / relative
            if relative.is_absolute() or not path.resolve().is_relative_to(root):
                _issue(report, root, "invalid_output_path", "Output path must stay relative to the run root", str(relative))
            elif not path.is_file() or path.is_symlink():
                _issue(report, path, "missing_output", "Expected a regular output file", kind)
            elif path.stat().st_size == 0:
                _issue(report, path, "empty_output", "Output file is empty", kind,
                       "warning" if kind == "timings" and kind not in required else "error")
    report.checks.append("required output categories and inventoried file existence/size")
    report.skipped.extend(f"Unsupported artifact: {path}" for path in files.unhandled)
    return report


def validate_statistics(table: StatisticsTable, *, required=("t", "s", "numParticles")) -> ValidationReport:
    """Check counts/ranges without assuming monotonic path length or conservation.

    Signed charge/centroids are valid. Repeated/decreasing times warn, allowing
    detection of concatenated restarts; records are never reordered or removed.
    """
    report = ValidationReport()
    arrays = _arrays(table, report, required)
    for name, values in arrays.items():
        if name == "numParticles":
            if np.any(values < 0) or np.any(values != np.floor(values)):
                _issue(report, table.source.path, "invalid_count", "Particle counts must be nonnegative integers", name)
            elif np.any(values == 0):
                _issue(report, table.source.path, "empty_population", "Some rows have zero particles", name, "warning")
        elif name.startswith(("rms_", "emit_")) or name in ("energy", "dE", "dt"):
            if np.any(values < 0):
                _issue(report, table.source.path, "negative_observable", "RMS, emittance, energy/spread and dt must be nonnegative", name)
        elif name in ("xpx", "ypy", "zpz") and np.any(np.abs(values) > 1 + 1e-12):
            _issue(report, table.source.path, "invalid_correlation", "Correlation lies outside [-1, 1]", name)
    if "t" in arrays and np.any(arrays["t"][1:] <= arrays["t"][:-1]):
        _issue(report, table.source.path, "nonmonotonic_time", "Times repeat or decrease; matching may be ambiguous", "t", "warning")
    for name, supported in (("t", _TIME), ("s", _LENGTH)):
        if name in arrays and _unit(table, name) not in supported:
            _issue(report, table.source.path, "unknown_unit", "Coordinate cannot be converted for matching", name, "warning")
    report.checks.append("statistics counts, physical ranges and coordinate metadata")
    return report


def validate_snapshot(snapshot: ParticleSnapshot, *, longitudinal_axis=None) -> ValidationReport:
    """Require six phase-space components and check all loaded particle arrays.

    Positive pz is required only for forward-z optics. Unknown units/conventions
    warn; no frame is inferred from reference-particle or rotation metadata.
    """
    if longitudinal_axis not in (None, "z"):
        raise ValueError("Only longitudinal_axis='z' or None is supported")
    report = ValidationReport()
    arrays = _arrays(snapshot, report, _AXES)
    source, step = snapshot.source.path, snapshot.step
    for name in ("x", "y", "z"):
        if name in arrays and _unit(snapshot, name) not in _LENGTH:
            _issue(report, source, "unknown_unit", "Position unit is unknown/unsupported for optics", name, "warning", step)
    for name in ("px", "py", "pz"):
        if name in arrays and not _normalized(snapshot, name):
            _issue(report, source, "unknown_convention", "Normalized momentum p/(mc) is not established", name, "warning", step)
    for name in ("s", "time"):
        value = getattr(snapshot, name)
        if value is None:
            report.skipped.append(f"Snapshot {name} coordinate unavailable for matching")
        elif not _finite_scalar(value):
            _issue(report, source, "invalid_coordinate", "Snapshot coordinate must be a finite scalar", name, step=step)
    if longitudinal_axis == "z" and "pz" in arrays and np.any(arrays["pz"] <= 0):
        _issue(report, source, "invalid_longitudinal_momentum", "Forward-z optics requires every pz > 0", "pz", step=step)
    if "id" in arrays:
        ids = arrays["id"]
        if ids.dtype.kind not in "iu":
            _issue(report, source, "invalid_ids", "Particle IDs must retain an integer dtype", "id", step=step)
        elif len(np.unique(ids)) != len(ids):
            _issue(report, source, "duplicate_ids", "Particle IDs repeat within this snapshot", "id", step=step)
    if "m" in arrays and np.any(arrays["m"] <= 0):
        _issue(report, source, "invalid_mass", "Particle mass must be positive", "m", step=step)
    if "sp" in arrays and len(np.unique(arrays["sp"])) > 1:
        _issue(report, source, "mixed_species", "Single-species optics requires selecting a species", "sp", "warning", step)
    if "q" not in arrays:
        _issue(report, source, "weights_unverified", "Equal macroparticle weights cannot be checked", "q", "warning", step)
    elif not np.allclose(arrays["q"], arrays["q"][0], rtol=1e-12, atol=0):
        _issue(report, source, "unequal_charges", "Equal macroparticle weighting differs from charge weighting", "q", "warning", step)
    report.checks.append("snapshot units, coordinates, IDs, species and weighting")
    return report


def validate_timing(timing: TimingData) -> ValidationReport:
    """Check optional text without inferring timing units or simulation success."""
    report = ValidationReport(checks=["timing text availability"])
    if not isinstance(timing.text, str):
        _issue(report, timing.source.path, "invalid_timing", "Timing metadata must be text")
    elif not timing.text.strip():
        _issue(report, timing.source.path, "empty_timing", "Optional timing text is empty", severity="warning")
    report.skipped.append("Timing numerical interpretation and simulation-success inference")
    return report


def _finite_scalar(value):
    array = np.asarray(value)
    return array.ndim == 0 and array.dtype.kind in "iuf" and bool(np.isfinite(array))


def _tolerances(rtol, atol):
    if not all(_finite_scalar(value) and value >= 0 for value in (rtol, atol)):
        raise ValueError("Tolerances must be finite nonnegative scalars")


def _matrix_issues(matrix, report, source, name, step, rtol):
    values = matrix.values
    n = len(matrix.coordinates)
    if (not isinstance(values, np.ndarray) or values.dtype.kind not in "iuf"
        or values.shape != (n, n) or not n or len(matrix.units) != n
        or len(set(matrix.coordinates)) != n):
        _issue(report, source, "invalid_covariance", "Matrix shape, real dtype, axes and units must agree", name, step=step)
        return False
    if not np.all(np.isfinite(values)):
        _issue(report, source, "nonfinite_covariance", "Covariance contains NaN or infinity", name, step=step)
        return False
    with np.errstate(over="ignore", invalid="ignore"):
        values = values.astype(np.float64)
    if not np.all(np.isfinite(values)):
        _issue(report, source, "invalid_covariance", "Covariance exceeds the float64 calculation range", name, step=step)
        return False
    diagonal = np.diag(values)
    if np.any(diagonal < 0):
        _issue(report, source, "negative_variance", "Covariance diagonal contains a negative variance", name, step=step)
        return False
    scales = np.sqrt(diagonal)
    zero = scales == 0
    if np.any(values[zero, :] != 0) or np.any(values[:, zero] != 0):
        _issue(report, source, "nonpositive_covariance", "Zero variance has a nonzero cross covariance", name, step=step)
        return False
    scales[zero] = 1
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        normalized = values / scales[:, None] / scales[None, :]
    if not np.all(np.isfinite(normalized)):
        _issue(report, source, "invalid_covariance", "Covariance cannot be scaled to finite correlation units", name, step=step)
        return False
    if not np.allclose(normalized, normalized.T, rtol=rtol, atol=rtol):
        _issue(report, source, "asymmetric_covariance", "Covariance is not symmetric in correlation units", name, step=step)
        return False
    try:
        minimum = np.linalg.eigvalsh((normalized + normalized.T) / 2).min()
    except np.linalg.LinAlgError:
        _issue(report, source, "covariance_check_failed", "Eigenvalue calculation failed", name, step=step)
        return False
    if minimum < -rtol * n:
        _issue(report, source, "nonpositive_covariance", "Covariance is not positive semidefinite", name, step=step)
        return False
    return True


def validate_analysis(result: AnalysisResult, *, longitudinal_axis=None, rtol=1e-8, atol=1e-12) -> ValidationReport:
    """Check completeness, ranges, covariance PSD, RMS/emittance and Twiss relations.

    Existing calculation issues are copied. Request the same longitudinal axis
    as calculation. Singular PSD matrices are valid. Determinant checks use
    correlation units to avoid cancellation and mixed-unit scaling artifacts.
    This validates internal consistency, not independent physical accuracy.
    """
    _tolerances(rtol, atol)
    if longitudinal_axis not in (None, "z"):
        raise ValueError("Only longitudinal_axis='z' or None is supported")
    report = ValidationReport(issues=list(result.issues))
    source, step = result.source.path, result.step

    for name in ("s", "time"):
        value = getattr(result, name)
        if value is not None and not _finite_scalar(value):
            _issue(report, source, "invalid_coordinate", "Result coordinate must be a finite scalar or None", name, step=step)

    def problem(code, message, name):
        _issue(report, source, code, message, name, step=step)

    required = [f"{prefix}_{axis}" for prefix in ("centroid", "rms") for axis in _AXES]
    required += ["num_particles", "emit_nx", "emit_ny"]
    if longitudinal_axis == "z":
        required += [f"{prefix}_{axis}" for prefix in ("emit", "alpha", "beta", "gamma") for axis in ("x", "y")]
        required += [f"{prefix}_{axis}_prime" for prefix in ("centroid", "rms") for axis in ("x", "y")]
    for name in required:
        if name not in result.quantities:
            problem("missing_quantity", "Requested observable is absent", name)
    scalars = {}
    for name, quantity in result.quantities.items():
        if not _finite_scalar(quantity.value):
            problem("invalid_quantity", "Beam observables must be finite real scalars", name)
            continue
        value = float(quantity.value)
        scalars[name] = value
        if name.startswith(("rms_", "emit_", "beta_", "gamma_")) and value < 0:
            problem("negative_observable", "RMS, emittance, beta and gamma cannot be negative", name)
        if name == "num_particles" and (value <= 0 or not value.is_integer() or quantity.unit != "1"):
            problem("invalid_count", "Calculated count must be a positive integer with unit 1", name)
    original_errors = any(issue.severity == "error" for issue in result.issues)
    if (result.status not in ("success", "partial", "failed")
        or (result.status == "success" and (original_errors or not result.quantities))
        or (result.status == "partial" and (not original_errors or not result.quantities))
        or (result.status == "failed" and (not original_errors or bool(result.quantities)))):
        problem("inconsistent_status", "Status disagrees with calculation issues and available quantities", "status")
    required_matrices = ["phase_space", "x_normalized", "y_normalized"]
    if longitudinal_axis == "z":
        required_matrices += ["x_geometric", "y_geometric"]
    for name in required_matrices:
        if name not in result.covariances:
            problem("missing_covariance", "Requested covariance is absent", name)
    valid_matrices = {}
    for name, matrix in result.covariances.items():
        if _matrix_issues(matrix, report, source, name, step, rtol):
            matrix = CovarianceMatrix(matrix.values.astype(np.float64), matrix.coordinates, matrix.units)
            valid_matrices[name] = matrix
            for i, axis in enumerate(matrix.coordinates):
                key = f"rms_{axis}"
                if key in scalars:
                    if result.quantities[key].unit != matrix.units[i]:
                        problem("inconsistent_units", "RMS unit differs from covariance axis unit", key)
                    elif not np.isclose(scalars[key], np.sqrt(matrix.values[i, i]), rtol=rtol, atol=atol):
                        problem("inconsistent_rms", "RMS disagrees with covariance diagonal", key)
    if "phase_space" in valid_matrices and valid_matrices["phase_space"].coordinates != _AXES:
        problem("inconsistent_axes", "Full covariance must use x, px, y, py, z, pz order", "phase_space")
    for plane in ("x", "y"):
        for kind, emit_name, second, expected_units in (
            ("normalized", f"emit_n{plane}", "p" + plane, ("m", "p/(mc)")),
            ("geometric", f"emit_{plane}", plane + "_prime", ("m", "1")),
        ):
            name = f"{plane}_{kind}"
            matrix = valid_matrices.get(name)
            if matrix is None or emit_name not in scalars:
                continue
            if matrix.coordinates != (plane, second) or matrix.units != expected_units:
                problem("inconsistent_axes", "Projected covariance axes/units disagree with the estimator", name)
                continue
            full = valid_matrices.get("phase_space")
            if kind == "normalized" and full is not None and full.coordinates == _AXES:
                indices = [_AXES.index(plane), _AXES.index(second)]
                block = full.values[np.ix_(indices, indices)]
                if tuple(full.units[i] for i in indices) != matrix.units:
                    problem("inconsistent_units", "Projected and full covariance units disagree", name)
                else:
                    scales = np.sqrt(np.diag(block))
                    scales[scales == 0] = 1
                    if not np.allclose(block / scales[:, None] / scales[None, :],
                                       matrix.values / scales[:, None] / scales[None, :],
                                       rtol=rtol, atol=rtol):
                        problem("inconsistent_covariance", "Projected covariance differs from the full covariance block", name)
            if result.quantities[emit_name].unit != "m":
                problem("inconsistent_units", "Emittance unit must be m (angles dimensionless)", emit_name)
            a, b, c = matrix.values[0, 0], matrix.values[0, 1], matrix.values[1, 1]
            scale = np.sqrt(a) * np.sqrt(c)
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                ratio = scalars[emit_name] / scale if scale else 0.
                determinant = 1 - (b / scale)**2 if scale else 0.
                consistent = np.isclose(ratio * ratio, max(determinant, 0), rtol=rtol, atol=rtol)
            if ((not scale and scalars[emit_name] != 0) or not np.isfinite(ratio) or not consistent):
                problem("inconsistent_emittance", "Emittance disagrees with scaled covariance determinant", emit_name)
            if kind != "geometric":
                continue
            twiss = [f"{prefix}_{plane}" for prefix in ("alpha", "beta", "gamma")]
            if any(key in result.quantities for key in twiss) and scalars[emit_name] <= 0:
                problem("undefined_twiss", "Twiss cannot be supplied for zero emittance", plane)
            elif all(key in scalars for key in twiss) and scalars[emit_name] > 0:
                epsilon = scalars[emit_name]
                with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                    expected = [-b / epsilon, a / epsilon, c / epsilon]
                for key, value, unit in zip(twiss, expected, ("1", "m", "1/m")):
                    if result.quantities[key].unit != unit:
                        problem("inconsistent_units", "Twiss unit disagrees with its definition", key)
                    elif not np.isclose(scalars[key], value, rtol=rtol, atol=atol):
                        problem("inconsistent_twiss", "Twiss disagrees with covariance/emittance", key)
                alpha, beta, gamma = (np.longdouble(scalars[key]) for key in twiss)
                residual = beta * gamma - alpha * alpha - 1
                if abs(residual) > rtol * max(1, abs(beta * gamma), alpha * alpha):
                    problem("inconsistent_twiss", "Scaled beta*gamma-alpha^2 identity failed", plane)
    report.checks.append("calculation issues/status, completeness, ranges, covariance PSD and moment/optics consistency")
    return report


def compare_diagnostics(
    snapshot: ParticleSnapshot, result: AnalysisResult,
    statistics: StatisticsTable | None = None, *, frame_confirmed=False,
    rtol=1e-8, atol=1e-12, time_atol=1e-15, path_atol=1e-6,
) -> ValidationReport:
    """Compare same-frame reported summaries with a calculation of that dump.

    The caller must verify compatible axes and equal-population conventions.
    HDF5 values are from the supplied dump. Statistics require exactly one row
    within time_atol seconds, and path agreement within path_atol metres when
    both paths are available. No nearest-row fallback, interpolation or implicit
    frame inference occurs. Missing/unknown units yield explicit skips/warnings.
    atol is expressed in each compared observable's canonical units; rtol is
    relative. No reported geometric emittance comparison is made: estimators
    differ. Existing calculation errors are checked by validate_analysis.
    """
    _tolerances(rtol, atol)
    _tolerances(time_atol, path_atol)
    report = ValidationReport()
    source, step = snapshot.source.path, snapshot.step
    if result.source.path.resolve() != source.resolve() or result.step != step:
        _issue(report, source, "provenance_mismatch", "Result source/step does not identify this snapshot", step=step)
        return report
    report.checks.append("snapshot/result source and step provenance")
    if not frame_confirmed:
        report.skipped.append("All reported comparisons: compatible coordinate frames/populations not confirmed")
        _issue(report, source, "comparison_not_performed", "Confirm compatible frames and populations to compare diagnostics", severity="warning", step=step)
        return report

    def compare(name, observed, unit, location, field):
        quantity = result.quantities.get(name)
        if quantity is None:
            report.skipped.append(f"{field}: calculated {name} is absent")
            return
        if quantity.unit != unit or not _finite_scalar(quantity.value):
            _issue(report, location, "incompatible_quantity", "Calculated observable has incompatible units or is not finite", field, step=step)
            return
        report.checks.append(f"{location.name}:{field} against {name}")
        if not np.isclose(quantity.value, observed, rtol=rtol, atol=atol):
            _issue(report, location, "reported_mismatch",
                   f"Reported {observed:g} {unit} differs from calculated {quantity.value:g} {unit}", field, step=step)

    attrs = snapshot.source.attributes
    file_attrs = attrs.get("file_attributes", {})
    for attr, names, factors, canonical in (
        ("centroid", ("centroid_x", "centroid_y", "centroid_z"), _LENGTH, "m"),
        ("RMSX", ("rms_x", "rms_y", "rms_z"), _LENGTH, "m"),
        ("RMSP", ("rms_px", "rms_py", "rms_pz"), {unit: 1. for unit in _NORMALIZED}, "p/(mc)"),
        ("#varepsilon", ("emit_nx", "emit_ny"), {"m": 1., "m rad": 1.}, "m"),
    ):
        if attr not in attrs:
            report.skipped.append(f"HDF5 {attr}: reported attribute absent")
            continue
        values = np.asarray(attrs[attr])
        if values.shape != (3,) or values.dtype.kind not in "iuf" or not np.all(np.isfinite(values)):
            _issue(report, source, "invalid_reported_metadata", "Expected a finite real three-component attribute", attr, step=step)
            continue
        unit = attrs.get(attr + "Unit", file_attrs.get(attr + "Unit"))
        if isinstance(unit, bytes):
            unit = unit.decode("utf-8")
        if not isinstance(unit, str) or unit not in factors:
            report.skipped.append(f"HDF5 {attr}: unknown/unsupported unit")
            _issue(report, source, "unknown_unit", "Reported attribute cannot be converted for comparison", attr, "warning", step)
            continue
        for index, name in enumerate(names):
            compare(name, values[index] * factors[unit], canonical, source, f"{attr}[{index}]")
    report.skipped.append("Reported geometric emittance: mean-beta-gamma and individual-slope estimators differ")
    if statistics is None:
        report.skipped.append("Statistics comparison: no table supplied")
        return report
    location = statistics.source.path
    times = statistics.columns.get("t")
    if (not _finite_scalar(snapshot.time) or not isinstance(times, np.ndarray)
        or times.ndim != 1 or not len(times) or times.dtype.kind not in "iuf"
        or not np.all(np.isfinite(times)) or _unit(statistics, "t") not in _TIME):
        _issue(report, location, "unmatched_coordinates", "Finite snapshot time and statistics times with known units are required", "t", "warning", step)
        report.skipped.append("Statistics: time matching unavailable")
        return report
    with np.errstate(over="ignore", invalid="ignore"):
        matches = np.flatnonzero(np.abs(times * _TIME[_unit(statistics, "t")] - snapshot.time) <= time_atol)
    if len(matches) != 1:
        code = "ambiguous_match" if len(matches) > 1 else "unmatched_coordinates"
        _issue(report, location, code, f"Expected exactly one time-matched row, found {len(matches)}", "t", step=step)
        report.skipped.append("Statistics observables: no unique time match")
        return report
    row = int(matches[0])
    paths = statistics.columns.get("s")
    if snapshot.s is not None and paths is not None:
        if (not _finite_scalar(snapshot.s) or not isinstance(paths, np.ndarray)
            or paths.shape != times.shape or paths.dtype.kind not in "iuf"
            or not _finite_scalar(paths[row]) or _unit(statistics, "s") not in _LENGTH):
            _issue(report, location, "unmatched_coordinates", "Path matching requires consistent dimensions and known units", "s", "warning", step)
            report.skipped.append("Statistics observables: path compatibility unavailable")
            return report
        if abs(paths[row] * _LENGTH[_unit(statistics, "s")] - snapshot.s) > path_atol:
            _issue(report, location, "coordinate_mismatch", "Time-matched statistics row has a different path coordinate", "s", step=step)
            report.skipped.append("Statistics observables: path mismatch")
            return report
        report.checks.append("statistics path coordinate agreement")
    else:
        report.skipped.append("Path check: path coordinate unavailable; statistics matched by time only")
    report.checks.append(f"unique statistics time match: row {row}")
    mappings = [("num_particles", "numParticles", {"1": 1.}, "1")]
    for axis, stat_axis in (("x", "x"), ("y", "y"), ("z", "s")):
        mappings += [(f"centroid_{axis}", f"mean_{stat_axis}", _LENGTH, "m"),
                     (f"rms_{axis}", f"rms_{stat_axis}", _LENGTH, "m"),
                     (f"rms_p{axis}", f"rms_p{stat_axis}", {u: 1. for u in _NORMALIZED}, "p/(mc)")]
    mappings += [("emit_n" + p, "emit_" + p, {"m": 1., "m rad": 1.}, "m") for p in ("x", "y")]
    for name, column, factors, canonical in mappings:
        values = statistics.columns.get(column)
        if values is None:
            report.skipped.append(f"Statistics {column}: column absent")
        elif (not isinstance(values, np.ndarray) or values.shape != times.shape
              or values.dtype.kind not in "iuf" or not _finite_scalar(values[row])):
            _issue(report, location, "invalid_reported_data", "Statistics column is malformed or matched value is not finite", column, step=step)
        elif _unit(statistics, column) not in factors:
            report.skipped.append(f"Statistics {column}: unknown/unsupported unit")
            _issue(report, location, "unknown_unit", "Statistics unit cannot be converted for comparison", column, "warning", step)
        else:
            compare(name, values[row] * factors[_unit(statistics, column)], canonical, location, f"{column}[{row}]")
    return report

