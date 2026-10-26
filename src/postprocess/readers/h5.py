"""Readers for the flat Step#N particle-dump layout observed in OPALX."""

from pathlib import Path
import re

import h5py
import numpy as np

from ..models import FieldMetadata, ParticleSnapshot, SourceMetadata


def _text(value) -> str | None:
    if value is None:
        return None
    array = np.asarray(value)
    if array.size != 1:
        raise ValueError("Expected scalar text metadata")
    value = array.reshape(-1)[0]
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise ValueError("Expected text metadata")


def _steps(handle: h5py.File) -> dict[int, str]:
    result = {}
    for name in handle:
        if not name.startswith("Step#"):
            continue
        if not re.fullmatch(r"Step#\d+", name):
            raise ValueError(f"Malformed snapshot group name: {name}")
        if not isinstance(handle.get(name, getlink=True), h5py.HardLink):
            raise ValueError(f"Linked snapshot groups are unsupported: {name}")
        if not isinstance(handle[name], h5py.Group):
            raise ValueError(f"Snapshot is not a group: {name}")
        step = int(name[5:])
        if step in result:
            raise ValueError(f"Duplicate numeric snapshot identifier: {name}")
        result[step] = name
    if not result:
        raise ValueError("No Step#N snapshot groups found")
    return result


def list_snapshots(path: str | Path) -> list[int]:
    """List numeric dump IDs without reading particle datasets; close the file."""
    path = Path(path).resolve()
    try:
        with h5py.File(path, "r") as handle:
            return sorted(_steps(handle))
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def _coordinate(attrs: dict, file_attrs: dict, name: str, factors: dict) -> float | None:
    if name not in attrs:
        return None
    value = np.asarray(attrs[name])
    if value.size != 1 or value.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be a real numeric scalar")
    unit = _text(attrs.get(name + "Unit", file_attrs.get(name + "Unit")))
    # Unknown units stay in raw metadata; never guess a convenience coordinate.
    return float(value.reshape(-1)[0]) * factors[unit] if unit in factors else None


def read_snapshot(path: str | Path, step: int) -> ParticleSnapshot:
    """Materialize one dump and close the file before returning.

    All datasets must be equally sized 1D real numeric particle arrays; missing
    physics fields are left for validation. Nested groups and linked datasets
    are rejected. Retain original group/file/dataset attributes, including bytes
    and array values, without reinterpretation. Field units prefer dataset
    'units'/'unit' attributes, then group/file '<name>Unit'. Coordinate frames and
    momentum conventions remain unknown. Known SPOS/TIME units are converted
    explicitly to metres/seconds; absent/unknown units give None.
    """
    if isinstance(step, bool) or not isinstance(step, (int, np.integer)) or step < 0:
        raise ValueError("Snapshot step must be a nonnegative integer dump ID")
    path = Path(path).resolve()
    try:
        with h5py.File(path, "r") as handle:
            groups = _steps(handle)
            if step not in groups:
                raise ValueError(f"Snapshot {step} not found; available: {sorted(groups)}")
            group = handle[groups[step]]
            attrs, file_attrs = dict(group.attrs), dict(handle.attrs)
            if {"file_attributes", "dataset_attributes"} & attrs.keys():
                raise ValueError("Snapshot attributes use reserved metadata keys")
            dataset_attrs, fields, lengths = {}, {}, set()
            for name in group:
                if not isinstance(group.get(name, getlink=True), h5py.HardLink):
                    raise ValueError(f"Linked particle datasets are unsupported: {name}")
                dataset = group[name]
                if not isinstance(dataset, h5py.Dataset):
                    raise ValueError(f"Nested particle groups are unsupported: {name}")
                if dataset.ndim != 1 or dataset.dtype.kind not in "iuf":
                    raise ValueError(f"Particle dataset {name} must be a 1D real numeric array")
                lengths.add(dataset.shape[0])
                dataset_attrs[name] = dict(dataset.attrs)
                unit = dataset.attrs.get("units", dataset.attrs.get("unit",
                    attrs.get(name + "Unit", file_attrs.get(name + "Unit"))))
                fields[name] = FieldMetadata(_text(unit), _text(dataset.attrs.get("description")))
            if len(lengths) > 1:
                raise ValueError("Particle dataset lengths disagree")
            snapshot = ParticleSnapshot(
                step=int(step), group_name=groups[step],
                columns={name: group[name][...] for name in group},
                source=SourceMetadata(path, _text(file_attrs.get("OPAL_version")),
                    {**attrs, "file_attributes": file_attrs, "dataset_attributes": dataset_attrs}),
                fields=fields,
                s=_coordinate(attrs, file_attrs, "SPOS", {"m": 1.0, "cm": 1e-2, "mm": 1e-3}),
                time=_coordinate(attrs, file_attrs, "TIME", {"s": 1.0, "ns": 1e-9, "us": 1e-6, "ps": 1e-12}),
            )
        return snapshot
    except (ValueError, TypeError) as error:
        raise ValueError(f"{path}, step {step}: {error}") from error
