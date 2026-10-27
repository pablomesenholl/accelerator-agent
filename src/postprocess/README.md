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
separate. General validation, exports, longitudinal Twiss, eigenemittances and
charge-weighted moments remain roadmap items.

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
