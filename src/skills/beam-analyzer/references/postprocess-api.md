# Postprocess API quick reference

Use the project's `.venv/bin/python`; installation is covered by the repository
README (`uv sync --locked`). All functions below import from `postprocess`.
They read local results; they do not retrieve files or launch simulations.
This reference follows the [library documentation](../../../postprocess/README.md)
and [public API](../../../postprocess/__init__.py).

## Discover and read

| Call | Returns / behavior |
| --- | --- |
| `discover_run(root)` | `RunFiles` with absolute `root` and sorted root-relative lists: `statistics`, `snapshots`, `timings`, `closed_orbits`, `inputs`, `derived`, `unhandled`. Classification is by filename, not content or job success. Subdirectories named `analysis` or `plots` are treated as derived; override with `derived_directories=(...)`. |
| `select_file(files, kind, path=None)` | Relative `Path` for `kind="statistics"`, `"snapshots"`, `"timings"`, or `"closed_orbits"`. No candidate returns `None`; multiple candidates raise `AmbiguousOutputError`. Supply an inventoried `path` explicitly to resolve ambiguity; files are not paired by basename. |
| `read_stat(path)` | `StatisticsTable`: `.columns[name]` NumPy arrays, `.fields[name].unit` / `.description`, `.row_count`, `.source`. Supports numeric columns in ASCII SDDS with `no_row_counts=1`; malformed rows raise rather than being skipped. |
| `read_closed_orbit(path)` | `ClosedOrbitData` from COF JSON: reported coordinates/residual (length 4), transfer map (4×4), convergence, stability and optional eigenvalues (4×2 real/imaginary pairs). All original fields remain in `.source.attributes`. Discovery recognizes `closed-orbit.json`; custom filenames can be read directly. See COF-only outputs below. |
| `list_snapshots(path)` | Sorted integer dump IDs from flat HDF5 `Step#N` groups, without loading particle arrays. IDs are not integration-step counts; zero and an exact exit dump are not guaranteed. |
| `read_snapshot(path, step)` | One materialized `ParticleSnapshot`; file is closed before return. `.columns`, `.fields`, `.particle_count`, `.step`, `.group_name`, `.source`, `.s` [m], `.time` [s]. Missing/unknown coordinate units yield `None` for `.s`/`.time`. |
| `read_timing(path)` | `TimingData` with `.text` and `.source`; preserves UTF-8 text, without parsing timer values or inferring success. |

Join selections with `files.root / selected_path` before reading. HDF5 particle
datasets must be equally sized 1D real numeric arrays; nested/linked layouts are
unsupported. Reader failures raise exceptions before validation can run.
Original metadata is retained in `.source.attributes` (including HDF5
`file_attributes` / `dataset_attributes` and the statistics `sdds_header`).

## Calculate and access results

`analyze_snapshot(snapshot, longitudinal_axis=None)` returns `AnalysisResult`:

- `.status`: `success`, `partial`, or `failed`; inspect `.issues` and `.assumptions`.
  Failed observables are omitted, not replaced by zero; particles are not silently
  discarded. Independent valid quantities can remain available in partial results.
- `.quantities[name]` has `.value`, `.unit`, `.definition`.
- `.covariances[name]` has `.values`, `.coordinates`, `.units`.
- `.source`, `.step`, `.s`, `.time` retain provenance and known coordinates.

| Keys | Meaning / units |
| --- | --- |
| `num_particles` | Unfiltered macroparticle count. |
| `centroid_x`, `rms_x`, etc. for `x,px,y,py,z,pz` | Means and centered population RMS spreads. Known m/cm/mm lengths convert to m; raw moments otherwise retain source units. |
| `emit_nx`, `emit_ny` | Projected normalized RMS emittances from `(x, px/(mc))`, `(y, py/(mc))`, in m. |
| `emit_x`, `emit_y` | Geometric RMS emittances using individual slopes `px/pz`, `py/pz`, in m; requires confirmed longitudinal z. |
| `alpha_x`, `beta_x`, `gamma_x` (and y) | Geometric Twiss parameters: units 1, m, 1/m. Zero emittance leaves Twiss undefined. |
| `centroid_x_prime`, `rms_x_prime` (and y) | Individual-slope mean and RMS, dimensionless; requires confirmed longitudinal z. |
| Covariance `phase_space` | Full 6×6 centered covariance in `(x,px,y,py,z,pz)` order when all fields are usable. |
| Covariances `x_normalized`, `y_normalized`, `x_geometric`, `y_geometric` | Corresponding 2×2 projected matrices; read their coordinate and unit metadata. |

Required conventions:

- Moments use equal macroparticle weights and population normalization N, with
  no factor of pi in emittance. Missing/unequal `q` warns; optics requires one
  species. Confirm common species independently if `sp` is absent.
- Normalized optics requires momentum units `p/(mc)` or `#beta#gamma`.
  Dimensionless `1` alone is insufficient. Only after independent verification,
  `snapshot.momentum_convention = "p/(mc)"` can resolve unknown/dimensionless
  metadata; conflicting units still block optics.
- Pass `longitudinal_axis="z"` only after verifying a common position/momentum
  frame with z longitudinal and every `pz > 0`. No orbit rotation is inferred.
  Otherwise omit it and use stored-axis moments and supported normalized optics.
- Multiply emittance in m by `1e6` for mm mrad. There is no dispersion subtraction,
  longitudinal Twiss, eigenemittance, or charge-weighted analysis.

## Validate and compare

Validators return `ValidationReport`: inspect `.issues` (severity, code, message,
source, step, field), `.checks`, and `.skipped`. `.is_valid` means no errors in
performed checks; it does not prove job completion or physical validity.

| Call | Checks |
| --- | --- |
| `validate_run_files(files, required=("statistics", "snapshots"))` | Required file categories, existence/size; warns on multiple candidates and records unsupported artifacts. Use `required=("statistics",)` for statistics-only analysis or `required=("closed_orbits",)` for COF-only analysis. |
| `validate_closed_orbit(orbit, require_stable=False, position_atol=None, momentum_atol=None)` | COF numerical integrity, metadata and convergence. Optionally requires reported `STABLE` and strict closure bounds in m and p/(mc). Does not independently compare the map, eigenvalues or tunes; see COF-only outputs below. |
| `validate_statistics(stats, required=("t", "s", "numParticles"))` | Numeric integrity, counts, nonnegative spreads/emittances, bounded correlations, time ordering. Does not assume particle or energy conservation. |
| `validate_snapshot(snapshot, longitudinal_axis=None)` | Six phase-space fields, numeric integrity, units, coordinates, IDs, species and weighting; requires forward pz when z is requested. |
| `validate_analysis(result, longitudinal_axis=None)` | Calculation status/issues, completeness, units, covariance consistency, emittance and Twiss identities. Use the same longitudinal-axis argument as calculation. |
| `validate_timing(timing)` | Timing text availability only. |
| `compare_diagnostics(snapshot, result, statistics=None, frame_confirmed=False)` | Compares calculated moments with HDF5 attributes and optional time-matched statistics. Source/step must match; caller must confirm compatible frames and populations. Otherwise comparisons are skipped. |

Analysis validation and comparisons default to `rtol=1e-8`, `atol=1e-12` in each
observable's canonical units. Statistics comparison requires exactly one row
within `time_atol=1e-15` s and, when both paths exist, agreement within
`path_atol=1e-6` m; no nearest-row matching or interpolation. Unknown units are
skipped with warnings. Reported geometric emittance is skipped because its
estimator differs. The documented OPALX FODO revision has incorrect HDF5
`centroid` attributes; retain comparison failures and use particle-derived
moments rather than repairing source metadata.

## Minimal analysis and export pattern

Replace the two example paths. This pattern requires both diagnostic categories;
adapt requirements for a statistics-only task. It retains reports and partial
results for inspection before choosing which quantities to plot.

```python
from pathlib import Path
from postprocess import (
    discover_run, select_file, read_stat, list_snapshots, read_snapshot,
    analyze_snapshot, validate_run_files, validate_statistics,
    validate_snapshot, validate_analysis, to_dataframe, results_to_dataframe,
    to_summary, write_json, write_statistics_csv,
)

files = discover_run("output/my-run/results")
out = Path("output/my-run/analysis/new-analysis/data")
out.mkdir(parents=True, exist_ok=False)
file_report = validate_run_files(files)
stat_path = select_file(files, "statistics")  # Supply path=... if ambiguous.
h5_path = select_file(files, "snapshots")
if stat_path is None or h5_path is None:
    raise FileNotFoundError("Statistics and particle dumps are required")
stats = read_stat(files.root / stat_path)
stat_report = validate_statistics(stats)
table = to_dataframe(stats, validation=stat_report)
print(table.columns.tolist(), table.attrs["units"])  # Inspect before plotting.

# Change to "z" only after independently confirming the frame and forward pz.
axis = None
results, reports, input_reports = [], [], []
for step in list_snapshots(files.root / h5_path):
    snapshot = read_snapshot(files.root / h5_path, step)
    input_reports.append(validate_snapshot(snapshot, longitudinal_axis=axis))
    result = analyze_snapshot(snapshot, longitudinal_axis=axis)
    results.append(result)
    reports.append(validate_analysis(result, longitudinal_axis=axis))
    # Extract any selected particle-plot data here to avoid rereading dumps.

series = results_to_dataframe(results, validation_reports=reports)
write_statistics_csv(stats, out / "statistics.csv", validation=stat_report)
series.to_csv(out / "observables.csv", index=False)
write_json(series.attrs, out / "observables.metadata.json")
write_json({"files": to_summary(file_report), "statistics": to_summary(stat_report),
            "snapshots": [to_summary(r) for r in input_reports]},
           out / "input_validation.json")
# Calculation reports, issues, assumptions and covariances are in series.attrs.
```

## Export behavior

- `to_dataframe(stats_or_snapshot, columns=None, validation=None)` copies source
  columns and preserves per-column dtypes; no conversion or filtering. Statistics
  time may be ns even though snapshot `.time` and result-series time are seconds.
- `results_to_dataframe(results, validation_reports=None)` preserves input order,
  failed/partial rows and missing quantities as NaN; columns include `source`,
  nullable-integer `step`, `status`, `s`, `time`, and scalar quantities. It neither
  sorts nor aligns runs. Conflicting units/definitions and array quantities raise.
- `to_summary(data, validation=None, include_arrays=False)` returns a JSON-compatible
  summary of tables, snapshots, COF data, results, reports, inventories, timing or mappings.
  `write_json(data, path, ...)` writes it. Full particle/statistics arrays are
  omitted by default; small COF arrays, calculated quantities and covariances remain included.
- `write_statistics_csv(stats, path, columns=None, validation=None)` returns
  `(csv_path, metadata_path)`; keep the `<filename>.metadata.json` sidecar.
  Pandas CSV does not preserve `.attrs`; save derived-series metadata separately.
- Library writers create parents and refuse existing destinations unless
  `overwrite=True`. JSON converts NaN/Inf to `null` with `serialization_issues`;
  `nonfinite="raise"` rejects them. CSV retains literal nan/inf values. Exporters
  do not validate, filter, or repair data.

## COF-only outputs

Use `read_closed_orbit(path)` for the observed COF JSON layout. Discovery
recognizes `closed-orbit.json` in `closed_orbits`; custom names can be read
explicitly. Other JSON is not classified as COF. For a COF-only task use
`validate_run_files(files, required=("closed_orbits",))`.

`ClosedOrbitData` exposes `.converged`, `.coordinates`, `.residual`, `.matrix`,
`.stability`, optional `.eigenvalues` (real/imaginary pairs), `.coordinate_order`,
`.units` and `.source`. Coordinate order is `(x, px, y, py)`, units are
`(m, p/(mc), m, p/(mc))`, and map entry i,j has units units[i]/units[j]. All
original fields remain in `.source.attributes`, including fractional modes,
energy drift and section-frame metadata. This is a transfer map, not a particle
snapshot or covariance. Do not apply `analyze_snapshot` to it.

`validate_closed_orbit(orbit, require_stable=False, position_atol=None,
momentum_atol=None)` checks numeric integrity, metadata and convergence.
Optional closure bounds are strict absolute bounds in m and p/(mc), respectively.
DBA uses `require_stable=True`, `position_atol=1e-7`, `momentum_atol=1e-7`.
Reported stability is not independently recomputed. Inspect skipped checks;
validation alone does not establish map accuracy against analytic optics.

`to_summary(orbit, validation=report)` and `write_json` preserve all small COF
arrays and source metadata. No DataFrame adapter or slope conversion is implicit.
For this DBA fixture, the separate offline checker
`tests/postprocess/check_dba.py` compares `T^-1 M T` with the analytic transverse
slope map, using `p0_mc` explicitly recovered from the run log; see the
[acceptance documentation](../../../../tests/postprocess/README.md).
