# OPALX Input Reference

**Local working reference for the `lattice-generator` skill.** Use this document to construct OPALX `.in` files and their supporting input directories. It summarizes the **current OPALX** language and commonly used accelerator/beam/tracking interfaces; it is not a fixed lattice template, a complete catalog of every feature, or an input validator.

## 1. Purpose, scope, and documentation priority

**Read this reference first.** If it covers the requested input, generate the files directly: **do not fetch the full manual or browse GitHub for every generation task**. Use the official documentation only when a requested feature is absent, ambiguous, experimental, or suspected to have changed. Consult maintained regression inputs and source code if the official documentation still leaves uncertainty. Never infer implementation support solely from a legacy OPAL example or from parser registration.

**Generation boundary:** describe and write the requested `.in` and auxiliary files. Do not run OPALX, Magnus, parsing/physics checks, or numerical tests. Input validation belongs to `lattice-validator`; execution belongs to `opalx-simulator`.

**Source basis:** the supplied 456-page *The OPALX Universe* PDF, primarily its sections explicitly marked **OPALX**; checked against selected pages of the [maintained OPALX manual source](https://github.com/OPALX-project/opalx-manual) (October 2026). References to manual pages in this document mean **PDF page numbers**. Exact chapters and URLs are collected in §14.

## 2. Anatomy of an OPALX input

A typical particle-tracking input contains the following **logical components**, although their order may vary when name dependencies are satisfied:

| Component | OPALX construct | What it provides |
|---|---|---|
| Global configuration | `OPTION`, `TITLE`, scalar variables | Output settings, numerical constants, readable parameters |
| Machine geometry | Named `DRIFT`, `QUADRUPOLE`, etc. | Placed physical elements and their field parameters |
| Traversal order | `LINE=(...)`, optionally `RING=(...)` | Sequence followed by tracking |
| Initial phase space | `DISTRIBUTION` | Particle sampling or file-based particle records |
| Injection | `EMISSIONSOURCE`, `EMISSIONSOURCELIST` | Distribution references, placement and injection timing |
| Particle container | `BEAM` | Species, reference momentum/energy, charge, allocation, sources |
| Self-fields | `FIELDSOLVER`; optional `BINNING` | No self-fields or a supported space-charge model |
| Tracking | `TRACK` → `RUN` → `ENDTRACK` | Beamline, beam, timestep, stop conditions, solver |
| End of input | `QUIT;` | Terminate input processing |

An input file may use `CALL, FILE="...";` to read additional OPALX files. The generator owns the **entire input bundle**, not just element definitions. For a simple no-space-charge simulation, a single `.in` file is usually enough.

**Dependency principle:** define named distributions before their sources, sources before their source list, the source list before use on the beam; define all elements before assembling a line, and define the beam, line, and solver before the tracking block. See manual §§5, 8 and 10.

## 3. Input language and commands

OPALX uses a MAD-inspired, free-format, statement-oriented language. End statements with `;`. Unquoted identifiers are case-insensitive (normalized to uppercase); quoted strings and **file paths** retain their contents. `//` and `/* ... */` introduce comments. Parameters can be assigned immediately with `=` or stored as expressions with `:=` for later re-evaluation. (Manual §§8–10, pp. 24–48.)

### 3.1 Common syntax forms

| Task | Example syntax |
|---|---|
| Real variable | `REAL LQ=0.5;` |
| Computed real | `REAL L2=2*LQ;` |
| Deferred real | `REAL KQ:=K0*scale;` |
| Logical variable | `BOOL use_output=TRUE;` |
| String variable | `STRING filename="particles.txt";` |
| Real vector | `REAL VECTOR v={1,2,3};` (also `VECTOR`) |
| Named element | `Q1: QUADRUPOLE, L=0.5, ELEMEDGE=0.0, K1=0.54;` |
| Ordered line | `L1: LINE=(Q1,D1);` |
| Read object attribute | `Q1->L` |
| Update object attribute | `Q1->K1=0.25;` |
| Print expressions | `VALUE, {LQ,KQ};` |
| Include input file | `CALL, FILE="includes/parameters.in";` |
| Human-readable title | `TITLE, STRING="Example study";` |
| End input | `QUIT;` |

Arithmetic includes `+`, `-`, `*`, `/`, `^`, parentheses and documented mathematical functions such as `sqrt`, `sin`, `cos`, `exp`; arrays use `{...}`. Do not treat illustrative `...` placeholders as actual OPALX syntax. Keep semicolons, variable names, labels, and source references explicit.

`STOP;` and `QUIT;` both terminate the *current input stream*: inside an included `CALL` file they return to the caller; in the main file they end processing. Prefer `QUIT;` at the end of the main input. An included file that terminates early should do so deliberately. (Manual §10.2, pp. 42–43; §10.6, pp. 46–47.)

### 3.2 Configuration principles

- Use descriptive unique labels. Parameterize repeated lengths, strengths, and particle settings with `REAL` expressions when it improves readability.
- Give numerical quantities in **the unit documented for that attribute** (see §4), not an assumed universal system.
- Use properly quoted relative filenames for data files; the generator must provide the referenced files (see §12).
- Use `VALUE, {...};` or comments only when useful; neither replaces defining a beam or tracker.
- Current **OPALX** syntax takes precedence over historical **OPAL** examples in the same manual (see §13).

## 4. Units and reference-particle conventions

OPALX uses SI internally, but input **attributes mix SI, accelerator, and normalized units**. This table is a practical selection; consult the attribute's own documentation for others. (Manual §7 pp. 22–23; §§12, 16–17.)

| Quantity / attribute | Input convention |
|---|---|
| Element `L`, `ELEMEDGE`, `X/Y/Z`, local offsets | m |
| Distribution `SIGMAX/Y/Z`, source `R0X/Y/Z` | m |
| `TRACK.DT`, source `T0`, pulse times | s |
| `THETA`, `PHI`, `PSI`, `LAG`, `ANGLE` | rad where the current element section specifies radians |
| `QUADRUPOLE.K1`, `K1S` | normalized gradient, m⁻² |
| `MULTIPOLE.KN`, `KS` | normalized coefficient arrays; index 0 dipole, index 1 quadrupole |
| `MULTIPOLET.TP` | physical coefficients: index 0 T, index 1 T/m, etc. |
| `SOLENOID.KS` | normalized map scale, m⁻¹ |
| `BEAM.PC` | reference momentum, GeV/c |
| `BEAM.ENERGY` | **total** particle energy, GeV (not kinetic energy) |
| `BEAM.MASS` | rest mass, GeV/c² |
| `BEAM.GAMMA` | dimensionless Lorentz factor |
| `BEAM.BCHARGE` | bunch-charge **magnitude**, C |
| `BEAM.CHARGE` | particle charge in elementary-charge units |
| `SIGMAPX/Y/Z`, source `P0X/Y/Z` | normalized momentum `p/(mc)` = βγ, not slopes or GeV/c |
| `RFCAVITY.FREQ`, `TRAVELINGWAVE.FREQ` | MHz |
| `RFCAVITY.VOLT` | MV (mapped standing-wave amplitude) |
| `TRAVELINGWAVE.VOLT` | MV/m (mapped traveling-wave amplitude) |
| `CONSTANTEFIELDCAVITY.EX/EY/EZ` | MV/m |
| `PROBE.XSTART/XEND/YSTART/YEND/STEP` | **mm**, unlike common element positions |

**Energy specification:** For a generated (non-file) distribution, supply exactly **one** of `BEAM.PC`, `BEAM.ENERGY`, or `BEAM.GAMMA`. If given kinetic energy `T` in GeV, derive total energy `E=T+m` (where `m` is the rest-energy value in GeV) or derive `PC=sqrt(E*E-m*m)` in GeV/c. The manual's electron example uses `EMASS` as the rest-energy constant:

```opal
REAL Edes=1e-3;                   // kinetic energy [GeV]
REAL gamma=(Edes+EMASS)/EMASS;
REAL beta=sqrt(1.0-1.0/(gamma*gamma));
REAL P0=gamma*beta*EMASS;         // reference momentum [GeV/c]
```

For `FROMFILE` and `EMITTEDFROMFILE`, **omit all three reference-energy attributes**: files supply absolute normalized momenta. Bunch-charge magnitude is ordinarily positive; particle charge sign comes from `CHARGE` (or the selected `PARTICLE`). The manual's overview contains a negative-charge example, but the detailed current beam definition and maintained worked inputs use a positive `BCHARGE`; prefer that convention. (Manual §§5.1, 16.1–16.3, 17.3.)

## 5. Accelerator elements and placement

### 5.1 Shared syntax and placement

```opal
D1: DRIFT,       L=0.5, ELEMEDGE=0.0;
Q1: QUADRUPOLE, L=0.3, ELEMEDGE=0.5, K1=0.54;
```

Every **placed physical element** needs exactly one documented placement method:

1. **Path placement:** `ELEMEDGE=s` locates the element entrance at path position `s` in **m**; optional `PSI` rotates about the local longitudinal axis.
2. **Absolute pose:** explicitly supply at least one of `X`, `Y`, `Z`, `THETA`, `PHI`, with the remaining pose coordinates defaulted as documented; `PSI` can set roll.

Do **not** mix `ELEMEDGE` with an absolute pose. `PSI` alone does not select absolute pose. The order of elements in `LINE` is not a substitute for placement. (Manual §12.1, pp. 60–61.)

| Shared attribute | Use / convention |
|---|---|
| `L` | Nominal element length [m]; use positive length for thick drift/quadrupole kernels |
| `ELEMEDGE` | Entrance along beamline reference path [m] |
| `X/Y/Z`, `THETA/PHI/PSI` | Absolute lab-frame translation [m] and rotations [rad] |
| `DX/DY/DZ`, `DTHETA/DPHI/DPSI` | Local position/rotation misalignment [m]/[rad] |
| `APERTURE` | Quoted geometry string, e.g. `"CIRCLE(0.02)"`, `"ELLIPSE(0.03,0.02)"`, `"RECTANGLE(0.03,0.02)"`; dimensions are full widths in metres |
| `DELETEONTRANSVERSEEXIT` | Boolean requesting particle deletion at a transverse aperture exit |

### 5.2 Common elements and useful attributes

The following are **independent element examples**, not one assembled lattice. Their placement values are illustrative. (Manual §12, pp. 60–73.)

**Drift, quadrupole and normalized multipole**

```opal
D1: DRIFT, L=0.5, ELEMEDGE=0.0;
QF: QUADRUPOLE, L=0.2, ELEMEDGE=0.5, K1=0.54;
QS: QUADRUPOLE, L=0.2, ELEMEDGE=0.7, K1S=0.10;
M1: MULTIPOLE, L=0.2, ELEMEDGE=0.9, KN={0.0,0.54};
```

- `K1` and `K1S`: normal and skew quadrupole strengths [m⁻²]. Do not substitute a gradient in T/m without applying the appropriate rigidity conversion.
- `MULTIPOLE.KN` and `KS` contain normalized normal/skew strengths; array indices 0 and 1 represent dipole and quadrupole. The current **particle** kernel does not implement all higher multipole orders even though the parser accepts larger arrays. For higher orders consider documented `MULTIPOLET` instead.
- `QUADRUPOLE.DK1/DK1S` and `MULTIPOLE.DKN/DKS` are currently stored but not applied by the field kernel. Avoid treating them as effective error controls.

**Physical/fringe multipole**

```opal
MT1: MULTIPOLET, L=0.5, ELEMEDGE=0.0,
    TP={0.0,1.80}, LFRINGE=0.05, RFRINGE=0.05,
    HAPERT=0.04, VAPERT=0.04;
```

`TP` has **physical** multipole coefficients (index 0 T, index 1 T/m; up to index 5); `LFRINGE`, `RFRINGE`, `HAPERT`, `VAPERT` are in metres. `ANGLE` [rad] chooses straight (`0`) versus constant-radius curved geometry, while `ROTATION` [rad] is available for straight skew elements. Variable-radius bending is not currently supported. `HAPERT`/`VAPERT` are this model's specific apertures, not substitutes for generic `APERTURE`. (Manual §12.7, pp. 65–66.)

**Constant electric field and constant focusing**

```opal
DC1: CONSTANTEFIELDCAVITY, L=0.5, ELEMEDGE=0.0,
    EX=0.0, EY=0.0, EZ=-5.0;
CF1: CONSTANTFOCUSING, L=0.01, ELEMEDGE=0.5,
    STRENGTH=1.5, RADIUS=1.774e-3;
```

`CONSTANTEFIELDCAVITY` applies a local uniform DC electric field in **MV/m**; a negative `EZ` accelerates an electron in the local `+z` direction. `CONSTANTFOCUSING` has an application-specific `STRENGTH` and `RADIUS` [m], primarily for DIH tests; do not substitute it for a normal quadrupole without a user request. (Manual §§12.3–12.4, pp. 62–63.)

**Field-map-based solenoid and RF structures**

```opal
S1: SOLENOID, L=0.5, ELEMEDGE=0.0,
    KS=0.12, FMAPFN="fieldmaps/solenoid.T7";

RF1: RFCAVITY, L=0.2927, ELEMEDGE=0.0,
    TYPE="STANDING", VOLT=60.0, FREQ=1300.0,
    LAG=0.0, FMAPFN="fieldmaps/DriveGun.T7", APVETO=FALSE;

TW1: TRAVELINGWAVE, L=2.8, ELEMEDGE=0.5,
    VOLT=15.0, FREQ=2998.0, LAG=0.0,
    FMAPFN="fieldmaps/traveling-wave.T7",
    NUMCELLS=84, MODE=0.3333333333;
```

| Element | Important attributes / details |
|---|---|
| `SOLENOID` | `KS` [m⁻¹]; **requires** `FMAPFN` and supported map data; no automatic hard-edge solenoid when file is missing |
| `RFCAVITY` | `TYPE="STANDING"`, `VOLT` [MV], `FREQ` [MHz], `LAG` [rad], required `FMAPFN`; `APVETO` exempts this cavity from autophase |
| `TRAVELINGWAVE` | `VOLT` [MV/m], `FREQ` [MHz], `LAG` [rad], `FMAPFN`, positive integer `NUMCELLS`, `MODE` as fraction of `2π` per cell; map and cell parameters must correspond |

`OPTION.AUTOPHASE` controls automatic RF phase search globally; `APVETO=TRUE` opts out on one RF element. A cavity's map can override a configured frequency when they disagree by more than 1%. The sample file paths above are **placeholders for real files**, not fabricated data. (Manual §§12.8–12.10, pp. 66–68; worked RF input §5.2.)

**Bends and diagnostics**

```opal
B1: SBEND, L=0.5, ELEMEDGE=1.0, ANGLE=0.1,
    K1=0.0, HGAP=0.02, FINT=0.5;
IP: MARKER, ELEMEDGE=1.2;
M1: MONITOR, L=0.01, ELEMEDGE=1.3,
    TYPE=SPATIAL, OUTFN="monitor.h5";
P1: PROBE, L=0.001, ELEMEDGE=1.4,
    XSTART=-10, XEND=10, YSTART=-10, YEND=10,
    STEP=1, OUTFN="probe.h5";
```

- `RBEND`/`SBEND`: `ANGLE` [rad], normalized `K0/K1/K2/K3` families [m⁻¹, m⁻², m⁻³, m⁻⁴], `HGAP` [m], `FINT`; `RBEND.L` is a straight-body length and `SBEND.L` an arc length. Use the detailed bend section for edge/geometry limitations.
- `MONITOR`: `TYPE=SPATIAL` or `TEMPORAL`, `OUTFN` output file. `MARKER` labels a position without field.
- `PROBE`: `XSTART/XEND/YSTART/YEND/STEP` are **millimetres**, and `OUTFN` names an output.
- Additional elements including `CYCLOTRONSECTOR`, `LASER`, and special diagnostics have dedicated documentation; consult it before configuring unfamiliar attributes. (Manual §§12.11–12.19, pp. 68–73.)

## 6. Beamlines and lattice composition

A `LINE` is an ordered list of **already defined** elements and/or previously defined sublines. Element occurrences need the placement described in §5.

```opal
D1: DRIFT, L=0.3, ELEMEDGE=0.0;
Q1: QUADRUPOLE, L=0.2, ELEMEDGE=0.3, K1=0.5;
D2: DRIFT, L=0.3, ELEMEDGE=0.5;
Cell: LINE=(D1,Q1,D2);
```

A second line may include named sublines, e.g. `Machine: LINE=(Cell,OtherCell);` **provided those names and the physical placements are appropriate**. The list order controls traversal; it does not auto-compute `ELEMEDGE` or move/reposition reused elements. For repeated physical elements at different positions, define distinct placed occurrences as needed. (Manual §15.1–15.2, pp. 112–113.)

`RING=(...)` defines a ring sequence but **does not close its geometry automatically**. Its reference trajectory and explicit six-dimensional entrance poses require dedicated treatment; do not assume that repeating `LINE` elements creates a ring. (Manual §15.3, pp. 113–114.)

## 7. Beam definitions

For a generated distribution:

```opal
Beam1: BEAM, PARTICLE=ELECTRON,
    PC=0.1, NALLOC=1000,
    BCHARGE=1e-12, CHARGE=-1,
    SOURCES=Sources;
```

This snippet assumes `Sources` was defined as an `EMISSIONSOURCELIST` (§8). Important `BEAM` attributes (manual §16.1–16.4, pp. 115–118):

| Attribute | Meaning / input |
|---|---|
| `PARTICLE` | Species name, e.g. `ELECTRON`, `POSITRON`, `PROTON`, `MUON`; see catalog below |
| `MASS` | Optional rest mass [GeV/c²], for custom species or override |
| `CHARGE` | Elementary-charge units (`-1` for electron) |
| `PC`, `ENERGY`, `GAMMA` | Alternative reference-state inputs; **select one** for generated distributions; **none** for file-distributions |
| `NALLOC` | Required positive particle allocation / macroparticle-weight baseline |
| `BCHARGE` | Bunch-charge magnitude [C] |
| `SOURCES` | Name of a nonempty `EMISSIONSOURCELIST` for a non-photon beam |
| `GLOBALPROCESSES`, `DAUGHTERBEAM`, `POLARIZATION` | Special decay/spin workflows; consult dedicated chapters before use |

Defined species in the current manual: `PHOTON`, `ELECTRON`, `POSITRON`, `MUON`, `PION`, `PROTON`, `ANTIPROTON`, `DEUTERON`, `HMINUS`, `H2P`, `ALPHA`, `CARBON`, `XENON`, `URANIUM`. `PHOTON` can be defined but current `TRACK` rejects photon beams. A tracked non-photon beam needs a populated source list. Set `NALLOC` at least as large as the total selected source `NPARTDIST`, unless the user explicitly requests different macroparticle weighting.

## 8. Distributions, emission sources and particle files

**OPALX object chain:** `DISTRIBUTION` → `EMISSIONSOURCE` → `EMISSIONSOURCELIST` → `BEAM.SOURCES`; distributions do **not** belong on `RUN`. (Manual §17, pp. 120–130.)

```opal
Dist: DISTRIBUTION, TYPE=GAUSS, NPARTDIST=1000,
    SIGMAX=2e-4, SIGMAY=2e-4, SIGMAZ=2e-4,
    SIGMAPX=1e-5, SIGMAPY=1e-5, SIGMAPZ=1e-5;
Source1: EMISSIONSOURCE, DISTRIBUTION=Dist;
Sources: EMISSIONSOURCELIST=(Source1);
```

### 8.1 Emission-source attributes

| Attribute | Meaning |
|---|---|
| `DISTRIBUTION` | Required existing distribution label |
| `R0X/R0Y/R0Z` | Position offset added after sampling [m] |
| `P0X/P0Y/P0Z` | Normalized-momentum offset added after sampling [`p/(mc)`] |
| `T0` | Injection start time [s]; positive values delay one-shot injection |
| `EMISSIONMODEL` | `NONE` or `ASTRA`; depends on distribution type |
| `EKIN` | Thermal kinetic energy for generated emitted particles [eV] |
| `ZEROFACE_R0Z`, `SHIFTED_GREENS_FUNCTION` | Alternative cathode-plane Dirichlet corrections; not simultaneous |
| `ZEROFACE_MAXSTEPS` | Limit of cathode-plane correction steps; 0 is unlimited |

An `EMISSIONSOURCELIST` can contain multiple named sources, e.g. `Sources: EMISSIONSOURCELIST=(S1,S2);`. Generated one-shot Gaussian/uniform sources use `EMISSIONMODEL=NONE`; emitted flat-top sources can support `ASTRA`. (Manual §§17.1–17.2, pp. 120–121.)

### 8.2 Available distribution types

The current OPALX manual lists **seven types**—not the additional types listed under legacy OPAL:

| `DISTRIBUTION.TYPE` | Generation inputs and behavior |
|---|---|
| `UNIFORM` | `NPARTDIST`; `SIGMAX/Y/Z` are **ellipsoid semi-axes** [m]; no momentum spread; one-shot |
| `GAUSS` | `NPARTDIST`; `SIGMAX/Y/Z` are position widths [m], `SIGMAPX/Y/Z` normalized momentum widths; independent Gaussian coordinates; one-shot |
| `MULTIVARIATEGAUSS` | Gaussian widths plus `CORR={15 coefficients}` for the correlations of `(x,px,y,py,z,pz)` |
| `FLATTOP` | Time-dependent transverse ellipse: `NPARTDIST`, `EMITTED=TRUE`, `SIGMAX/Y`, pulse parameters `TRISE/TFALL` or `SIGMAT`, `TPULSEFWHM`, `CUTOFFLONG` |
| `OPALFLATTOP` | Flat-top emission with precomputed birth times; additional `EMISSIONSTEPS`, optional `FTOSCAMPLITUDE`, `FTOSCPERIODS` |
| `FROMFILE` | Non-emitted 6D records; `FNAME`, positive `NPARTDIST`; file contains absolute normalized momenta; no beam `PC/ENERGY/GAMMA` |
| `EMITTEDFROMFILE` | Per-particle birth times; `FNAME`, `NPARTDIST` (0 means all), optional `EMISSIONSTEPS`; no beam `PC/ENERGY/GAMMA` |

**Independent Gaussian / uniform:**

```opal
G: DISTRIBUTION, TYPE=GAUSS, NPARTDIST=10000,
    SIGMAX=1e-3, SIGMAY=1e-3, SIGMAZ=2e-3,
    SIGMAPX=1e-4, SIGMAPY=1e-4, SIGMAPZ=2e-4;
U: DISTRIBUTION, TYPE=UNIFORM, NPARTDIST=10000,
    SIGMAX=1e-3, SIGMAY=2e-3, SIGMAZ=3e-3;
```

For `GAUSS`, position sampling uses internally fixed ±3σ bounds; accepted user cutoffs and `CORRX/CORRY/CORRZ/CORRT` do not currently alter the active sampler. `UNIFORM` positions fill an ellipsoid uniformly by volume and its particles share the reference momentum. (Manual §§17.3.1–17.3.2, pp. 123–124.)

**Correlated Gaussian:**

```opal
MG: DISTRIBUTION, TYPE=MULTIVARIATEGAUSS, NPARTDIST=10000,
    SIGMAX=1e-3, SIGMAPX=1e-4,
    SIGMAY=1e-3, SIGMAPY=1e-4,
    SIGMAZ=2e-3, SIGMAPZ=2e-4,
    CORR={0.2,0,0,0,0, 0,0,0,0, 0,0,0, 0,0,0};
```

`CORR` lists the 15 upper-triangle off-diagonal correlations in this order:
`(x,px), (x,y), (x,py), (x,z), (x,pz), (px,y), (px,py), (px,z), (px,pz), (y,py), (y,z), (y,pz), (py,z), (py,pz), (z,pz)`.
Use physically meaningful correlations; the matrix must be positive definite. (Manual §17.3.3, pp. 124–125.)

**Generated pulsed distribution:**

```opal
FT: DISTRIBUTION, TYPE=FLATTOP, NPARTDIST=10000,
    EMITTED=TRUE, SIGMAX=1e-3, SIGMAY=1e-3,
    TRISE=0.5e-12, TFALL=0.5e-12,
    TPULSEFWHM=10e-12, CUTOFFLONG=3;
```

`SIGMAX/Y` are transverse ellipse semi-axes for flat-top types. `TRISE/TFALL`, `SIGMAT`, and `TPULSEFWHM` are in seconds; `CUTOFFLONG` truncates Gaussian pulse edges. `OPALFLATTOP` uses the same base pulse specification plus its inventory/modulation attributes. (Manual §§17.3.4–17.3.5, pp. 125–127.)

### 8.3 External particle files

**`FROMFILE` format** (plain text, manual §17.3.6, pp. 127–128): first non-comment line contains record count; next line contains case-insensitive column names including `x y z px py pz` in any order; subsequent rows contain the data. Positions are **m**; `px/py/pz` are **absolute** normalized momenta `p/(mc)` (not relative deviations). Lines beginning with `#` and blank lines are ignored.

```text
2
x px y py z pz
0.0 0.001 0.0 0.0 0.0 1.2
0.1 0.002 0.0 0.0 0.0 1.2
```

```opal
Particles: DISTRIBUTION, TYPE=FROMFILE,
    FNAME="particles.txt", NPARTDIST=2;
```

`NPARTDIST` selects at most that many records from the beginning of the file. **Do not define beam reference `PC`, `ENERGY`, or `GAMMA` for this distribution.** OPALX resolves `DISTRIBUTION.FNAME` relative to the input file.

**`EMITTEDFROMFILE` format** (manual §17.3.7, pp. 129–130): prefer a header with `x y z px py pz birth_time`. `birth_time` is a time offset [s] from source `T0`; positions are offsets from `R0*`, momenta remain absolute normalized values (plus `P0*`). Older positional `x px y py t pz [bin]` files use different time conventions; do not silently mix them. Example of a named-header format:

```text
2
x y z px py pz birth_time
1e-6 2e-6 -3e-4 0.1 -0.2 0.3 -4e-12
-1e-6 1e-6 2e-4 -0.1 0.2 -0.3 3e-12
```

```opal
EmittedParticles: DISTRIBUTION, TYPE=EMITTEDFROMFILE,
    FNAME="emitted.txt", NPARTDIST=0, EMISSIONSTEPS=100;
```

## 9. Field solvers, space charge and binning

The **lattice generator defines** a `FIELDSOLVER` even when self-fields are disabled; `RUN.FIELDSOLVER` selects it. A current OPALX solver definition requires positive `NX/NY/NZ` mesh sizes, `PARFFTX=TRUE`, `PARFFTY=TRUE`, `PARFFTZ=TRUE`, and a consistent set of all three `BCFFT*` boundary types. (Manual §19, pp. 147–156.)

### 9.1 No self-fields

```opal
FSNone: FIELDSOLVER, TYPE=NONE,
    NX=8, NY=8, NZ=8,
    PARFFTX=TRUE, PARFFTY=TRUE, PARFFTZ=TRUE,
    BCFFTX=OPEN, BCFFTY=OPEN, BCFFTZ=OPEN;
```

`TYPE=NONE` disables particle self-field computation, **not external magnet or RF fields**. The mesh and decomposition attributes remain required by the current constructor. This is the documented no-space-charge choice.

### 9.2 Active solver choices

| `TYPE` | Physics / boundaries | Important settings |
|---|---|---|
| `OPEN` | Isolated finite bunch (Hockney free-space FFT) | All `BCFFT*=OPEN`; optional `GREENSF=INTEGRATED` (default) or `STANDARD`; `BBOXINCR` |
| `FFT` | Periodically repeated box | All `BCFFT*=PERIODIC`; **not** isolated free-space calculation |
| `P3M` | Particle–particle/particle–mesh | All boundaries uniformly `OPEN` or `PERIODIC`; **positive `RCUT`** [m]; `BINS=NONE` |
| `NONE` | No particle self-field | All `BCFFT*=OPEN` conventional |
| `CG` | Intended all-face Dirichlet solver | **Not implemented** in documented current OPALX runtime; do not generate as operational solver |

**Open free-space solver example:**

```opal
FSOpen: FIELDSOLVER, TYPE=OPEN,
    NX=64, NY=64, NZ=128,
    PARFFTX=TRUE, PARFFTY=TRUE, PARFFTZ=TRUE,
    BCFFTX=OPEN, BCFFTY=OPEN, BCFFTZ=OPEN,
    GREENSF=INTEGRATED, BBOXINCR=2.0;
```

`BBOXINCR` is **percent padding** on each side of the moving particle mesh, not an extra fixed length. For active self-fields, nonzero bunch charge is needed when tracking multiple charged macroparticles. Solver mesh resolution and particle number are scientific choices: use requested values or explicitly documented starting settings, not unexplained production defaults. (Manual §§19.1–19.4, pp. 147–152.)

### 9.3 Optional velocity binning and cathode-plane corrections

Binning uses a separate named object and is selected via `FIELDSOLVER.BINS`:

```opal
Bins: BINNING, MAXBINS=64, DESIREDWIDTH=0.2,
    BINNINGALPHA=1.1, BINNINGBETA=1.6,
    PARAMETER=GAMMAZ, ADAPTIVEBINNING=TRUE,
    TABLEPRINTFREQ=20;

FSBinned: FIELDSOLVER, TYPE=OPEN, BINS=Bins,
    NX=16, NY=16, NZ=16,
    PARFFTX=TRUE, PARFFTY=TRUE, PARFFTZ=TRUE,
    BCFFTX=OPEN, BCFFTY=OPEN, BCFFTZ=OPEN,
    GREENSF=INTEGRATED;
```

- `MAXBINS`: positive integer maximum; `DESIREDWIDTH`, `BINNINGALPHA`, `BINNINGBETA` guide adaptive merging; `ADAPTIVEBINNING` enables the merge scheme.
- **Supported implemented** `PARAMETER` selectors: `VELOCITYZ`, `GAMMAZ`. The parser also accepts `POSITIONZ` and `PZ`, but the documented runtime rejects them.
- `BINS=NONE` disables binning. `P3M` does not support binning.
- Cathode-plane corrections are configured on **`EMISSIONSOURCE`**, not just on the solver. `ZEROFACE_R0Z=TRUE` and `SHIFTED_GREENS_FUNCTION=TRUE` are mutually exclusive. Shifted-Green requires an `OPEN` solver and **named binning** to be effective. See the manual before preparing emitted-beam boundary configurations.

(Manual §18 pp. 144–146; §§19.5–19.6 pp. 152–156; worked space-charge example §5.3.)

## 10. Tracking and run statements

The input **must contain** the tracking block, even though the generator **must not execute it**:

```opal
TRACK, LINE=Cell, BEAM=Beam1,
    DT={1e-11}, MAXSTEPS={1000}, ZSTOP={0.8};
  RUN, METHOD=PARALLEL, FIELDSOLVER=FSNone;
ENDTRACK;
QUIT;
```

This illustrative fragment assumes `Cell`, `Beam1`, `FSNone` were previously defined. (Manual §§20.1–20.2, pp. 167–173.)

| Construct | Configuration |
|---|---|
| `TRACK.LINE` | Previously defined `LINE` or `RING` |
| `TRACK.BEAM` | One previously defined `BEAM` |
| `TRACK.BEAMS={...}` | Ordered multiple-beam selection; nonempty `BEAMS` takes precedence over `BEAM` |
| `TRACK.DT` | Timestep [s], scalar or `{...}` schedule |
| `TRACK.MAXSTEPS` | Maximum steps per segment, scalar or `{...}` schedule |
| `TRACK.ZSTOP` | Stop longitudinal reference positions [m], scalar or `{...}` schedule |
| `TRACK.ZSTART` | Initial reference-path position [m] |
| `RUN.METHOD` | **`PARALLEL`** is the current implemented method |
| `RUN.FIELDSOLVER` | Name of defined `FIELDSOLVER` |
| `RUN.SCFIELDUPDATE` | For active self-fields, `MIDPOINT` (default) or `PRESTEP` |
| `ENDTRACK;` | Leave tracking mode |

**Multi-segment tracking:** `DT`, `MAXSTEPS` and `ZSTOP` can contain arrays of different lengths. OPALX extends shorter arrays by repeating their final entry and orders segment triples by increasing `ZSTOP`. Each segment receives its **own** `MAXSTEPS` budget. For clarity, prefer arrays of equal length when defining an intentional multi-segment schedule.

```opal
TRACK, LINE=Cell, BEAM=Beam1,
    DT={1e-11,2e-12}, MAXSTEPS={10,20},
    ZSTOP={0.2,0.8};
  RUN, METHOD=PARALLEL, FIELDSOLVER=FSNone;
ENDTRACK;
```

`RUN` in current OPALX **does not accept** `BEAM`, `BEAMS`, `SOURCES`, or `DISTRIBUTION`; these connect through `TRACK` and `BEAM.SOURCES`. `RUN.METHOD="PARALLEL-T"` is legacy syntax, not the current method. Some `TRACK` options (e.g., `TIMEINTEGRATOR`) are parsed for compatibility but do not select the current parallel particle integration kernel. Ring/COF/spectral-tune options require their own documentation. (Manual §§20.1–20.3.)

## 11. Runtime options and diagnostics

`OPTION` statements configure output, reproducibility and runtime options *inside the input*; command-line flags and job submission are outside the generator's scope. Example:

```opal
OPTION, VERSION=10900;
OPTION, SEED=123456789;
OPTION, PSDUMPFREQ=1000, STATDUMPFREQ=1;
OPTION, AUTOPHASE=0;
```

| Option / diagnostic | Use |
|---|---|
| `VERSION=10900` | Documented current-version selector used by maintained examples |
| `SEED` | Reproducible sampling; `-1` requests time-based seed where supported |
| `PSDUMPFREQ` | Frequency of phase-space dumps, in global tracking steps |
| `STATDUMPFREQ` | Frequency of statistics dumps, in global tracking steps |
| `CHECKPOINTFREQ` | Restart checkpoint frequency; `0` disables |
| `ENABLEHDF5`, `ENABLEVTK` | Enable supported HDF5/VTK output families |
| `RHODUMP`, `EBDUMP`, `RANKDUMP` | Additional supported per-particle/field output |
| `AUTOPHASE` | Global RF phase optimization setting: `0` disables search |
| `ECHO`, `INFO`, `TRACE`, `WARN` | Parser-message controls; `TRACE` belongs early in the file |
| `ENABLELINEARTRANSFERMAPS` | Additional numerical transfer-map diagnostic; see its dedicated options before requesting it |

`OPTION, INFO=...;` is **not** the same as the executable's `--info N` verbosity argument. Special diagnostics may require a placed `MONITOR`, `PROBE`, or separate documented command; don't invent a generic output statement. Parser-accepted legacy options may have no effect in the current parallel tracker. (Manual §11, pp. 49–59; §12.13–12.15.)

## 12. Input directories and external dependencies

The generator produces a **portable input bundle**. Create only the supporting files the requested simulation actually needs, and report the simulation directory and the main `.in` path **relative to it**. For example:

```text
simulation/
├── main.in
├── particles.txt                 # if using FROMFILE
├── fieldmaps/
│   └── cavity.T7                 # if the provided field map is needed
└── includes/
    └── parameters.in            # if using CALL
```

| Reference in `.in` | Supporting-file action |
|---|---|
| `DISTRIBUTION, FNAME="particles.txt"` | Include the requested physical particle data, or generate it only if the user supplied a defined sampling recipe |
| `SOLENOID` / `RFCAVITY` / `TRAVELINGWAVE`, `FMAPFN="fieldmaps/..."` | Include the actual compatible magnetic/RF field map; **do not synthesize an unknown map** |
| `CALL, FILE="includes/parameters.in";` | Include the referenced OPALX statements; keep file names and dependency order coherent |
| `MONITOR` / `PROBE`, `OUTFN="..."` | This names *future simulation output*, not a required pre-existing input file |

OPALX explicitly resolves `DISTRIBUTION.FNAME` relative to its input file. Other constructs have their own documented path rules; use clear relative paths, and consult the corresponding section when path resolution is unclear. The current field-map reader supports **specific map formats**; a filename extension alone does not establish compatibility. (Manual §10.6, §17.3, §26, pp. 46–47, 122, 207–221.)

**Do not include produced simulation results** in the input bundle. Validation, OPALX execution and result retrieval are delegated to other skills.

## 13. Current OPALX versus legacy OPAL: common traps

The manual intentionally contains both **OPALX** and historical **OPAL** sections. Do not copy old syntax across that boundary without evidence of current implementation.

| Do not assume | Current OPALX usage |
|---|---|
| `FIELDSOLVER, FSTYPE=FFT` with open boundaries denotes free space | Use `FIELDSOLVER, TYPE=OPEN` and all `BCFFT*=OPEN` |
| `FSTYPE="NONE"` is the solver switch | Use `TYPE=NONE`, with required mesh and FFT flags |
| `RUN, METHOD="PARALLEL-T"` is supported | Current supported method is `PARALLEL` |
| `RUN, BEAM=..., DISTRIBUTION=...` selects a bunch | Set `TRACK.BEAM` and `BEAM.SOURCES` → emission sources → distributions |
| `BCURRENT` or `BFREQ` are normal `BEAM` attributes | Current OPALX explicitly rejects them; use `BCHARGE` as appropriate |
| `GAUSSMATCHED`, `BINOMIAL`, `MULTIGAUSS` are current distribution types | Current OPALX supports the **seven** types in §8.2 |
| `QUADRUPOLE.K1` is a gradient in T/m | Current `K1` is normalized m⁻²; physical gradients belong to other interfaces (e.g., `MULTIPOLET.TP`) |
| Array entries beyond quadrupole on `MULTIPOLE` are applied to all tracked particles | Current particle/reference kernels disagree for higher orders; use the documented `MULTIPOLET` implementation |
| Parser-visible features always work | Current `TYPE=CG`, some bin selectors and compatibility knobs are not operational |
| `LINE` ordering alone positions/duplicates physical magnets | Define an explicit placement strategy for each physical occurrence |

These are **input-generation guidelines**, not validation procedures. (Manual §§11–12, 16–20.)

## 14. Manual and official source index (fallback only)

**This index is for missing or ambiguous features, not a mandatory pre-generation reading list.** If §2–§13 contain the needed syntax, proceed without external calls. Page numbers refer to the **456-page supplied PDF**.

| Missing information | *The OPALX Universe* | PDF pages |
|---|---|---|
| Complete maintained examples: drift, RF, emitted space charge | §5 Worked Input Files | 13–17 |
| Units, conventions | §7 Conventions | 22–23 |
| Input language and execution order | §8 Input Language | 24–32 |
| Grammar, expressions, labels, arrays | §9 Command Format; Appendix B | 33–41; 222–226 |
| `TITLE`, variables, `CALL`, `QUIT` | §10 Control Statements | 42–48 |
| Options, diagnostics and compatibility | §11 Runtime Options | 49–59 |
| Physical elements, placement, detailed attributes | §12 Elements (**OPALX portion**) | 60–73 |
| `LINE`, nested lines, `RING` | §15 Beam Lines | 112–114 |
| `BEAM` parameters and species | §16 Beam Definitions (**OPALX portion**) | 115–118 |
| `DISTRIBUTION`, sources and particle file formats | §17 Beam and Distributions (**OPALX portion**) | 120–130 |
| Binning | §18 Structures | 144–146 |
| Field solvers and boundaries | §19 Field Solvers (**OPALX portion**) | 147–156 |
| Tracking and run semantics | §20 Tracking (**OPALX portion**) | 167–173 |
| Supported field-map formats | Appendix A, §26 | 207–221 |
| Language/element/command registries | §§43–45 | 413–419 |
| Status, known limitations and regression guide | §§55, 58 | 448, 456 |

**Live official sources** (only if needed):

- [OPALX manual source](https://github.com/OPALX-project/opalx-manual) — especially `user-guide/input-language.qmd`, `user-guide/elements.qmd`, `user-guide/beam.qmd`, `user-guide/beam-distributions.qmd`, `user-guide/field-solver/index.qmd`, `user-guide/tracking.qmd` and `getting-started/worked-inputs.qmd`.
- [OPALX maintained regression inputs](https://github.com/OPALX-project/regression-tests-x) — working inputs and their required supporting files.
- [OPALX implementation](https://github.com/OPALX-project/OPALX) — last resort for confirmed behavior or interface changes.

When extending this reference, add concise, directly usable OPALX statements and their documented units/limitations; keep specialized end-to-end lattice examples outside this general reference. If a requested feature remains unconfirmed, report that limitation rather than inventing parameters.
