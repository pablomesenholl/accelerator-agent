# Report compiler checks

From the repository root, install the compiler and warm its TeX cache by building
the fixture (choose another output directory if this one already exists):

```bash
.venv/bin/python scripts/setup_latex.py
.venv/bin/python scripts/compile_report.py tests/scientific-reporting/report.tex \
  --outdir output/latex-toolchain-check/online-v1
.venv/bin/python -m unittest discover -s tests/scientific-reporting -v
```

The fixture includes an equation, parameter table, the existing OPALX logo, a
BibTeX bibliography, and cross-references. Values are typesetting examples.
No simulation or beam analysis is performed. Inspect the generated PDF visually
as well as checking the final TeX log for warnings.

Tests run offline in temporary directories. They check successful PDF/BibTeX
output with resolved references, source preservation, refusal to overwrite a
build, retained failure diagnostics for invalid TeX, and failure on an unavailable
package. They skip if the compiler is absent; an installed compiler with an
unwarmed cache causes the success check to fail with compilation diagnostics.
These checks establish toolchain functionality, not scientific correctness or
compatibility with arbitrary LaTeX templates. Linux x86_64 is the initially
supported platform; no standalone Python agent integration is included.

Validated on 2026-11-03 with Tectonic 0.17.0 on Linux x86_64: the online fixture
build succeeded, all three offline integration tests passed, and the single-page
PDF was rendered and visually inspected. Equations, table, logo, bibliography,
and cross-references were readable with no clipping. The compiler and warmed
cache occupied approximately 69 MiB. Generated verification artifacts are under
`output/latex-toolchain-check/online-v1/` and are not committed.
