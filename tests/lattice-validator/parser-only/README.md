# Parser-only FODO checks

`inputs/fodo.in` preserves the successfully executed input from
`output/fodo-no-spacecharge-20261030/inputs/main.in`. Variants cover parser errors,
includes and runtime references that deliberately pass syntax validation only.

Run from the repository root with the project environment:

```bash
.venv/bin/python -B tests/lattice-validator/parser-only/test_parser_only.py
.venv/bin/python -B tests/lattice-validator/parser-only/test_parser_only.py --docker
.venv/bin/python -B tests/lattice-validator/parser-only/test_parser_only.py --magnus
```

Magnus checks require the registered `opalx-validation` blueprint and backend
runner code. Add `--stage-runner` to test uncommitted runners using temporary uploads.

Generated local files are cleaned automatically; Magnus outputs are not downloaded.
