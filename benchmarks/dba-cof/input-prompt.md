Construct a geometrically closed electron storage ring consisting of six identical cells, each containing the following elements in order:

- Sector dipole B1: bending angle 30°, radius 2 m
- Drift D1: length 1 m
- Quadrupole Q: length 0.2 m, K1 = +2.84 m⁻² 
- Drift D2: length 1 m
- Sector dipole B2: bending angle 30°, radius 2 m

In every cell, give both drifts (D1 and D2) and the quadrupole Q a rectangular transverse aperture with full horizontal width 1.0 m and full vertical height 0.2 m.

Use ideal hard-edge magnets without fringe fields and an electron beam with reference momentum 0.2505104781131461 GeV/c. No space charge or RF acceleration.

**Perform two closed-orbit calculations:**

1. Nominal initial guess: X = PX = Y = PY = 0.
2. Displaced initial guess: X = Y = 0.1 mm, PX = PY = 0.001.

Choose suitable numerical solver parameters and verify convergence.

Report the closed-orbit coordinates, convergence residuals, stability classification and fractional betatron tunes for both calculations. Compare the results and determine whether both initial guesses converge to the same closed orbit.

If stability is not achieved, adjust the numerical solver parameters and try again.

Make plots if appropriate. Do not inspect or copy an existing valid dba cof input for lattice generation.