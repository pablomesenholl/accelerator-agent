# Scientific Plotting Guidelines — Beam Analyzer

This reference defines figure-quality standards for OPALX beam analysis. Follow the user's explicit plotting requirements unless doing so would misrepresent data. Physical definitions and assumptions are in [Physics conventions](physics-conventions.md); library calls are in [Postprocess API](postprocess-api.md).

## 1. Mandatory scientific rules

- Plot only supported, validated quantities under the verified conventions required by `SKILL.md` and the physics reference.
- Label every axis with a physical quantity and its unit, e.g. `Path length $s$ [m]`, `RMS $x$ [mm]`, or `Normalized $\varepsilon_{n,x}$ [mm mrad]`.
- Convert **numerical data** when changing display units; never change only the label. Preserve the source unit and conversion in exported metadata.
- Distinguish path length $s$ from stored position $z$, normalized from geometric emittance, and reported OPALX from recomputed values.
- Do not invent data, zero-fill missing values, silently drop invalid samples, interpolate gaps, smooth curves, or remove outliers without an explicit, documented reason. Show discontinuities where data are missing.
- Show comparisons using common definitions, units, and verified frame/time/path alignment.
- Make figure source, selected snapshot/step, frame assumptions, and any transformations traceable in the analysis script, caption, or saved metadata.

## 2. Preferred visual defaults (adapt when useful)

These are defaults, **not fixed constraints**. Choose a layout that makes the physics clear; override them for dense panels, unusual ranges, or an explicit user style request.

| Element | Default |
| --- | --- |
| Page widths | 3.4 in (single column), 7.0 in (wide/two columns) |
| Aspect | Approximately 1.4–1.7 for ordinary Cartesian plots |
| Typography | 8–10 pt at final display size; math in Matplotlib mathtext |
| Lines / markers | 1.5–2 pt lines; 3–5 pt markers where needed |
| Background | White, unobtrusive axes and light major grid if helpful |
| Output | PDF (vector where practical) and PNG (300 dpi) |
| Style | Colorblind-friendly, consistent between related figures |

- Keep visual encodings and annotations concise; avoid duplicating information across title, legend, and caption.
- Keep margins generous enough for labels, scientific notation, legends, colorbars, and the logo when used. Use `constrained_layout` or another tested layout method.
- Put legends where they do not obscure data; move outside the axes when needed. Omit a legend for a single self-evident trace.
- Use Matplotlib's built-in mathtext by default; do not require an external LaTeX installation merely to draw plots.

## 3. Color and visual encoding

- Keep the following plane colors consistent across figures when suitable:
  - **Horizontal $x$:** blue `#0072B2`.
  - **Vertical $y$:** vermilion `#D55E00`.
  - **Longitudinal:** bluish green `#009E73`.
- For comparisons, distinguish runs using both line style and color (or markers), so the plot remains understandable in grayscale.
- Use solid and dashed styles, or distinct markers, to distinguish **OPALX-reported** from **postprocess-calculated** observables. Identify the mapping explicitly in the legend.
- Use sequential colormaps for magnitude/density and diverging colormaps only for signed or reference-centered quantities. Include a labeled colorbar with units when applicable.
- For overlapping scatter populations, use transparency, smaller markers, or a density representation rather than opaque overplotting.

## 4. Axes, units, and scales

- Prefer readable display units: beam position/size in mm or $\mu$m, path length in m, angles in mrad, and transverse RMS emittance in mm mrad or $\mu$m as appropriate.
- Apply the emittance conversion and Twiss units defined in the physics reference; label dimensionless quantities when ambiguous.
- Choose axis limits to show meaningful variation without hiding outliers. A zero baseline is useful for some positive quantities but is not mandatory for all line plots.
- Use logarithmic scales only when justified by the dynamic range; label them clearly and handle zero/negative values explicitly.
- Prefer standard scientific tick formatting over excessive precision. Avoid dual $y$-axes unless the alternative is clearly less interpretable.
- Do not force equal axis scales in phase space when axes have different physical units; an equal aspect ratio is appropriate only when its meaning is justified.

## 5. Plot-type guidance

### Evolution and beam-envelope plots

- Plot ordered diagnostics against their actual path length $s$ (or time $t$ when requested); do not assume uniform sampling.
- Use continuous lines for genuinely ordered histories; add markers for sparse snapshots. Leave gaps for missing or invalid values.
- For beam envelopes, label centered RMS sizes $\sigma_x$, $\sigma_y$ rather than confusing them with centroids or full widths.

### Transverse phase-space plots

- Label both phase-space axes and their units; state whether momentum or slope ($x'$, $y'$) is shown.
- Use scatter for manageable particle counts and hexbin/2D histograms for dense distributions; label density/count scales and binning where relevant.
- Mark centroids or covariance ellipses only when informative and identify their statistical definition. Avoid presenting an RMS ellipse as the full particle boundary.
- Include the selected dump/step and, if available, $s$ in a caption or metadata.

### Comparisons, histograms, and multi-panel plots

- Use consistent axis ranges, units, normalization, and legend conventions across comparable panels.
- For histograms, record the binning and whether heights represent counts, probability, or density; use common bins for direct comparisons.
- Give each panel a clear purpose; share axes when scientifically appropriate and label panel groups only when needed.

## 6. OPALX logo and attribution

- Use the bundled [OPALX logo](../assets/OPALX-logo.png) discreetly in a figure margin, with unchanged proportions and sufficient separation from axes, labels, and data. The [styling helper](../scripts/plot_style.py) places it above the plotting area by default.
- Resolve the asset relative to the repository/skill location, **not** the analysis working directory. Do not distort, redraw, or download a substitute logo.
- If the asset is missing or unreadable, the helper omits it without failing the analysis. `logo=True` warns when it is missing; an unreadable asset always warns.
- Permit logo-free export for journals, reports, or user requests that disallow figure branding.

## 7. Export, scripts, and quality control

- Use Matplotlib's noninteractive `Agg` backend when no display is available; avoid depending on notebook state or interactive windows.
- Save each final figure as a high-resolution `.png` and a `.pdf` when vector output is appropriate. For very dense point clouds, rasterize only the data artist if needed while keeping text and axes vectorized.
- Use short, descriptive filenames such as `rms_envelope.png`, `normalized_emittance.pdf`, and `phase_space_exit_x.png`; keep naming consistent between formats.
- Use the artifact layout and provenance requirements in `SKILL.md`; retain plotting configuration needed to regenerate figures.
- Open or render each generated figure and verify: nonempty data; correct units; sensible limits; legible labels/legends; no clipped text, overlapping panels, or obscured data; and successful logo placement if used.
- Fix layout failures before delivery. If an essential plotting assumption cannot be verified, omit the misleading figure and explain the limitation.

## 8. Styling helper usage

- [scripts/plot_style.py](../scripts/plot_style.py) provides `apply_style()`, plane `COLORS`, `FIGSIZE_SINGLE`, `FIGSIZE_WIDE`, and `save_figure(fig, path, dpi=300, logo=None, overwrite=False)`. It handles styling and export only; callers choose data, units, and layouts.

Resolve the skill directory from the repository location, not the current working
directory. For example, in a saved analysis script (replace the repository path):

```python
from pathlib import Path
import sys
import matplotlib

matplotlib.use("Agg")  # Before importing pyplot.
import matplotlib.pyplot as plt

skill_dir = Path("/absolute/path/to/accelerator-agent/src/skills/beam-analyzer")
sys.path.insert(0, str(skill_dir / "scripts"))
from plot_style import apply_style, save_figure

apply_style()  # Before creating figures.
# Create and label figures from validated data here.
```

Call `save_figure(fig, analysis_dir / "figures" / "descriptive_name")` after plotting;
it returns `(png_path, pdf_path)`, creates parent directories, and refuses existing
outputs unless `overwrite=True`. It accepts a filename stem or a `.png`/`.pdf` path
and saves both formats at 300 dpi by default (use at least 200 dpi for final PNGs).
`logo=None` includes the asset when available; `logo=False` omits it. The temporary
logo axes are removed after export so repeated saves do not accumulate logos.
Record the helper and asset paths as dependencies in the analysis manifest, and
close figures with `plt.close(fig)` when done.
