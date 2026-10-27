# Postprocessing acceptance checks

After `uv sync --locked`, the offline suite covers the supported v1 library.
No OPALX executable, Magnus connection, network or new simulation is required.

```bash
MPLCONFIGDIR=/tmp/opalx-postprocess-tests-mpl \
  .venv/bin/python -m unittest discover -s tests/postprocess -v
```

The project `.venv` provides the installed package. MPLCONFIGDIR keeps plotting caches in a
writable temporary location; use another writable path if desired.

| Area | Checks |
| --- | --- |
| Models/discovery | Dimensions, integer precision, missing/ambiguous files, explicit selection and symlinks. |
| Readers | SDDS parameters/types/units, malformed/unsupported formats, selective HDF5 reads, closed handles and verbatim timing. |
| Observables | Exact analytic populations, a full coupled 6D covariance, linear drift emittance conservation and Twiss transport, unit conversions, degeneracy and numerical failure. |
| Validation | Required data, counts/ranges, units, PSD/symmetry, status/completeness and unique time/path matches. |
| Exports | Strict JSON, nonfinite diagnostics, metadata/dtype/CSV round trips, failed rows, plotting copies and existing-file guards. |
| Acceptance | Clean synthetic SDDS/HDF5, corrupt summaries, skipped comparisons, reference hash mismatch, CLI exit codes, source integrity and real headless PNGs. |

Local FODO tests skip when generated outputs are absent. Synthetic tests always
run. The acceptance CLI below requires real inputs and fails if they are absent;
it cannot silently skip the requested local check.

## Run the local FODO acceptance check

The existing `output/opalx-simulator/fodo-no-spacecharge` dataset has usable
particle/statistics data and a diagnosed HDF5 centroid metadata defect. A new
clean simulation is unnecessary for testing the library: this fixture verifies
both correct numerical results and detection of the upstream defect. It is not
an independently certified reference for the entire OPALX physics model.

Choose a new output directory outside the source run:

```bash
MPLCONFIGDIR=/tmp/opalx-postprocess-acceptance-mpl \
  .venv/bin/python tests/postprocess/check_fodo.py \
    --input output/opalx-simulator/fodo-no-spacecharge \
    --output output/postprocess/fodo-acceptance \
    --reference tests/postprocess/fixtures/fodo_reference.json \
    --confirm-z-longitudinal
```

The explicit axis confirmation asserts a straight FODO setup with shared
position/momentum axes and longitudinal z. This harness requires the compared
statistics lengths and emittances in metres. General library readers/adapters
retain their broader documented unit behavior. `--no-plots` explicitly skips
rendering; all numerical and export checks still run.

The script:

1. Discovers required outputs, verifies any supplied reference checksums, reads
   statistics and inventories snapshots; timing remains optional.
2. Loads each dump separately, validates inputs, computes and validates the
   observables, and compares them with uniquely time/path-matched diagnostics.
3. Retains all comparison issues. Only a checksum-pinned reference at the known
   OPALX revision, reproducing the exact sum(x)/sum(px)/sum(y) writer signature,
   can classify centroid mismatches as the known issue. Other mismatches fail.
4. Checks exact dtype-aware CSV and JSON round trips, and renders statistics vs.
   particle envelope/emittance overlays through a headless Agg canvas.
5. Rechecks input hashes and writes stage outcomes, source/software provenance,
   detailed validation and artifact paths. Source files are never rewritten.

Artifacts include `report.json`, `manifest.json`, per-snapshot summaries,
statistics CSV plus sidecar, observable-series CSV plus metadata, optional timing
text JSON, `envelope.png` and `normalized_emittance.png`. These generated files
stay under ignored `output/` and are not committed. Existing output directories
are refused, preserving previous checks.

| Status | Meaning | CLI exit |
| --- | --- | --- |
| `passed` | Requested checks passed with no reported diagnostic errors. | 0 |
| `passed_with_known_issue` | Postprocessor checks passed; the exact reference centroid defect remains explicitly reported. | 0 |
| `failed` | An unexpected mismatch, missing/unverifiable comparison, input/calculation error or export failure occurred. | 1 |
| Invocation/precondition error | Invalid flags, missing input directory or existing/unsafe destination. | 2 |

Inspect `stages`, validation warnings and skipped checks even for an accepted
run. The per-snapshot diagnostic reports remain `is_valid=false` for the legacy
centroid defect; the harness does not rewrite them to pass.

## Reference and final local result

`fixtures/fodo_reference.json` pins the original `.stat`/`.h5` bytes, 1087 rows,
47 columns, 11 dumps and 10000 particles per dump. OPALX revision:
`33d444649e3379b08c4610290d948fa2a4f39c93`. It also records measured maximum
normalized-emittance variations relative to the first dump: approximately
0.02955% in x and 0.15227% in y. These are regression measurements, not claims of
perfect physical conservation. Energy variation is bounded at 1e-10 relative.
Generic checks without this profile report variation without imposing these
reference-specific expectations.

The final local check on 2026-10-27 accepted the reference with 33 known centroid
component mismatches (three per dump), no unexpected errors, unchanged source
hashes, successful exports and both plot overlays. Recomputed values agree with
stored diagnostics at matching coordinates. The full suite passed 92 tests.

For a future clean FODO dataset, omit `--reference`; all centroid mismatches then
fail. A changed dataset cannot inherit the legacy exception based on a revision
string alone. Keep the legacy profile for its regression and add a separately
reviewed profile if another dataset needs fixed numerical expectations.
