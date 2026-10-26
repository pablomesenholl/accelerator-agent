# Accelerator Physics Study Guide — OPALX DBA Closed-Orbit Benchmark

**Project:** `accelerator-agent`  
**Focus:** Transverse beam dynamics, linear optics, closed orbits, and validation of the `dba-ring-cof-1` benchmark  
**Suggested duration:** 5 focused study days, alongside manual OPALX runs

## Goal

Learn enough accelerator physics to **understand, run, interpret, and independently validate** the DBA closed-orbit-finder (COF) simulation in OPALX. This is a targeted study plan, not a full accelerator-physics course.

By the end, you should be able to:

1. Explain what dipoles and quadrupoles do to a particle trajectory.
2. Construct and multiply linear transfer matrices in beamline order.
3. Explain periodic beam optics, the reference/closed orbit, and betatron tunes.
4. Distinguish a *closed* orbit from a *stable* orbit.
5. Interpret the COF result: orbit coordinates, closure residual, one-turn matrix, eigenvalues, and stability diagnostics.
6. Compare OPALX's one-turn map with an independent analytical matrix model and document numerical limitations.

## 1. Recommended study materials

### Primary textbook — S. Y. Lee, *Accelerator Physics*, 4th ed.

- **Available within this project:** `Accelerator Physics Book.pdf` (provided project resource).
- Publisher/book reference: <https://doi.org/10.1142/11111>
- **Read selectively:** Chapter 2 (*Transverse Motion*) is much more relevant to this benchmark than the remaining chapters.
- The section and page numbers below refer to the **printed book pages**, which may differ from the PDF viewer's page indices.

### Introductory lecture material — CERN Accelerator School

- Wolfgang Hillert, *Transverse Linear Beam Dynamics*: <https://indico.cern.ch/event/1622828/contributions/7202769/>
- Bernhard Holzer, introductory transverse beam-dynamics lectures:
  - [Part I](https://videos.cern.ch/record/3025953)
  - [Part II](https://videos.cern.ch/record/3025951)
  - [Part III](https://videos.cern.ch/record/3025960)

**Use:** Start with lectures to build intuition about magnets, focusing, trajectories, and periodic focusing before studying detailed derivations.

### Alternative structured course — US Particle Accelerator School (USPAS)

- Eric Prebys, *Fundamentals of Accelerator Physics* (2018 course materials): <https://prebys.physics.ucdavis.edu/misc/uspas_2018/>
- Particularly relevant: **Lecture 3 — Transverse Motion**, **Lecture 4 — Off-Momentum Particles**, and **Lecture 6 — Closed Orbit Distortions**.

### Implementation and benchmark references

- **OPALX user/physics manual:** `The-OPALX-Universe.pdf` (provided project resource); online documentation: <https://opalx-project.github.io/opalx-manual/>
  - §13.4: **Closed Orbit Finder**.
  - §20.4: **Closed-orbit command** (documented as experimental in the referenced manual).
- **DBA benchmark:** [OPALX PR #553 — Ring and Cyclotron Capabilities, Part 1](https://github.com/OPALX-project/OPALX/pull/553), especially the `dba-ring-cof-1` benchmark, analytic reference, results, and limitations sections.
- **COF source implementation:** <https://github.com/OPALX-project/OPALX/blob/master/src/Track/CofCmd.cpp>

## 2. Priority topics and reading map

| Order | Topic | Key questions | S. Y. Lee, Chapter 2 |
|---|---|---|---|
| 1 | Coordinates, magnetic elements, and transverse motion | What is the reference trajectory? How do dipoles bend and quadrupoles focus? | §§ I.1–I.4, pp. 34–40 |
| 2 | Transfer matrices and FODO optics | How are element maps composed? How can linear stability be determined? | §§ II.1–II.3, pp. 44–52 |
| 3 | Courant–Snyder optics and emittance | What do $\alpha$, $\beta$, $\gamma$, phase advance, and emittance mean? | §§ II.2–II.7, pp. 47–62 |
| 4 | Periodic orbits and dispersion | What changes in rings and for off-momentum particles? What does *achromatic* mean? | §§ IV.1–IV.4, pp. 122–134 |
| 5 | Numerical COF and stability | How does OPALX solve for a periodic orbit? What do the Jacobian eigenvalues mean? | OPALX §§13.4, 20.4; PR #553 |

### Concepts to learn carefully

#### Linear transverse motion

In an uncoupled linear approximation, transverse motion relative to a reference trajectory is described by Hill's equation:

$$
x''(s) + K_x(s)x(s) = 0.
$$

A linear element advances the transverse coordinates using a transfer matrix. In a simple horizontal model,

$$
\begin{pmatrix}x\\x'\end{pmatrix}_{\!\mathrm{out}}
= M_x
\begin{pmatrix}x\\x'\end{pmatrix}_{\!\mathrm{in}}.
$$

For a drift of length $L$,

$$
M_{\mathrm{drift}} = \begin{pmatrix}1&L\\0&1\end{pmatrix}.
$$

**Study exercise:** Derive the drift matrix, then find the thick-quadrupole maps from the textbook and multiply them in the correct traversal order to construct a FODO-cell map.

#### Periodic motion, phase advance, and tune

A stable uncoupled one-period matrix typically has eigenvalues on the unit circle. For a $2\times2$ symplectic map with $|\operatorname{Tr}M|<2$,

$$
\cos\mu = \frac{\operatorname{Tr}M}{2},
$$

where $\mu$ is the phase advance per period. For a complete ring, the fractional tune is related to the one-turn phase advance by $\nu=\mu/(2\pi)$, modulo integer and branch ambiguities.

**Study exercise:** Calculate the horizontal and vertical phase advances of a simple periodic FODO lattice and explain why focusing in one plane typically accompanies defocusing in the other.

#### The closed orbit

Let $\mathcal T$ denote the one-turn map on the chosen transverse section. A closed orbit is a fixed point:

$$
\mathcal T(\mathbf u^*)=\mathbf u^*,
\qquad
F(\mathbf u)=\mathcal T(\mathbf u)-\mathbf u=0.
$$

In OPALX's current COF method, the four-dimensional section state is

$$
\mathbf u=(x,p_x,y,p_y)^T,
$$

with positions in metres and **mechanical momenta normalized by $mc$**. The numerical solver uses Newton-type iterations, with finite-difference estimates of the map Jacobian.

**Key distinction:** Finding a fixed point does **not** establish that nearby trajectories remain bounded.

#### Stability of the closed orbit

The linearized one-turn map is

$$
M=\left.\frac{\partial\mathcal T}{\partial\mathbf u}\right|_{\mathbf u^*}.
$$

Its eigenvalues describe the local response to small perturbations. For ideal stable, uncoupled oscillatory modes, the eigenvalues lie on the complex unit circle and their arguments encode fractional tunes. Numerical errors, coupling, unstable modes, and coordinate conventions make interpretation more delicate in general.

**Study exercise:** Plot the eigenvalues of an example $4\times4$ one-turn matrix in the complex plane together with the unit circle. Explain what OPALX's stability classification does and does not establish.

#### Dispersion and the DBA lattice

Dipole bending makes the closed trajectory sensitive to momentum. Dispersion describes, to first order, the transverse response of the orbit to a change in reference momentum. A *double-bend achromat* is a class of optical arrangement designed to control dispersion, but **the stable `dba-ring-cof-1` settings in PR #553 are explicitly non-achromatic**. Do not infer zero dispersion from the benchmark name.

## 3. Five-day study plan

### Day 1 — Physical intuition

**Read/watch:** CERN transverse beam-dynamics lectures (start with Parts I–II).  
**Focus:** magnetic rigidity, dipole and quadrupole fields, reference trajectories, focusing and defocusing.  
**Deliverable:** A half-page explanation or annotated sketch of why alternating-gradient focusing works.

### Day 2 — Transfer matrices and FODO

**Read:** Lee §§II.1–II.3 (and §§I.3–I.4 if needed).  
**Focus:** matrix multiplication order, linear stability, phase advance, and periodic FODO optics.  
**Deliverable:** A short handwritten calculation or Python notebook that constructs a drift/quadrupole/FODO transfer matrix and tests $|\operatorname{Tr}M|<2$ in each uncoupled plane.

### Day 3 — Rings, periodic optics, and dispersion

**Read:** Lee §§II.2–II.7 and §§IV.1–IV.4; optionally USPAS lectures on off-momentum motion and closed-orbit distortions.  
**Focus:** closed orbit, Twiss functions, one-turn map, tune, dispersion, and achromaticity.  
**Deliverable:** Explain in your own words the difference between *closed orbit*, *linear stability*, *betatron tune*, and *achromat*.

### Day 4 — Understand the OPALX COF method

**Read:** OPALX manual §§13.4 and 20.4; `dba-ring-cof-1` and analytical-reference sections of PR #553.  
**Focus:** COF input attributes, Newton iterations, finite-difference steps, numerical integrators, one-turn matrix, and JSON output.  
**Deliverable:** Annotate the benchmark input and describe the meaning and units of every important COF output field.

### Day 5 — Run and independently analyze the benchmark

**Do:** Execute the documented DBA COF case manually. Request JSON output and load it in Python.  
**Focus:** closure residual, matrix, eigenvalues, stability, fractional tunes, and sensitivity to numerical settings.  
**Deliverable:** A reproducible analysis script/notebook with one comparison table, an eigenvalue plot, and a short discussion of agreement and numerical limitations.

## 4. Benchmark-specific checklist — `dba-ring-cof-1`

PR #553 describes a **six-cell** ring with the sequence **B1–D1–Q–D2–B2** per cell. The documented stable hard-edge benchmark uses:

| Parameter | Value |
|---|---|
| Two sector bends per cell | Radius $2\,\mathrm m$, angle $30^\circ$ each, $L=\pi/3\,\mathrm m$; hard-edge setting |
| Two drifts per cell | $1\,\mathrm m$ each |
| One quadrupole per cell | $L=0.2\,\mathrm m$, $K_1=+2.84\,\mathrm{m^{-2}}$ in the stated OPALX electron convention |
| Beam | Electron, $PC=0.2505104781131461\,\mathrm{GeV}/c$ |
| Ring circumference | Approximately $25.76637\,\mathrm m$ |
| COF integrator and timestep | DOP853, $DT=5\times10^{-12}\,\mathrm s$ |
| Reference fractional tunes | Approximately $0.229892431$ and $0.310463603$ |

These are **specific settings from PR #553**, not universal DBA parameters. Check that the source version and input file match the benchmark before comparing numbers.

### COF outputs to understand

The optional `OUTPUT="closed-orbit.json"` attribute writes a structured result file. In the current COF implementation, key fields include:

| JSON field | Meaning / use |
|---|---|
| `converged` | Closed-orbit solver success flag |
| `coordinates` | Four-dimensional fixed-point coordinates |
| `residual` | Difference between returned and initial transverse coordinates |
| `matrix` | Linearized one-turn $4\times4$ map |
| `eigenvalues` | Complex eigenvalues, encoded as real/imaginary pairs |
| `stability` | Eigenvalue-based stability classification |
| `fractional_modes` | Fractional mode phases/tunes and complementary values where available |
| `dt_s` | Integration time step |
| `relative_energy_drift` | Energy-consistency diagnostic |

Consult the current OPALX source/manual for the precise field schema. If no `OUTPUT` attribute is specified, the COF command does **not** automatically create a JSON report.

### Manual analysis acceptance criteria

- [ ] COF finishes and reports convergence.
- [ ] The orbit-closure residual is recorded with correct units and numerical tolerance.
- [ ] The full one-turn matrix is saved and its coordinate convention identified.
- [ ] Its eigenvalues and OPALX stability classification are interpreted correctly.
- [ ] Fractional tunes are compared with the PR's reference values without overclaiming mode or integer-tune identification.
- [ ] The numerical and analytical matrices are compared **in the same coordinates**. PR #553 uses $(x,x',y,y')$ for the stated analytic comparison; OPALX COF reports mechanical momentum coordinates $(x,p_x,y,p_y)$.
- [ ] At least one integration-timestep or finite-difference-step sensitivity check is performed.
- [ ] The simulation revision, input file, relevant settings, scripts, raw outputs, and plots are retained.

**Important limitation:** The fixed-energy COF benchmark is not a demonstration of self-consistent ring space-charge matching or RF-synchronous six-dimensional closure. PR #553 also distinguishes COF accuracy from subsequent particle `TRACK` accuracy; successful COF-to-TRACK initialization does not guarantee high-accuracy multi-turn tracking.

## 5. Connection to the `accelerator-agent` project

This study should produce an **independent manual reference** against which a Codex/Claude Code workflow can be checked.

1. **Manual baseline:** verified OPALX input and COF JSON output.
2. **Independent analysis:** a small Python script that reads the JSON, constructs arrays, performs coordinate conversions, evaluates eigenvalues, makes plots, and compares reference results.
3. **Reusable infrastructure:** extract only well-defined, independently testable operations (data reading, units, coordinates, and common matrix calculations) into a small postprocessing library.
4. **`beam-analyzer` skill:** teach the agent how to use the library, consult domain references, write benchmark-specific analyses, and report scientific caveats.
5. **End-to-end test:** ask an advanced coding agent to reproduce the analysis using the same OPALX outputs, then compare it with the manual baseline.

**Design principle:** Keep parsing and critical coordinate/units handling deterministic. Allow the agent to select scientific analyses and write problem-specific plotting code. A successful simulation and an attractive plot are not, by themselves, physics validation.

## 6. What can wait until later

For the initial DBA COF study, detailed 3D space-charge theory, RF acceleration, nonlinear resonances, dynamic aperture, and large parameter scans are **not prerequisites**. Study these when the project progresses beyond the fixed-energy, linear-optics/closed-orbit benchmark.

---

## Completion criterion

You are ready to implement the first `beam-analyzer` workflow when you can independently answer:

> *What does OPALX's DBA closed-orbit solution mean physically, how does its one-turn matrix determine linearized stability, and how closely does it agree with a separately constructed reference at documented numerical settings?*

If you can answer that with a reproducible input, script, numerical comparison, and plots, the foundational learning phase is complete.
