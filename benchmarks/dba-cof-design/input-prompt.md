# DBA Ring — Autonomous Quadrupole Strength Design

Construct a geometrically closed electron storage ring consisting of six identical cells, each containing the following elements in order:

- Sector dipole B1: bending angle 30°, radius 2 m
- Drift D1: length 1 m
- Quadrupole Q: length 0.2 m
- Drift D2: length 1 m
- Sector dipole B2: bending angle 30°, radius 2 m

In every cell, give both drifts (D1 and D2) and the quadrupole Q a rectangular transverse aperture with full horizontal width 1.0 m and full vertical height 0.2 m.

Use ideal hard-edge magnets without fringe fields and an electron beam with reference momentum 0.250 GeV/c. No space charge or RF acceleration.

## Design task: Determine the quadrupole strength K1

This is an autonomous accelerator-design task.

The appropriate quadrupole strength K1 is unknown. Treat K1 as a free design parameter, with the same value in all six cells. All other lattice specifications must remain fixed.

**Objective:** Find a suitable K1 that produces a converged, linearly stable closed orbit with an acceptable horizontal and vertical betatron working point.

The desired tunes are not specified. Determine the resulting betatron tunes and prefer a working point sufficiently far from integer and half-integer resonances. Explain why the chosen K1 is suitable.

You may use analytical accelerator physics calculations, numerical methods, parameter scans, and OPALX simulations to determine and validate the quadrupole strength. Choose and justify your approach.

## Closed-orbit validation

For the selected K1, perform two OPALX closed-orbit calculations:

1. Nominal initial guess: X = PX = Y = PY = 0.
2. Displaced initial guess: X = Y = 0.1 mm, PX = PY = 0.001, using OPALX's normalized momentum convention.

Choose suitable numerical solver parameters and verify convergence.

Verify that both calculations converge to the same closed orbit within reasonable numerical tolerances.

If a candidate K1 is unstable or the solver fails, investigate the cause, adjust the focusing strength or numerical settings as appropriate, and repeat. Do not treat changes to solver tolerances as a correction for physical instability.

## Results and reporting

Report focusing strength selection and resulting tunes and simulation outcomes over all attempted simulation runs appropriately. 

Make plots where they help explain the design process or results, for example a tune-versus-K1 scan or stability diagram.

**Important:** Generate the lattice independently from the specifications above. Do not inspect or copy an existing solved DBA COF input file for lattice generation or optimization. You may consult OPALX documentation and generic syntax references.