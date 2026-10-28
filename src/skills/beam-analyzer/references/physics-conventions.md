# Physics Conventions — Beam Analyzer

Use this reference when interpreting OPALX diagnostics and `postprocess` results. It defines **required physical assumptions and safeguards**, not a complete theory of accelerator optics. Never infer a convention solely from a variable name or a plausible numerical value.

## 1. Coordinates and reference frames

- `x`, `y`, `z`: particle positions in the **stored coordinate frame**. Interpret `x`, `y` as transverse and `z` as longitudinal only after verifying that frame.
- `s`: path length along the reference trajectory; **not** the particle coordinate `z`. Use `s` for lattice evolution only when available from trusted diagnostic metadata.
- `(px, py, pz)`: components of stored **mechanical** momentum. Do not silently interpret them as canonical momenta, particle angles, or momentum deviations.
- A bent beamline or rotated output frame may not have `z` aligned with the local direction of motion. The library does not infer or perform beam-frame rotations.
- Set `longitudinal_axis="z"` only after verifying that particle positions and momenta share a frame with `z` longitudinal and $p_z>0$ for every particle. Otherwise omit it and restrict analysis to supported stored-coordinate observables.
- Do not confuse **longitudinal beam dynamics** (coordinates within the bunch) with evolution **along the accelerator** (the path variable `s`).

## 2. Momentum, slopes, and emittance units

- OPALX particle momentum may be stored as dimensionless $u_i=p_i/(mc)$ (also labeled `#beta#gamma`). Confirm this from reader metadata or verified source information; a unit label of `1` alone is insufficient.
- For a verified common frame with longitudinal `z`, the library uses **individual-particle tangent slopes** $x'=p_x/p_z$ and $y'=p_y/p_z$; it does not use $\arctan(p_x/p_z)$ or replace each $p_z$ by its mean.
- Projected normalized transverse RMS emittance requires verified normalized-momentum units:

  $$\varepsilon_{n,x}=\sqrt{\det\operatorname{Cov}(x,u_x)}.$$

- Projected geometric transverse RMS emittance requires validated slopes:

  $$\varepsilon_x=\sqrt{\det\operatorname{Cov}(x,x')}.$$

  The corresponding formulas apply in the vertical plane.
- The familiar $\varepsilon_n\approx\beta_{\mathrm{rel}}\gamma_{\mathrm{rel}}\varepsilon_{\mathrm{geom}}$ is an **approximation** for a paraxial beam with sufficiently small relative momentum spread, not an exact identity between these two numerical estimators.
- The library represents transverse emittance in metres (radians dimensionless): $1\,\mathrm{m}=10^6\,\mathrm{mm\,mrad}$ numerically. State **normalized** or **geometric** explicitly; never treat them interchangeably.
- The library's particle-slope geometric emittance may differ from OPALX's reported geometric-emittance estimator. Compare only quantities with matching definitions.

## 3. Beam moments, covariance, and Twiss parameters

- For `N` equal-weight macro-particles, $\langle a\rangle=\frac{1}{N}\sum_i a_i$ and $\sigma_a=\sqrt{\langle(a-\langle a\rangle)^2\rangle}$. RMS spreads are **centered**, not $\sqrt{\langle a^2\rangle}$.
- Population covariance is $\operatorname{Cov}(a,b)=\langle(a-\langle a\rangle)(b-\langle b\rangle)\rangle$ (normalization $N$, not $N-1$). A covariance matrix contains the spreads and correlations of its explicitly ordered axes.
- For a verified transverse pair $(x,x')$, let $\varepsilon_x=\sqrt{\det\Sigma_x}$. The geometric Twiss parameters are:

  $$\beta_x=\frac{\operatorname{Var}(x)}{\varepsilon_x},\qquad
  \alpha_x=-\frac{\operatorname{Cov}(x,x')}{\varepsilon_x},\qquad
  \gamma_x=\frac{\operatorname{Var}(x')}{\varepsilon_x}.$$

- For defined, nonsingular optics, $\beta_x\gamma_x-\alpha_x^2=1$. Twiss $\alpha_x$ is dimensionless, $\beta_x$ has units of metres, and $\gamma_x$ has units of inverse metres; **Twiss gamma is not Lorentz gamma**.
- Twiss parameters are undefined for zero or numerically singular emittance. Do not fabricate or extrapolate them.
- These are **projected RMS** emittances and Twiss parameters, not beam acceptance, canonical eigenemittances, or dispersion-corrected intrinsic emittances.
- `longitudinal_axis="z"` enables **transverse slope-based** geometric optics; it does **not** request longitudinal Twiss or conventional longitudinal emittance (e.g. in eV·s).

## 4. Statistical and numerical assumptions

- The library uses **equal macro-particle weighting** without filtering particles. If macro-particle charges differ, these moments are not necessarily charge-weighted bunch moments; disclose that distinction.
- Verify particle species and momentum conventions before interpreting optics. Mixed species or an unverified common frame can invalidate emittance and Twiss interpretations.
- A changing surviving-particle population can change centroids, RMS spreads, and projected emittances even without the same particles experiencing intrinsic emittance growth. Inspect particle counts and losses.
- `.stat` files provide OPALX-reported summaries; they do not reconstruct the full particle covariance or phase-space distribution. Use particle snapshots for those quantities.
- Different `.stat` rows and HDF5 snapshots may sample different positions or times. Match sources, frames, definitions, and **time/path coordinates** before numerical comparisons; do not align by row or dump index alone.
- Validation errors invalidate affected conclusions. Warnings and **skipped checks** must remain visible: passing performed consistency checks alone does not establish simulation success or physical validity.
- Missing, nonfinite, or undefined observables are **unavailable**, not zero. Do not silently remove snapshots, rescale values, or change assumptions to make checks pass.

## 5. Physical interpretation and reporting limits

- Beam-size oscillations in a FODO channel may reflect normal quadrupole focusing/defocusing; distinguish envelope evolution from centroid motion and emittance changes.
- Under ideal **linear, uncoupled, lossless** transport at fixed energy, geometric projected transverse RMS emittance is expected to be conserved. Under suitable ideal acceleration, normalized emittance is approximately conserved.
- Observed emittance changes may involve nonlinear fields, space charge, coupling, dispersion, particle loss, sampling, or numerical artifacts; **do not assign a cause from a trend alone**.
- Changes in centroids may indicate coherent motion, steering, offsets, or frame changes. Check the reference trajectory and simulation setup first.
- Separate **observation** (measured change and units), **interpretation** (plausible mechanism), and **evidence** (comparison, validation, or model details). State material assumptions and limitations.
- When a requested interpretation exceeds the library's verified conventions or available data, report the limitation and identify the additional information needed; do not invent a physical result.
