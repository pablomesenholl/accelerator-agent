# FODO input generation and validation

Status: **PASS under the current lattice-validator policy**, which explicitly
permits skipping native parser validation. This is not an OPALX parser or runtime
certification. No simulation was launched.

- Simulation directory: `tests/lattice-validator/fodo-no-spacecharge/input`
- Main input filename: `FODO-no-spacecharge.in`
- Original specification: `input-prompt.md` in this directory.
- Syntax reference: `src/skills/lattice-generator/references/opalx-input-reference.md`.

## Generation

Prepared a self-contained single-file input using the existing matching FODO
example from `tests/lattice-generator/fodo-no-spacecharge/input/`, inspected
against the requested specification and local reference. No auxiliary input
files are required. Particle sampling is configured for future OPALX execution;
particles have not been sampled during preparation.

The cell contains QF, D1, QD, D2 at entrances 0, 0.5, 1.0, 1.5 m,
respectively, each 0.5 m long. Quadrupole K1 values are +1.5 and -1.5 m^-2.
The input preserves the supplied beam charge, particle count, six RMS widths,
two correlations, timestep, step limit, and diagnostic frequencies exactly.

The 250 MeV specification is interpreted as proton kinetic energy, 0.250 GeV.
The special global P0 is defined before the magnets as
`sqrt(kinetic_energy*(kinetic_energy+2.0*PMASS))`, where PMASS is the built-in
proton rest energy. The beam uses `PC=P0`; no competing energy attribute is set.
The reference momentum is approximately 0.729134 GeV/c.

Technical choices: fixed seed 123456789, version selector 10900, HDF5 output
enabled, RF autophase disabled, and one-shot injection centered at the origin
at time zero with zero source offsets. The NONE solver has an 8-by-8-by-8 mesh,
all parallel FFT flags enabled, and all OPEN boundaries, as required by the
documented constructor even without self-fields. No new physical effects,
apertures, or matching adjustments were added.

## Validation layers

1. **Native syntax: SKIPPED.** The lattice-validator skill Step 2 currently
   permits this because parser-only OPALX validation is not implemented.
   No Magnus job or tracking run was used as a substitute.
2. **Structural and semantic checks: PASS.** Reviewed syntax against the local
   reference, definition ordering, explicit element placement, complete
   distribution/source/source-list/beam connections, line and solver references,
   positive lengths and tracking settings, allocation matching 10,000 particles,
   and the complete TRACK/RUN/ENDTRACK/QUIT block. No external files are referenced.
3. **Specification consistency: PASS.** Confirmed all requested lattice, beam,
   Gaussian, correlation, no-space-charge, tracking and diagnostic settings.
   CORR contains 15 entries; x-px is entry 1 and y-py is entry 10;
   all other entries are zero. ZSTART is 0 m and ZSTOP is 2 m.
4. **Basic physics consistency: PASS.** Checked proton charge, kinetic-to-momentum
   conversion, consistent beam and magnet normalization, normalized momentum
   units, and disabled self-fields. Correlation eigenvalues are
   0.170722, 0.265549, 1, 1, 1.734451, 1.829278, all positive.
   With beta approximately 0.613608, reference transit through 2 m takes
   approximately 1,087 timesteps of 1e-11 s, within the 2,000-step budget.

The numerical sanity checks and assertions against the generated input ran
successfully using the project `.venv/bin/python`. They are not a native parser.
The supplied matched-beam parameters were preserved; periodic matching was not
independently recomputed. Finite-sample moments and actual tracking behavior have
not been measured.

Blocking errors: none found. Warning: native parsing remains untested.
Generation and current-policy validation completed. Simulation and analysis
were not performed, as requested. The paths are suitable for a later simulator
handoff under this validation policy; no handoff was executed.
