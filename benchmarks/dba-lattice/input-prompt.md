# Zero-current tune matching in a six-cell double-bend ring

Use the Hamiltonian and coordinate conventions in [theory.md](theory.md) and the baseline cell in [cell.json](cell.json). Work from these inputs and the accelerator-agent workflow.

## Reconstruct the baseline

Build the six-cell hard-edge ring for protons at 2.5 MeV kinetic energy. Use the baseline values in `cell.json` exactly for this step. Compute the element, cell, and one-turn linear maps in the specified canonical coordinates. Report the circumference, position and tangent closure, map symplecticity residual, entrance periodic horizontal dispersion and slope, and full horizontal and vertical tunes in oscillations per turn.

## Match the tunes

At zero current, match the full ring tunes to **Qx = 0.800** and **Qy = 1.700**, each within **0.001**. Choose your own numerical method. Vary only these two parameters, shared across all six cells:

- The common length of the two drifts, **0.95 to 1.10 m**. The baseline value of 1.00 m in [cell.json](cell.json) is a starting value.
- The central quadrupole focusing magnitude **g**, from **2.70 to 3.00 m⁻²**, with **kx = −g** and **ky = +g**. The baseline value of 2.84 m⁻² in [cell.json](cell.json) is a starting value.

Keep the beam energy, bend geometry and strengths, quadrupole length, element order, and sixfold symmetry fixed. The circumference may change. Require closed reference geometry and transversely linearly stable optics. Recover the full tune branches from the cell optics or the phase advance around the ring.

## Verify in OPALX

Generate the matched OPALX deck. Use hard-edge magnets, zero space charge, and no RF. Give each drift and quadrupole a rectangular aperture with full widths of 1.0 m horizontally and 0.2 m vertically.

Use the accelerator-agent workflow to validate the final deck and run OPALX's closed-orbit finder (COF) through Magnus. Confirm that COF converges, reports transverse linear stability, and returns both full tunes within 0.001 of the targets. Record the closure residuals, the full tunes, and their differences from the Hamiltonian model. If full tunes are unavailable, report the COF diagnostic and mark the tune verification incomplete.

Save the reconstructed baseline machine and maps, the matched cell and ring geometry, the matching script or calculation.

Do **not** inspect and copy existing files that might contain the calculations, results or inputs for this study.