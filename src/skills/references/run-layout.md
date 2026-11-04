# Run artifact layout

Read this reference before creating artifacts for any accelerator workflow stage.
All paths below are relative to the repository root; `output/` is not a filesystem-root directory.

```text
output/<run-id>/
├── prompt/                         # User prompt used for this run
├── inputs/                         # Portable OPALX input bundle
├── progress/
│   ├── generation.md               # Parameters, derivations and assumptions
│   ├── validation.md               # Checks, status and handoff decision
│   ├── native-parser-<job-id>.json  # Native syntax result, diagnostics and provenance
│   ├── simulation.md               # Job ID, execution and retrieval status
│   └── ...                         # Saved execution logs and other stage reports
├── results/                        # Retrieved raw simulation bundle
├── scientific-reports/             # Scientific report sources, assets and PDFs
└── analysis/<analysis-id>/
    ├── scripts/
    ├── figures/
    ├── data/
    ├── analysis_summary.md
    └── manifest.json
```

- At the first requested stage of a new physics run, create
  `output/<descriptive-slug>-<YYYYMMDDTHHMMSSZ>/`, for example
  `output/dba-cof-20261103T173126Z/`. Use a short lowercase description with
  hyphens between words and the actual directory-creation time in UTC, to second
  precision; `Z` denotes UTC. If the complete ID exists, append `-02`, `-03`,
  etc. rather than overwriting it. Choose the ID once and pass it unchanged
  between stages. Continuing a run, reanalyzing it, or generating its report
  reuses that run's directory. A new simulation, including adjusted design or
  numerical settings, requires a new run ID. Apply this convention prospectively;
  preserve existing directories and references. Development-output directories
  need not follow the physics-run naming convention.
- Keep generated inputs, reports, saved logs, results and analysis artifacts
  inside that run directory. Put any additional overall summary or manifest
  at the run root. Create stage directories as needed; do not imply that an
  unexecuted stage completed.
- Put the main `.in` file and required supporting files in `inputs/`. Keep
  generation reports in `progress/` so they are not uploaded as simulation inputs.
- Download the complete simulation bundle to `results/`. This bundle can include
  copies of the executed inputs. Keep retrieved raw files unchanged.
- Save stage reports, job IDs, completion/failure status and saved execution logs
  in `progress/`. Update status when continuing a stage; preserve prior attempts'
  evidence under distinct filenames rather than overwriting it.
- Keep parser-only validation results in `progress/native-parser-<job-id>.json`,
  linked from `validation.md`. Parser-only validation does not produce a
  simulation-results bundle or require a `results/` directory.
- For each new analysis, choose a unique analysis ID and create
  `analysis/<analysis-id>/` with the structure above. Reuse the run ID when
  analyzing that run's results. For external existing results, create a run
  directory for the new analysis and record the original source path without
  moving or duplicating the raw data.
- Use [scientific-reporting](../scientific-reporting/SKILL.md) for user-facing
  input-physics and completed-run reports in `scientific-reports/`. For iterative
  studies, place one final study report in the initiating run's report directory
  unless another location is specified, linking all covered runs. Keep LaTeX
  sources, required assets, build notes, and successfully compiled PDFs there.
  Record compilation failures explicitly when a PDF cannot be produced. Reuse
  this directory when continuing a run and preserve earlier reports with distinct
  filenames or versioned subdirectories. Stage records remain in `progress/`
  and analysis summaries and manifests remain in `analysis/<analysis-id>/`.
- Return the run directory and relevant artifact paths at each handoff. Never
  silently overwrite an existing input bundle, result directory or analysis;
  use a new run ID for a new simulation and a new analysis ID for reanalysis.
- Add the original user prompt to `prompt/` for reproducibility
