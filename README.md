# An Autonomous Agent for Accelerator Beam Dynamics

This semesterproject is dedicated to creating an autonomous
agent in order to orchestrate the heterogeneous software ecosystem 
for accelerator design and simulation. The framework for this project
will be based on the ColliderAgent architecture. 

## Python environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
from this repository:

```bash
uv sync --locked
source .venv/bin/activate
```

This creates a local Python 3.12 environment with the Magnus SDK, NumPy,
SciPy, pandas, matplotlib, and h5py. Python is downloaded if needed.
`pyproject.toml`, `.python-version`, and `uv.lock` describe the environment;
commit these files rather than `.venv`, which is already ignored by Git.
The lockfile records exact dependency versions for subsequent installations.

The project is installed as an editable package by `uv sync --locked`, exposing
the `postprocess` library to the agent's project interpreter:

```bash
.venv/bin/python -c "import postprocess; print(postprocess.__file__)"
```

No `PYTHONPATH` setting is needed. See [postprocessing usage](src/postprocess/README.md)
for readers, calculations, validation, plotting adapters and exports. Development
acceptance checks live under `tests/postprocess/`; `scripts/` holds workflow
runners such as the Magnus simulation runner.

The SDK connects to the existing Magnus backend using your Magnus configuration:

```bash
magnus config
```

Installing the SDK does not start a backend or register project blueprints.
Docker and the OPALX container are separate simulation requirements.

For development against a local Magnus SDK checkout, optionally replace the
installed SDK (adjust the path for your machine):

```bash
uv pip install --no-deps --editable "$HOME/.magnus/repository/sdks/python"
```

This local override is not part of the reproducible environment. After applying
it, use the activated environment's `python` and `magnus` commands directly;
`uv sync --locked` restores the locked SDK release. The backend configuration
and data are shared across Python environments.

## Core OPALX workflow

The workflow has five stages: [input generation](src/skills/lattice-generator/SKILL.md),
[validation](src/skills/lattice-validator/SKILL.md),
[simulation](src/skills/opalx-simulator/SKILL.md),
[analysis](src/skills/beam-analyzer/SKILL.md) and
[scientific reporting](src/skills/scientific-reporting/SKILL.md).

For standalone runs, scientific reporting produces an input-physics report after
generation and validation, then a completed report after simulation and analysis,
as requested. Design, optimization, and numerical-tuning studies produce one final
LaTeX/PDF report covering the iterations and relevant failed attempts; stage
records provide the evidence without separate per-run reports unless requested.
Stage records remain in `progress/`, analysis artifacts in `analysis/<analysis-id>/`, and
user-facing scientific reports in `scientific-reports/`; see the
[shared run layout](src/skills/references/run-layout.md).

Validation includes an OPALX parser-only syntax check and a review of the setup,
requested parameters and physical consistency. All checks must pass before
simulation. Follow the linked skills for commands and reporting instructions.

## LaTeX report compilation

Install the project-local compiler (currently Linux x86_64; requires `curl`):

```bash
.venv/bin/python scripts/setup_latex.py
```

The installer verifies the Tectonic release archive checksum and the versioned
TeX bundle's index checksum and `SHA256SUM` identity, using the pins in
`scripts/latex-toolchain.json`. The compiler, fetched TeX resources, and format
caches live in `.tools/tectonic/` (ignored by Git), separately from `.venv`.
Setup refuses to replace an existing installation. To update, edit and verify
the pins, move the old installation aside, and rerun setup.

Compile an existing report with a **new** build directory:

```bash
.venv/bin/python scripts/compile_report.py \
  output/<run-id>/scientific-reports/report.tex \
  --outdir output/<run-id>/scientific-reports/build-v1
```

Keep figures and bibliography paths relative to the source. Compilation checks
the bundle identity and downloads only needed resources into the local cache;
it does not download the full approximately 2.9 GB distribution. Initial builds
need network access and can take longer while creating the LaTeX format.
Subsequent builds can use `--offline`; a document requiring uncached resources
will fail explicitly. Bundle identity is the distribution's own content identifier,
not a checksum of the entire remote tar archive. Use bundled fonts for consistency
across machines. This setup fixes the toolchain, but does not promise byte-identical
PDFs across operating systems or source changes.

The fresh build directory contains the PDF on success, TeX/BibTeX diagnostics,
`compile.log`, and `build.json` with source/toolchain hashes, command, and status.
Inspect warnings and the rendered PDF before delivery. Compilation does not run
simulations or analysis. See [report compilation checks](tests/scientific-reporting/README.md).

## Standalone Python agent

The standalone Google ADK + LiteLLM CLI defaults to local Ollama `qwen3.5:2b`,
with configurable models, workspace-confined file tools, read-only skill loading,
and persistent run summaries:

```bash
uv sync --locked
.venv/bin/python python-agent/agent.py --show-config
.venv/bin/python python-agent/agent.py 'Create notes.txt describing a FODO cell.'
```

See [python-agent/README.md](python-agent/README.md) for progressive skill loading,
configuration, and the discovery and FODO generation smoke tests. Magnus and
simulation execution are available through opt-in tools; see
[Magnus usage](python-agent/MAGNUS.md) for operator-controlled submission and the
direct CLI that runs without an LLM.

Phase 4's reusable v0.1 runtime is complete and covered by offline integration
checks. Native parser-only validation and scientific result-analysis tools are
still missing, and successful complete model-generated lattices and reliable
model-driven simulations remain unverified. See the
[capability overview](python-agent/README.md#current-capabilities-and-missing-functionality)
and [AI roadmap](docs/AI_roadmap.md) for the distinction between runtime completion
and a complete autonomous physics workflow.
