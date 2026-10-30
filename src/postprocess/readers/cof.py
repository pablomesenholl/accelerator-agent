"""Read the observed OPALX COF JSON layout without deriving optics."""

import json
from pathlib import Path

import numpy as np

from ..models import ClosedOrbitData, SourceMetadata


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _array(value, shape, name):
    array = np.asarray(value)
    if array.shape != shape or array.dtype.kind not in "iuf":
        raise ValueError(f"{name}: expected real numeric array of shape {shape}")
    return array.astype(np.float64)


def read_closed_orbit(path: str | Path) -> ClosedOrbitData:
    """Load COF vectors/map, preserving every source field in attributes.

    Required fields follow the observed COF layout. Malformed structures raise;
    nonfinite numbers and unconverged results remain available for validation.
    Arbitrarily named files are accepted, but generic JSON is not a COF result.
    """
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(data, dict):
            raise ValueError("Expected a COF JSON object")
        for name in ("converged", "coordinates", "residual", "matrix", "stability"):
            if name not in data:
                raise ValueError(f"Missing COF field: {name}")
        if type(data["converged"]) is not bool:
            raise ValueError("converged: expected boolean")
        if not isinstance(data["stability"], str):
            raise ValueError("stability: expected string")
        return ClosedOrbitData(
            source=SourceMetadata(path, attributes=data),
            converged=data["converged"],
            coordinates=_array(data["coordinates"], (4,), "coordinates"),
            residual=_array(data["residual"], (4,), "residual"),
            matrix=_array(data["matrix"], (4, 4), "matrix"),
            stability=data["stability"],
            eigenvalues=(_array(data["eigenvalues"], (4, 2), "eigenvalues")
                         if "eigenvalues" in data else None),
        )
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError(f"{path}: {error}") from error
