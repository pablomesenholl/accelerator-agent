### Accelerator lattice

Construct one FODO cell with:

- Quadrupole lengths: 0.5 m each.
- Drift lengths: 0.5 m each.
- Normalized quadrupole strengths: K1 = +1.5 m⁻² and −1.5 m⁻².
- Total cell length: 2.0 m, starting at s = 0 m.

The cell sequence should be: Focusing quadrupole, drift, defocusing quadrupole, drift.

### Proton beam and distribution

Use a **250 MeV proton beam** with a total bunch charge of **1 nC**.

Generate an initial six-dimensional Gaussian distribution with:

- Spatial RMS widths: σx = σy = 1 × 10⁻³ m, σz = 5 × 10⁻³ m.
- Longitudinal normalized RMS momentum width: σpz = 1 × 10⁻⁵.
- Transverse momentum distributions matched to the periodic linear optics of the FODO cell **without space charge**.

Determine the appropriate transverse momentum spreads and position-momentum correlations from the periodic Twiss parameters. Assume no additional phase-space correlations.

### Tracking and output

Include **3D space-charge effects** and track the proton bunch through the complete 2 m FODO cell.

### Task

Perform a complete simulation workflow, including setup, execution, and analysis of the beam dynamics.

Do not inspect or copy existing FODO examples in other subdirectories.