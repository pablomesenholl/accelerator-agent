# OPALX postprocessing roadmap

First milestone: load the existing FODO outputs, calculate beam quantities from
selected snapshots, validate them, and expose numerical arrays and summaries.
The library consumes local results; Magnus retrieval stays with opalx-simulator.

## Implementation steps

1. [x] Define data contracts in `models.py`: dataclasses containing NumPy arrays,
   explicit units, coordinates, provenance, reported metadata, calculation status
   and validation issues. Preserve integer particle IDs and unknown conventions.
2. [ ] **Deferred at user request.** Enable packaging in `pyproject.toml`: remove
   `package = false`, add a setuptools build backend and restrict discovery to
   `postprocess` packages.
   Refresh the lockfile and verify imports after sync. `readers/__init__.py`
   already exists for discovery imports.
3. [x] Discover files in `readers/discovery.py`: support absent outputs, multiple
   candidates and explicit selection. Separate inputs and derived artifacts;
   inventory unsupported files (including JSON) without interpreting them.
4. [x] Read the observed ASCII SDDS `.stat` format and selected HDF5 snapshots.
   Preserve header parameters, column types, descriptions, units and attributes.
   Sort snapshot IDs numerically; avoid loading every snapshot at once. Retain
   timing.dat as raw execution metadata initially. Reject unsupported variants.
5. [ ] Calculate centered population moments, RMS sizes, covariance, projected
   transverse normalized/geometric emittances and Twiss parameters. Start with
   equal particle weighting; document it and flag unequal charges. Verify frames
   and p/(mc) versus slope conventions before deriving geometric quantities.
6. [ ] Validate required fields, empty data, dimensions, nonfinite/nonphysical
   values and singular calculations. Report errors with source context; compare
   reported and calculated diagnostics only at matched coordinates/conventions.
7. [ ] Expose a small public API, JSON-compatible summaries and CSV statistics;
   keep arrays directly available for plotting. Include units and assumptions.
8. [ ] Complete synthetic numerical/error tests and a local FODO integration
   check; document supported formats and formulas. Do not launch simulations.

## Data contract decisions

- Dataclasses group numerical arrays and metadata; no pandas dependency in the
  contract. A DataFrame adapter can be added later for tabular consumers.
- Arrays are mutable and shared, with no implicit dtype or unit conversion.
  Constructors check structure; physical validation remains a separate stage.
- Statistics preserve source units. Snapshot path length/time are metres/seconds
  when known; readers must explicitly convert and retain original metadata.
- Unknown units/frames stay unknown. Raw reported values remain separate from
  calculated results. Covariance axes have explicit order and individual units.
- No run-wide lazy-loading object yet: define its API when readers exist.
- Discovery API: `discover_run(root)` returns a sorted `RunFiles` inventory;
  `select_file(files, "statistics" | "snapshots" | "timings", path=None)` returns
  a root-relative path, None for absent outputs, or raises `AmbiguousOutputError`
  for multiple candidates. An explicit path selects an inventoried candidate.
- Discovery classifies names, not contents. `.in` files are inputs; files under
  `analysis`/`plots` directories are derived (configurable with
  `derived_directories`). JSON, auxiliary outputs and symlinks stay unhandled;
  symlink directories are not traversed. No basename pairing is assumed.
- Reader API (from `postprocess.readers`): `read_stat(path)`,
  `list_snapshots(path)`, `read_snapshot(path, step)` and `read_timing(path)`.
  Pass `files.root / select_file(files, kind)` after checking for absent outputs.
- Statistics support the observed ASCII, row-oriented `no_row_counts=1` layout,
  numeric columns and one parameter per line. Preserve original SDDS definitions
  under `source.attributes['sdds_header']`; other unsupported layouts fail clearly.
- HDF5 reads one flat `Step#N` dump at a time and closes handles before returning.
  Original file/dataset attributes are retained under `file_attributes` and
  `dataset_attributes` in snapshot source attributes; group attributes stay at
  the top level. Nested/linked particle datasets are unsupported. Known SPOS/TIME
  units are converted to m/s; unknown units leave convenience coordinates unset.
- `TimingData` retains UTF-8 text verbatim, including line endings and repeated
  timer labels. Timing is optional execution metadata, never evidence of physics
  validity or run success. Do not flatten multiple tables or assume missing units;
  structured timing analysis remains deferred.

## Verification and limits

- Step 1: focused unittest checks cover structural errors, integer IDs, unknown
  metadata, covariance metadata, independent defaults and explicit failed results.
  All 7 model tests passed on 2026-10-26; numerical calculations remain pending.
  Run with `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/postprocess -v`
  until packaging is enabled.
- Step 3: all 14 model/discovery tests passed on 2026-10-26. Discovery tests
  cover missing/ambiguous outputs, explicit paths, classification, recursion,
  ordering, symlinks and traversal errors. A read-only FODO inventory check
  identified the expected `.stat`, `.h5`, `timing.dat`, input and derived report.
- Step 4: all 28 tests passed, including synthetic malformed/unsupported inputs,
  integer precision, metadata preservation, empty/nonfinite data, selective HDF5
  reads, closed handles, coordinate conversions and verbatim timing text. The
  local FODO integration test passed: 47 statistics columns, 1087 rows, 11 dumps,
  10000 particles in first/last dumps, and consistent final stored time/path.
  It skips when local FODO outputs are absent. No simulation was launched.
- FODO reference: `output/opalx-simulator/fodo-no-spacecharge`; `.stat` time is
  ns, HDF5 time is s; 11 particle snapshots. Verify reported attribute semantics
  before using them as numerical reference values.
- Deferred: DBA/COF JSON readers pending representative outputs, structured
  timing analysis, weighted moments, coupled optics and longitudinal Twiss.
