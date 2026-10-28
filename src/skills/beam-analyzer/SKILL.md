---
name: beam-analyzer
description: Analyze retrieved OPALX beam-dynamics results with the postprocess Python library, produce requested or baseline scientific figures, and save reproducible analysis artifacts. Use after simulation output is available locally, or to analyze an existing OPALX run.
---

# Beam Analyzer

## Scope

Analyze **existing, local OPALX results**. Read the local references at the workflow stages indicated below. Use the project's `.venv` Python interpreter (`uv sync --locked` if setup is needed).

Respect the workflow boundary: the `opalx-simulator` skill handles Magnus execution and output retrieval. Do not submit simulations, modify source data or OPALX inputs, or change reusable library/skill code to fulfill an ordinary analysis request. A final LaTeX/PDF report belongs to a separate reporting skill.

## Inputs and outputs

- **Input:** a local simulation-results directory (normally retrieved through Magnus), plus any user-requested observables, plots, comparison runs, or analysis constraints.
- **Output:** figures, reproducible analysis script(s), relevant derived data, a short scientific summary, and an artifact manifest. Report incomplete or unsuccessful analysis explicitly.

Write to a **new** `output/postprocess/<run-id>/<analysis-id>/` directory, outside the raw simulation directory:

```text
scripts/analysis.py       # Executable, reproducible analysis and plotting
figures/                  # Plots: .png and, where practical, vector .pdf
data/                     # Derived CSV/JSON plus units/metadata sidecars
analysis_summary.md       # Key observations, numerical values, limitations
manifest.json             # Sources, selections, assumptions, products, status
```

Use descriptive, stable filenames; do not silently overwrite a previous analysis. Keep source files read-only. Record paths to originals rather than copying large particle dumps.

## Workflow

### 1. Discover and check the run

Before writing analysis code, read the [Postprocess API](references/postprocess-api.md) for reader, calculation, validation, and export usage.

1. Confirm the results directory exists and identify relevant files using `discover_run` and `select_file`. Inspect available `.stat` statistics and HDF5 snapshot steps with `read_stat` and `list_snapshots` as needed. Never guess a file, step number, or column name.
2. Check run/job completion separately if Magnus result information is available; the existence of data files does not prove a successful simulation.
3. Use `validate_run_files` with requirements appropriate to the task (e.g., statistics-only analysis need not require snapshots). Run `validate_statistics` and/or `validate_snapshot` on data actually used. Inspect `issues`, `checks`, and `skipped`, not just `is_valid`.

### 2. Choose the analysis

Before calculating or interpreting particle observables, read [Physics conventions](references/physics-conventions.md) for coordinate frames, momentum conventions, definitions, and interpretation limits.

- **Specific request:** prioritize exactly what the user asks. Select additional diagnostics only if useful to answer it; keep them clearly distinguished.
- **Open-ended request:** start with a compact baseline, insofar as validated data permit:
  - RMS horizontal/vertical beam sizes versus path length (`s`), normally from `.stat`.
  - Normalized transverse RMS emittance versus `s` where enough particle snapshots are available.
  - Horizontal/vertical phase-space distributions from the last available snapshot; call it an exit snapshot only if its location is verified. Use `(x, x')` / `(y, y')` only if the frame is verified, otherwise use explicitly labeled stored position/momentum coordinates.
- Adapt plots to the physics model (e.g., centroid motion, losses, energy evolution, comparisons), and omit diagnostics that are unavailable or misleading. Do not generate a large fixed plot catalog.
- Prefer `.stat` for high-resolution reported histories and HDF5 snapshots for particle-level distributions and newly calculated observables. Do not present sparse snapshot histories as dense trajectories.

### 3. Calculate with the Python library

Use existing `postprocess` readers, calculations, validations, and exporters rather than reimplementing centroids, spreads, covariance matrices, emittances, or Twiss parameters. Follow its status and unit metadata.

Call `analyze_snapshot(snapshot)` for raw moments and supported normalized projections. **Only** pass `longitudinal_axis="z"` to `analyze_snapshot`, `validate_snapshot`, and `validate_analysis` after verifying the common coordinate frame and positive longitudinal momenta; it enables slope-based geometric emittance and Twiss quantities, not longitudinal Twiss. For curved lattices or ambiguous frames, do not assert this convention. Compare reported and calculated diagnostics with `compare_diagnostics` only when its frame/population matching assumptions and time/path alignment are verified.

Do not infer unknown units, momentum normalization, species, charge weighting, or reference frames. Distinguish OPALX-reported statistics from the library's calculated quantities; their estimators can differ. Never replace absent/invalid data with zero, silently discard failed snapshots, or conceal warnings. Process large HDF5 files one snapshot at a time and export only data needed for the analysis.

### 4. Produce scientific figures

Before creating figures, read the [Plotting guidelines](references/plotting-guidelines.md) for layouts, styling, unit conversions, export, and logo usage. Choose plots suited to the scientific question:

- Label quantities and units, convert numerical values consistently, and distinguish planes, runs, and reported-versus-calculated results.
- Use [scripts/plot_style.py](scripts/plot_style.py) for headless Matplotlib styling and PDF/PNG export. It includes the bundled [OPALX logo](assets/OPALX-logo.png) by default; use `logo=False` for unbranded figures.
- Save final PNGs at least 200 dpi and PDFs where suitable. Inspect rendered figures before delivery using the reference's quality checks.

### 5. Save and communicate results

Save the script that produced the figures and ensure it can be rerun using local source paths. Export only useful derived tables or summaries, retaining the relevant unit/definition metadata (for example, the CSV sidecar or `series.attrs` metadata in JSON). Do not rely on pandas `.attrs` surviving CSV export.

Write `analysis_summary.md` with: analysis objective; sources and selected snapshot(s); key measured/derived trends or values **with units**; notable anomalies; assumptions and validation failures/skips; and limits on interpretation. Keep it concise and separate observation from hypothesis. In `manifest.json`, record source paths, available job ID if known, analysis script, figure/data filenames, applied conversions, frame assumptions, validation outcome, and overall analysis status.

Return links/paths to the generated figures and analysis directory and briefly explain the findings. Clearly state which requested tasks could not be completed and why; do not claim simulation success or physical validity solely from passing numerical checks.

## Failure handling

If a required output, field, unit, or frame convention is missing, perform the supported subset and document the skipped analysis. If validation fails, do not present affected quantities as trustworthy; preserve diagnostic context. Fix plotting or script errors without altering raw simulation data or silently weakening validation. Do not rerun OPALX automatically.
