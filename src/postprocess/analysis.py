"""Equal-macroparticle population moments and projected transverse optics.

No particles are silently removed and no coordinates are rotated. Reported OPALX
attributes are provenance only, never substitutes for recomputed quantities.
See README.md for units, formulas, result names and scope.
"""

from typing import Literal

import numpy as np

from .models import AnalysisResult, CovarianceMatrix, ParticleSnapshot, Quantity, ValidationIssue


_AXES = ("x", "px", "y", "py", "z", "pz")
_LENGTH_FACTORS = {"m": 1.0, "cm": 1e-2, "mm": 1e-3}
_NORMALIZED_UNITS = {"#beta#gamma", "p/(mc)"}
_RANK_TOLERANCE = 32 * np.finfo(np.float64).eps


def _center(values):
    # Shift before averaging to avoid subtracting two large raw second moments.
    shifted = values - values[0]
    offset = np.mean(shifted)
    return float(values[0] + offset), shifted - offset


def _covariance(centered, coordinates, units):
    values = np.column_stack([centered[name] for name in coordinates])
    matrix = values.T @ values / len(values)
    if not np.all(np.isfinite(matrix)):
        raise FloatingPointError("Covariance is not finite")
    return CovarianceMatrix(matrix, tuple(coordinates), tuple(units[name] for name in coordinates))


def _emittance(first, second):
    """Stable sqrt(det(cov)): SVD of centered, RMS-scaled particle columns."""
    scales = np.sqrt([np.mean(first * first), np.mean(second * second)])
    if np.any(scales == 0):
        return 0.0
    standardized = np.column_stack((first / scales[0], second / scales[1]))
    singular = np.linalg.svd(standardized, compute_uv=False)
    if len(singular) < 2 or singular[1] <= _RANK_TOLERANCE * singular[0]:
        return 0.0
    value = float(np.prod(singular / np.sqrt(len(first))) * scales[0] * scales[1])
    if not np.isfinite(value):
        raise FloatingPointError("Emittance is not finite")
    return value


def _is_normalized(snapshot, name):
    metadata = snapshot.fields.get(name)
    unit = metadata.unit if metadata else None
    convention = snapshot.momentum_convention
    if convention is not None and convention != "p/(mc)":
        return False
    return unit in _NORMALIZED_UNITS or (
        convention == "p/(mc)" and unit in (None, "1")
    )


def analyze_snapshot(
    snapshot: ParticleSnapshot,
    *,
    longitudinal_axis: Literal["z"] | None = None,
) -> AnalysisResult:
    """Calculate moments and normalized x/y emittances in the stored axes.

    Opt into geometric emittance/Twiss with longitudinal_axis='z', asserting
    that positions and momenta share a frame with z longitudinal. No reference
    rotation is inferred from OPALX attributes. Use a common particle species.

    Lengths in m/cm/mm are converted to m. Other/unknown units are retained for
    raw moments, but cannot support physical emittance calculations. Normalized
    momentum requires explicit p/(mc) metadata or the OPALX '#beta#gamma' label.
    A dimensionless unit alone is insufficient. Geometric optics requires every
    pz > 0 and uses per-particle slopes, not a mean-momentum approximation.

    Invalid fields/calculations produce contextual issues and partial results.
    Missing q or unequal q produces a warning: results still describe the
    equal-macroparticle population, not a charge-weighted bunch. General input
    validation and reported-output comparisons remain separate workflow stages.
    """
    if longitudinal_axis not in (None, "z"):
        raise ValueError("Only an explicitly confirmed longitudinal z axis is supported")
    result = AnalysisResult(snapshot.source, "failed", step=snapshot.step,
                            s=snapshot.s, time=snapshot.time)
    result.assumptions.extend([
        "Equal macroparticle weighting; population moments use normalization N, not N-1.",
        "Stored coordinate axes; no reference-orbit rotation, dispersion subtraction or particle filtering.",
        "Projected mechanical-momentum emittances, not canonical eigenemittances; common particle species required.",
        f"RMS-scaled singular-value ratios <= {_RANK_TOLERANCE:g} are treated as zero emittance.",
    ])
    if longitudinal_axis == "z":
        result.assumptions.append(
            "Caller confirms common position/momentum frame with forward longitudinal z; slopes are px/pz and py/pz."
        )
    else:
        result.assumptions.append("Geometric optics omitted: no longitudinal axis confirmed.")

    def issue(code, message, field_name=None, severity="error"):
        result.issues.append(ValidationIssue(
            code, message, severity, snapshot.source.path, snapshot.step, field_name,
        ))

    def put(name, value, unit, definition):
        result.quantities[name] = Quantity(value, unit, definition)

    arrays, centered, units = {}, {}, {}
    count = None
    for name in _AXES:
        if name not in snapshot.columns:
            issue("missing_field", f"Missing particle coordinate {name}", name)
            continue
        values = snapshot.columns[name]
        if not isinstance(values, np.ndarray) or values.ndim != 1 or values.dtype.kind not in "iuf":
            issue("invalid_dimensions", "Expected a 1D real numeric array", name)
            continue
        if count is None:
            count = len(values)
        if len(values) != count:
            issue("inconsistent_dimensions", "Particle coordinate lengths disagree", name)
            continue
        if not len(values):
            issue("empty_snapshot", "No particles available for population moments", name)
            continue
        if not np.all(np.isfinite(values)):
            issue("nonfinite_data", "Coordinate contains nonfinite values; no particles were dropped", name)
            continue
        metadata = snapshot.fields.get(name)
        unit = metadata.unit if metadata else None
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                values = values.astype(np.float64)
                if name in ("x", "y", "z") and unit in _LENGTH_FACTORS:
                    values = values * _LENGTH_FACTORS[unit]
                    if unit != "m":
                        result.assumptions.append(f"Converted {name} from {unit} to m.")
                    unit = "m"
                elif name.startswith("p") and _is_normalized(snapshot, name):
                    unit = "p/(mc)"
                mean, deviations = _center(values)
                rms = float(np.sqrt(np.mean(deviations * deviations)))
                if not np.isfinite(mean) or not np.isfinite(rms):
                    raise FloatingPointError("Nonfinite moments")
        except FloatingPointError as error:
            issue("calculation_failed", str(error), name)
            continue
        arrays[name], centered[name], units[name] = values, deviations, unit
        put(f"centroid_{name}", mean, unit, f"mean({name})")
        put(f"rms_{name}", rms, unit, f"sqrt(mean(({name} - mean({name}))**2))")

    if not arrays:
        return result
    put("num_particles", float(count), "1", "Number of equally weighted macroparticles; no filtering")
    if all(name in centered for name in _AXES):
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                result.covariances["phase_space"] = _covariance(centered, _AXES, units)
        except FloatingPointError as error:
            issue("calculation_failed", str(error), "phase_space")

    charge = snapshot.columns.get("q")
    if charge is None:
        issue("weights_unverified", "No q dataset; equal macroparticle weights assumed", "q", "warning")
    elif (not isinstance(charge, np.ndarray) or charge.ndim != 1 or len(charge) != count
          or charge.dtype.kind not in "iuf" or not np.all(np.isfinite(charge))):
        issue("invalid_charge", "Cannot check equal charges; q is malformed or nonfinite", "q", "warning")
    elif not np.allclose(charge, charge[0], rtol=1e-12, atol=0):
        issue("unequal_charges", "Equal macroparticle moments are not charge-weighted bunch moments", "q", "warning")

    species = snapshot.columns.get("sp")
    mixed_species = species is not None and len(np.unique(species)) > 1
    if mixed_species:
        issue("mixed_species", "Select one particle species before calculating normalized or geometric optics", "sp")

    for plane in ("x", "y"):
        momentum = "p" + plane
        if plane not in centered or momentum not in centered or mixed_species:
            continue
        if units[plane] != "m" or not _is_normalized(snapshot, momentum):
            issue("unknown_convention", "Emittance requires known position units and momentum p/(mc)", f"emit_n{plane}")
            continue
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                result.covariances[f"{plane}_normalized"] = _covariance(centered, (plane, momentum), units)
                emit = _emittance(centered[plane], centered[momentum])
            put(f"emit_n{plane}", emit, "m", f"sqrt(det(cov({plane}, {momentum}))); stored {momentum} is p_{plane}/(mc)")
        except (FloatingPointError, np.linalg.LinAlgError) as error:
            issue("calculation_failed", str(error), f"emit_n{plane}")
            continue
        if longitudinal_axis is None:
            continue
        if "pz" not in arrays or not _is_normalized(snapshot, "pz"):
            issue("unknown_convention", "Geometric optics requires longitudinal momentum pz/(mc)", f"emit_{plane}")
            continue
        if np.any(arrays["pz"] <= 0):
            issue("invalid_longitudinal_momentum", "Geometric optics requires every particle pz > 0", f"emit_{plane}")
            continue
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                slope = arrays[momentum] / arrays["pz"]
                mean, deviations = _center(slope)
                slope_name = f"{plane}_prime"
                covariance = _covariance(
                    {plane: centered[plane], slope_name: deviations},
                    (plane, slope_name), {plane: "m", slope_name: "1"},
                )
                emit = _emittance(centered[plane], deviations)
                rms = float(np.sqrt(covariance.values[1, 1]))
            result.covariances[f"{plane}_geometric"] = covariance
            put(f"centroid_{slope_name}", mean, "1", f"mean({momentum}/pz)")
            put(f"rms_{slope_name}", rms, "1", f"std({momentum}/pz, ddof=0)")
            put(f"emit_{plane}", emit, "m", f"sqrt(det(cov({plane}, {momentum}/pz)))")
            if emit == 0:
                issue("undefined_twiss", "Zero or numerically rank-deficient emittance; Twiss parameters are undefined", plane)
                continue
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                alpha = float(-covariance.values[0, 1] / emit)
                beta = float(covariance.values[0, 0] / emit)
                gamma = float(covariance.values[1, 1] / emit)
                if not np.all(np.isfinite([alpha, beta, gamma])):
                    raise FloatingPointError("Nonfinite Twiss parameters")
            put(f"alpha_{plane}", alpha, "1", f"-cov({plane}, {slope_name}) / emit_{plane}")
            put(f"beta_{plane}", beta, "m", f"var({plane}) / emit_{plane}")
            put(f"gamma_{plane}", gamma, "1/m", f"var({slope_name}) / emit_{plane}")
        except (FloatingPointError, np.linalg.LinAlgError) as error:
            issue("calculation_failed", str(error), f"geometric_{plane}")

    result.status = "partial" if any(item.severity == "error" for item in result.issues) else "success"
    return result
