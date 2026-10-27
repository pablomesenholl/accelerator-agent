# OPALX numerical postprocessing

Packaging is deferred. Run from the repository with `PYTHONPATH=src` and the
project `.venv` interpreter. This library reads local files; Magnus retrieval
remains with the simulator skill. No simulation is launched by these functions.

```python
from postprocess import analyze_snapshot
from postprocess.readers import read_snapshot

snapshot = read_snapshot("output/opalx-simulator/fodo-no-spacecharge/FODO-no-spacecharge.h5", 10)
result = analyze_snapshot(snapshot, longitudinal_axis="z")
sigma_x = result.quantities["rms_x"].value  # metres
epsilon_nx = result.quantities["emit_nx"].value  # metres (rad dimensionless)
issues = result.issues
```

## Metrics and definitions

Each macroparticle has equal weight. For N particles, angle brackets below mean
the population average (sum/N), not the sample estimator sum/(N-1).

| Result | Definition and purpose |
| --- | --- |
| `num_particles` | Count of macroparticles in the unfiltered snapshot. |
| `centroid_x`, ..., `centroid_pz` | Mean of each stored coordinate; beam position and mean momentum. |
| `rms_x`, ..., `rms_pz` | Centered spread sqrt(mean((a-mean(a))²)); beam size and momentum spread, not raw sqrt(mean(a²)). |
| `covariances['phase_space']` | Full centered covariance in order `(x, px, y, py, z, pz)`; preserves cross-plane correlations. Present only if all six coordinates are usable. |
| `emit_nx`, `emit_ny` | sqrt(var(x) var(ux) - cov(x,ux)²), with ux=p_x/(mc), and similarly y. Projected normalized RMS phase-space area, with no factor of pi. |
| `emit_x`, `emit_y` | Same estimator for position and the individual slope x'=px/pz or y'=py/pz. Geometric projected RMS emittance. |
| `alpha_x`, `beta_x`, `gamma_x` (and y) | -cov(x,x')/epsilon, var(x)/epsilon, var(x')/epsilon. Describe ellipse tilt, size and divergence; beta*gamma-alpha²=1 for nonsingular cases. Twiss gamma is not Lorentz gamma. |
| `centroid_x_prime`, `rms_x_prime` (and y) | Mean and centered spread of individual particle slopes. |

`x_normalized`/`y_normalized` and `x_geometric`/`y_geometric` covariance entries
contain the corresponding 2x2 matrices. Axis order and individual units are
explicit on every matrix. Quantities carry a definition and unit string.

## Units, frames and assumptions

- Lengths labelled m/cm/mm are converted to metres in calculations; inputs are
  unchanged. Unsupported/unknown units are retained for raw moments, but cannot
  support an emittance with a known physical unit.
- Momentum must be explicitly labelled `p/(mc)` or OPALX's `#beta#gamma` for
  normalized emittance. An explicit `snapshot.momentum_convention = 'p/(mc)'`
  also permits unknown/dimensionless unit labels after the caller verifies them.
  A conflicting convention blocks optics calculations. Other raw momentum
  moments retain their units.
- Emittance unit `m` means metres with angles dimensionless. Multiply by 1e6
  for the conventional mm mrad number. Twiss alpha is dimensionless, beta is m,
  and gamma is 1/m. No automatic unit conversion occurs during export yet.
- `analyze_snapshot(snapshot)` computes stored-axis moments and normalized
  projections. Passing `longitudinal_axis='z'` additionally requests geometric
  optics and asserts a common position/momentum frame with z longitudinal.
  Every pz must be positive. Slopes are tangent slopes, not arctan angles;
  no paraxial mean-pz substitution is made. No bent-orbit frame is inferred.
- These are projected mechanical-momentum observables, not canonical or coupled
  eigenemittances. Dispersion is not subtracted. Use one particle species for
  optics; mixed `sp` values block optics but leave raw population moments.
- Unequal charges produce a warning: equal-macroparticle results differ from
  charge-weighted bunch moments. Missing/malformed charge data also warns. The
  caller must confirm common species when no species dataset is available.

## Numerical behavior and scope

The implementation centers before forming covariance matrices. Emittance uses
SVD of RMS-scaled centered columns to avoid subtracting nearly equal determinant
terms. A scaled singular-value ratio <=32*float64 epsilon is treated as zero;
zero emittance remains a valid reported quantity, but Twiss is omitted with an
`undefined_twiss` error. No finite-N correction is applied.

Missing, malformed, empty, nonfinite and overflowing coordinates produce issues
with source/step/field context. No particles are dropped. Independent valid
observables remain available. `success` means requested calculations completed,
`partial` means some failed, and `failed` means no coordinate moments could be
computed. Warnings alone do not change success. No longitudinal-axis argument
means geometric optics was not requested. Read status/issues before using values.

`.stat` contains reported summaries and cannot reconstruct a full particle
covariance. Calculations here consume HDF5 snapshots; reported diagnostics stay
separate. Longitudinal Twiss, eigenemittances and charge-weighted moments remain
roadmap items.

## Agent interface, plots and exports

All discovery, reader, calculation, validation and export entry points can be
imported from `postprocess`. The library returns data; agents choose plots and
interpretations. Packaging is still deferred (`PYTHONPATH=src`).

```python
from pathlib import Path
from postprocess import (
    discover_run, select_file, read_stat, read_snapshot, list_snapshots,
    analyze_snapshot, validate_statistics, validate_analysis,
    to_dataframe, results_to_dataframe, write_json, write_statistics_csv,
)

run = Path("output/opalx-simulator/fodo-no-spacecharge")
files = discover_run(run)
stat_file = select_file(files, "statistics")
particle_file = select_file(files, "snapshots")
if stat_file is None or particle_file is None:
    raise FileNotFoundError("This analysis requires statistics and particle dumps")

# Plot reported statistics without changing their original units.
stats = read_stat(files.root / stat_file)
stats_report = validate_statistics(stats)
table = to_dataframe(stats, columns=["s", "rms_x", "rms_y"], validation=stats_report)
ax = table.plot(x="s", y=["rms_x", "rms_y"], ylabel="RMS size [m]")

# Load particles one dump at a time; only small results remain in memory.
results, reports = [], []
for step in list_snapshots(files.root / particle_file):
    snapshot = read_snapshot(files.root / particle_file, step)
    result = analyze_snapshot(snapshot, longitudinal_axis="z")  # Verified for straight FODO.
    results.append(result)
    reports.append(validate_analysis(result, longitudinal_axis="z"))
series = results_to_dataframe(results, validation_reports=reports)
ax = series.plot(x="s", y=["emit_nx", "emit_ny"], ylabel="Normalized emittance [m]")

out = Path("output/postprocess/fodo")
csv_path, metadata_path = write_statistics_csv(stats, out / "statistics.csv", validation=stats_report)
write_json(results[-1], out / "last_snapshot.json", validation=reports[-1])
write_json(series.attrs, out / "series.metadata.json")
series.to_csv(out / "series.csv", index=False)
ax.figure.savefig(out / "emittance.png")
```

Inspect validation issues and skipped checks before interpreting plots. The
metre labels above apply to this FODO fixture; generic statistics keep their
source units in `table.attrs['units']`. Neither adapter converts units or filters
rows. `longitudinal_axis='z'` remains an explicit frame assertion, not a default
for arbitrary simulations. Use `validate_snapshot` for input checks as described
below. Validation is never run implicitly by an exporter.

| Entry point | Output and intended use |
| --- | --- |
| `to_summary(data, validation=None)` | A schema-versioned JSON-compatible dict for model/agent inspection. Accepts statistics, snapshots, calculation results, validation reports, inventories, timing and explicit mappings. |
| `to_dataframe(stats_or_snapshot, columns=None, validation=None)` | Independent copies of original numerical columns, with each column's dtype preserved. Units, source and optional validation are in `.attrs`. |
| `results_to_dataframe(results, validation_reports=None)` | One row per calculation: source, nullable integer step, status, s [m], time [s] and scalar quantities. Use for observable histories and plots. |
| `write_json(data, path, ...)` | Strict UTF-8 JSON on disk; also accepts an already-created summary without wrapping it or losing diagnostics. |
| `write_statistics_csv(table, path, columns=None, validation=None)` | Returns `(csv_path, metadata_path)`. The adjacent `<filename>.metadata.json` carries units, dtypes, source, column descriptions and validation. |

Arrays also remain directly available in `stats.columns`, `snapshot.columns`,
and `result.covariances[name].values`. Use per-column `.to_numpy()` on a DataFrame
when retaining an integer dtype matters; converting a mixed float/integer frame
to one homogeneous array can coerce integer IDs to float.

`results_to_dataframe` preserves input order, failed/partial rows and missing
observables (NaN, never zero). Known snapshot time/path coordinates are retained
by calculation in `AnalysisResult`; unavailable coordinates remain missing.
Quantities with conflicting units/definitions across results are rejected, as
are array-valued quantities in this scalar adapter. Full result summaries,
covariances, issues and assumptions stay in `series.attrs['results']`. No sorting,
resampling or frame alignment is performed. Pandas operations and plain CSV can
discard `.attrs`, so persist metadata separately when exchanging a derived table.

Summaries omit full statistics/particle columns by default, retaining dtype,
shape, units, description, first/last, finite min/max and nonfinite count. Pass
`include_arrays=True` to `to_summary`/`write_json` when full column lists are
needed. Calculated quantities and covariance matrices are always included.
Original reported metadata is retained under `source.attributes`, separate from
calculated quantities; the known incorrect upstream centroid is not repaired.

NumPy scalars/arrays, paths and UTF-8 bytes are converted to JSON-native values.
NaN/infinity become `null`, with their locations and kinds recorded in
`serialization_issues`; original model values are unchanged. `nonfinite='raise'`
rejects nonfinite numbers that would be serialized. This is a serialization
policy, not input validation: omitted arrays may still contain nonfinite cells,
which their descriptors count. Unknown objects or non-UTF-8 bytes raise instead
of silently stringifying. Generic mappings are wrapped under `data`; existing
schema-v1 summaries retain their layout. Integer values are not routed through
float; JSON consumers must themselves support the required integer precision.

CSV uses ordinary column-name headers and retains all numeric rows, including
literal `nan`, `inf` and `-inf` cells. Exported metadata records nonfinite counts
and original dtypes. Keep the sidecar with the CSV and restore dtypes explicitly
when precision matters. Writers create parent directories, serialize metadata
before opening output files, and refuse existing files unless `overwrite=True`.
The CSV and sidecar are not an atomic two-file transaction. Other serialization
or filesystem errors are raised to the caller. Exporting an invalid result is
allowed for diagnosis and never changes its status to success.

## Validation

Validation is a separate, nonmutating stage. Reports contain `issues` with
severity/code/source/step/field, `checks` describing performed checks, and
`skipped` explaining unavailable comparisons. `report.is_valid` means no errors
were found within those checks; warnings and skips remain visible. It does not
establish that the simulation completed, that the physics model is appropriate,
or that every output format was supported. Reader exceptions still indicate
unreadable or unsupported file formats before this stage.

```python
from postprocess import (
    validate_run_files, validate_snapshot, validate_statistics,
    validate_analysis, compare_diagnostics,
)
from postprocess.readers import discover_run, read_stat

files = discover_run("output/opalx-simulator/fodo-no-spacecharge")
file_report = validate_run_files(files)
input_report = validate_snapshot(snapshot, longitudinal_axis="z")
calculation_report = validate_analysis(result, longitudinal_axis="z")
table = read_stat(files.root / files.statistics[0])  # This fixture has one .stat.
statistics_report = validate_statistics(table)
comparison_report = compare_diagnostics(
    snapshot, result, table,
    frame_confirmed=True,  # Explicitly verified for this straight FODO fixture.
)
```

- `validate_run_files` requires statistics and snapshot files by default; pass
  `required=('statistics',)` for a statistics-only run. Multiple candidates warn;
  use discovery's `select_file` to resolve ambiguity before reading. Empty or
  missing requested files error. Timing is optional; `validate_timing` checks
  text availability without interpreting timing numbers or inferring success.
- `validate_snapshot` checks all numeric arrays, six required phase-space fields,
  dimensions, empty/nonfinite data, units/conventions, finite time/path, unique
  integer IDs, positive masses when present, species and macroparticle charges.
  Forward pz is required only when requesting `longitudinal_axis='z'`.
- `validate_statistics` requires t, s and numParticles by default (customizable).
  It checks nonnegative integral counts, nonnegative RMS/emittance/energy/spread
  values, bounded correlations, and time ordering. Decreasing/repeated times
  warn, allowing restart histories to be inspected; path need not increase and
  particle/energy conservation is not assumed.
- `validate_analysis` copies calculation issues, checks requested completeness,
  status, finite scalar observables, units, covariance symmetry/positive
  semidefiniteness, RMS/variance, projected/full covariance agreement, emittance
  determinants and Twiss relations. Singular positive-semidefinite covariance
  is valid. Pass the same longitudinal-axis argument as calculation to check
  geometric/Twiss completeness. These are consistency checks, not an independent
  recomputation of every observable.
- `compare_diagnostics` requires the result's source and step to match the
  snapshot. Without `frame_confirmed=True`, it explicitly skips comparisons.
  Confirmation covers compatible position/momentum frames and population/weight
  conventions; the library cannot infer those for arbitrary lattices/monitors.
  It checks HDF5 centroid/RMS/normalized-emittance attributes and available
  statistics counts, centroids, RMS and normalized emittances. Unknown units are
  skipped with warnings: a statistics momentum unit `1` alone does not establish
  p/(mc). Reported geometric emittance is skipped because the estimator differs.

Default consistency/comparison tolerances are rtol=1e-8 and atol=1e-12 in each
observable's stated canonical units. Covariance symmetry/PSD and determinant
checks use dimensionless correlation scaling; tiny mixed-unit entries must not
hide an invalid covariance. The Twiss identity uses a scaled residual for nearly
singular ellipses. These tolerances are configurable; emittance determinant checks
cannot resolve differences below covariance roundoff in nearly singular cases.

Statistics comparison requires exactly one row within `time_atol=1e-15` seconds;
there is no nearest-row fallback or interpolation. Where both paths are present,
they must agree within `path_atol=1e-6` metres. A missing path is an explicit skip
and leaves time-only matching; an unknown/inconsistent path blocks comparisons.
When the clocks differ or tables combine restarts, resolve that alignment before
comparing. No rows, fields, attributes or calculation statuses are repaired.

## Reference checks

The FODO output identifies OPALX revision
`33d444649e3379b08c4610290d948fa2a4f39c93`. The
[particle writer](https://github.com/OPALX-project/OPALX/blob/33d444649e3379b08c4610290d948fa2a4f39c93/src/Structure/H5PartWrapperForPT.cpp)
copies stored R/P components directly, declares positions in m and normalized
momenta, and does not supply a verified beam-frame transformation. The
[moment implementation](https://github.com/OPALX-project/OPALX/blob/33d444649e3379b08c4610290d948fa2a4f39c93/src/Algorithms/DistributionMoments.cpp)
uses population normalization and reports geometric emittance as normalized
emittance divided by sqrt(mean(gamma)²-1). That estimator can differ from this
library's individual-slope emittance when momenta vary. Integration tests compare
RMS sizes and normalized emittances at matching stored times, and test geometric
optics independently against analytic populations.

Reference-data caveat: the FODO HDF5 `centroid` attribute differs from the ordered
means of its stored x/y/z arrays. Those particle means agree with the time-matched
`.stat` mean columns. Calculated centroids use particles; the original HDF5
attribute is preserved unchanged for inspection. This upstream metadata issue
does not require changing the reader or simulation outputs.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/postprocess -v
```

Local FODO checks skip if generated outputs are absent. No external services or
simulation execution are needed for the synthetic checks.
