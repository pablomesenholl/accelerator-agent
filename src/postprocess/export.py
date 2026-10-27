"""Agent-facing summaries, plotting adapters and portable numerical exports.

No calculation, physical validation, filtering or unit conversion happens here.
Column values and dtypes are preserved; optional validation reports are explicit.
"""

from collections.abc import Iterable, Mapping
import csv
from dataclasses import fields, is_dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .models import (
    AnalysisResult, ParticleSnapshot, RunFiles, StatisticsTable, TimingData,
    ValidationReport, _check_columns,
)


_SCHEMA_VERSION = 1
_TABLES = (StatisticsTable, ParticleSnapshot)


def _json_value(value, replacements, path="$", *, nonfinite="null"):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if np.isfinite(number):
            return number
        if np.isfinite(value):
            raise ValueError(f"Finite value at {path} exceeds JSON float range")
        if nonfinite == "raise":
            raise ValueError(f"Nonfinite number at {path}")
        kind = "nan" if np.isnan(number) else ("positive_infinity" if number > 0 else "negative_infinity")
        replacements.append({"path": path, "kind": kind})
        return None
    if isinstance(value, np.ndarray):
        return _json_value(value.tolist(), replacements, path, nonfinite=nonfinite)
    if is_dataclass(value) and not isinstance(value, type):
        value = {item.name: getattr(value, item.name) for item in fields(value)}
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError(f"JSON mapping keys must be strings at {path}")
        return {key: _json_value(item, replacements, f"{path}[{key!r}]", nonfinite=nonfinite)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item, replacements, f"{path}[{index}]", nonfinite=nonfinite)
                for index, item in enumerate(value)]
    raise TypeError(f"Unsupported JSON value {type(value).__name__} at {path}")


def _selected(data, columns):
    _check_columns(data.columns)
    if columns is None:
        return dict(data.columns)
    if isinstance(columns, str):
        raise TypeError("columns must be a sequence of column names, not a string")
    names = list(columns)
    if not names or not all(isinstance(name, str) for name in names) or len(set(names)) != len(names):
        raise ValueError("Select nonempty, unique string column names")
    missing = [name for name in names if name not in data.columns]
    if missing:
        raise KeyError(f"Unknown columns: {missing}")
    return {name: data.columns[name] for name in names}


def _table_summary(data, columns, include_arrays):
    descriptions = {}
    for name, array in columns.items():
        finite = array[np.isfinite(array)]
        field = data.fields.get(name)
        entry = {
            "dtype": str(array.dtype), "shape": list(array.shape),
            "unit": field.unit if field else None,
            "description": field.description if field else None,
            "nonfinite_count": int(array.size - finite.size),
            "finite_min": finite.min() if finite.size else None,
            "finite_max": finite.max() if finite.size else None,
            "first": array[0] if array.size else None,
            "last": array[-1] if array.size else None,
        }
        if include_arrays:
            entry["values"] = array
        descriptions[name] = entry
    summary = {
        "kind": "statistics" if isinstance(data, StatisticsTable) else "particle_snapshot",
        "source": data.source, "row_count": data.row_count if isinstance(data, StatisticsTable) else data.particle_count,
        "columns": descriptions,
        "units": {name: entry["unit"] for name, entry in descriptions.items()},
        "includes_arrays": include_arrays,
    }
    if isinstance(data, ParticleSnapshot):
        summary.update(step=data.step, group_name=data.group_name, s=data.s, time=data.time,
                       coordinate_units={"s": "m", "time": "s"},
                       coordinate_frame=data.coordinate_frame, momentum_convention=data.momentum_convention)
    return summary


def _finalize(payload, validation, nonfinite):
    if nonfinite not in ("null", "raise"):
        raise ValueError("nonfinite must be 'null' or 'raise'")
    if validation is not None and not isinstance(validation, ValidationReport):
        raise TypeError("validation must be a ValidationReport")
    payload["schema_version"] = _SCHEMA_VERSION
    payload["validation"] = (payload.get("validation") if validation is None else {
        "is_valid": validation.is_valid, "issues": validation.issues,
        "checks": validation.checks, "skipped": validation.skipped,
    })
    payload["nonfinite_policy"] = nonfinite
    previous = payload.pop("serialization_issues", [])
    if not isinstance(previous, list):
        raise TypeError("serialization_issues must be a list in an existing summary")
    replacements = []
    result = _json_value(payload, replacements, nonfinite=nonfinite)
    result["serialization_issues"] = _json_value(previous, replacements, "$['serialization_issues']",
                                                nonfinite=nonfinite) + replacements
    return result


def to_summary(data, *, include_arrays=False, validation: ValidationReport | None = None,
               nonfinite="null") -> dict:
    """Return schema-v1 JSON-compatible data, omitting full particle arrays by default.

    Supports loaded tables/snapshots, AnalysisResult, ValidationReport, RunFiles,
    TimingData and explicit mappings. Source metadata stays separate from
    calculated quantities. Nonfinite numbers become null with JSON locations in
    serialization_issues, or raise with nonfinite='raise'. Column descriptors
    count all nonfinite cells; finite_min/max describe only finite entries.
    Unknown objects, non-string dictionary keys and non-UTF-8 bytes raise.
    """
    if isinstance(data, _TABLES):
        payload = _table_summary(data, _selected(data, None), include_arrays)
    elif isinstance(data, AnalysisResult):
        payload = {"kind": "analysis_result", **{f.name: getattr(data, f.name) for f in fields(data)},
                   "coordinate_units": {"s": "m", "time": "s"}}
    elif isinstance(data, ValidationReport):
        payload = {"kind": "validation_report", "is_valid": data.is_valid,
                   "issues": data.issues, "checks": data.checks, "skipped": data.skipped}
    elif isinstance(data, (RunFiles, TimingData)):
        payload = {"kind": "run_files" if isinstance(data, RunFiles) else "timing",
                   **{f.name: getattr(data, f.name) for f in fields(data)}}
    elif isinstance(data, Mapping):
        # Passing an existing summary through write_json must preserve its
        # schema, validation and previous nonfinite-value diagnostics.
        payload = (dict(data) if data.get("schema_version") == _SCHEMA_VERSION
                   and isinstance(data.get("kind"), str) else {"kind": "mapping", "data": data})
    else:
        raise TypeError(f"Unsupported summary type: {type(data).__name__}")
    # Structural schemas remain visible even for failed/partial calculations.
    return _finalize(payload, validation, nonfinite)


def to_dataframe(data: StatisticsTable | ParticleSnapshot, *, columns=None,
                 validation: ValidationReport | None = None) -> pd.DataFrame:
    """Copy selected original columns for plotting; preserve each NumPy dtype.

    Metadata is JSON-compatible in frame.attrs, including frame.attrs['units'].
    No rows are filtered and no units converted. Pandas/CSV operations may drop
    attrs; persist a JSON sidecar if exchanging tables with other programs.
    """
    if not isinstance(data, _TABLES):
        raise TypeError("to_dataframe expects StatisticsTable or ParticleSnapshot")
    selected = _selected(data, columns)
    frame = pd.DataFrame(selected, copy=True)
    # Build only selected descriptors, keeping the original row count/provenance.
    metadata = _table_summary(data, selected, False)
    frame.attrs = _finalize(metadata, validation, "null")
    return frame


def results_to_dataframe(results: Iterable[AnalysisResult], *,
                         validation_reports: Iterable[ValidationReport] | None = None) -> pd.DataFrame:
    """One row per calculation, retaining input order and failed/partial rows.

    Columns: source, step, status, s [m], time [s], then scalar observables.
    Missing observables remain NaN, never zero. Units and definitions must agree
    across rows; no frame alignment or resampling is inferred. Full per-result
    summaries (issues, assumptions, covariance) are retained in attrs['results'].
    Array-valued quantities use to_summary instead of this scalar table adapter.
    """
    results = list(results)
    reports = list(validation_reports) if validation_reports is not None else [None] * len(results)
    if len(reports) != len(results):
        raise ValueError("Provide exactly one validation report per result")
    reserved = {"source", "step", "status", "s", "time"}
    units, definitions, rows, summaries = {"s": "m", "time": "s"}, {}, [], []
    for result, report in zip(results, reports):
        if not isinstance(result, AnalysisResult):
            raise TypeError("results must contain AnalysisResult objects")
        row = {"source": str(result.source.path), "step": result.step, "status": result.status,
               "s": result.s, "time": result.time}
        for name, quantity in result.quantities.items():
            if name in reserved:
                raise ValueError(f"Quantity name conflicts with a coordinate/provenance column: {name}")
            array = np.asarray(quantity.value)
            if array.ndim != 0 or array.dtype.kind not in "iuf":
                raise ValueError(f"Quantity {name} must be a real scalar for an analysis table")
            if name in units and (quantity.unit != units[name] or quantity.definition != definitions[name]):
                raise ValueError(f"Inconsistent units or definitions for quantity {name}")
            units[name], definitions[name] = quantity.unit, quantity.definition
            row[name] = quantity.value
        rows.append(row)
        summaries.append(to_summary(result, validation=report))
    frame = pd.DataFrame(rows, columns=["source", "step", "status", "s", "time", *definitions])
    # Use original integers before inference can round them through float when
    # another row has an unknown step.
    frame["step"] = pd.array([row["step"] for row in rows], dtype="Int64")
    for coordinate in ("s", "time"):
        frame[coordinate] = pd.to_numeric(frame[coordinate])
    frame.attrs = {"schema_version": _SCHEMA_VERSION, "kind": "analysis_series",
                   "units": units, "definitions": definitions, "results": summaries}
    return frame


def _destination(path, overwrite):
    path = Path(path)
    if not overwrite and path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_json(data, path: str | Path, *, include_arrays=False,
               validation: ValidationReport | None = None, nonfinite="null", overwrite=False) -> Path:
    """Save a strict UTF-8 JSON summary; serialize before creating any file.

    Existing files require overwrite=True. Parents are created as needed.
    """
    payload = to_summary(data, include_arrays=include_arrays, validation=validation, nonfinite=nonfinite)
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path = _destination(path, overwrite)
    with path.open("w" if overwrite else "x", encoding="utf-8") as handle:
        handle.write(text)
    return path


def write_statistics_csv(table: StatisticsTable, path: str | Path, *, columns=None,
                         validation: ValidationReport | None = None, overwrite=False) -> tuple[Path, Path]:
    """Write column-name CSV plus '<path>.metadata.json' containing units/dtypes.

    Numeric values are streamed without float coercion of integer columns.
    NaN/Inf cells retain their textual nan/inf/-inf forms, with counts in the
    metadata. No records are dropped. Existing data or sidecar requires explicit
    overwrite=True. This pair is not an atomic multi-file transaction.
    """
    if not isinstance(table, StatisticsTable):
        raise TypeError("write_statistics_csv expects StatisticsTable")
    selected = _selected(table, columns)
    metadata = _table_summary(table, selected, False)
    path = Path(path)
    sidecar = path.with_name(path.name + ".metadata.json")
    metadata["export"] = {"format": "csv", "path": str(path), "columns": list(selected),
                          "nonfinite_cells": "nan/inf/-inf", "units_converted": False}
    payload = _finalize(metadata, validation, "null")
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if not overwrite:
        for target in (path, sidecar):
            if target.exists():
                raise FileExistsError(target)
    _destination(path, overwrite)
    with path.open("w" if overwrite else "x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(selected)
        if selected:
            for index in range(table.row_count):
                writer.writerow([array[index].item() for array in selected.values()])
    with sidecar.open("w" if overwrite else "x", encoding="utf-8") as handle:
        handle.write(text)
    return path, sidecar
