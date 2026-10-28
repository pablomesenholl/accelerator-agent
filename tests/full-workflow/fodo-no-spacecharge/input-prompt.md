### Accelerator lattice

Construct one FODO cell with:

- Quadrupole lengths: 0.5 m each.
- Drift lengths: 0.5 m each.
- Normalized quadrupole strengths: K1 = +1.5 m⁻² and −1.5 m⁻².
- Total cell length: 2.0 m, starting at s = 0 m.

### Proton beam and distribution

Use a **250 MeV proton beam** with a bunch charge of 1 nC and **10,000 macroparticles**.

Generate an initial six-dimensional Gaussian distribution with:

- Spatial RMS widths: σx = σy = 1 × 10⁻³ m, σz = 5 × 10⁻³ m.
- Transverse normalized RMS momentum widths: **σpx = 3.48922 × 10⁻⁴**, **σpy = 4.23738 × 10⁻⁴**.
- Longitudinal normalized RMS momentum width: **σpz = 1 × 10⁻⁵**.
- Phase-space correlations: **Corr(x, px) = +0.829278**, **Corr(y, py) = −0.734451**; all other correlations are zero.

Momentum widths are expressed in p/(mc). The transverse values correspond to a beam matched to the periodic linear optics of the FODO cell.

### Tracking and output

Disable space charge and track through the complete 2 m cell.

Use a tracking timestep of 1 × 10⁻¹¹ s, a maximum of 2,000 steps, a phase-space dump frequency of 100, and a statistics dump frequency of 1.

### Task

Do a full analysis workflow of this lattice. Do not inspect or copy existing fodo examples in other subdirectories. Save all generated stuff in this directory. Tell me if you had issue with the workflow, skills, python lib or opalx/magnus etc. Were the workflow instructions efficient?