# Run artifact layout

Read this reference before creating artifacts for any accelerator workflow stage.
All paths below are relative to the repository root; `output/` is not a filesystem-root directory.

```text
output/<run-id>/
├── inputs/                         # Portable OPALX input bundle
├── progress/
│   ├── generation.md               # Parameters, derivations and assumptions
│   ├── validation.md               # Checks, status and handoff decision
│   ├── simulation.md               # Job ID, execution and retrieval status
│   └── ...                         # Saved execution logs and other stage reports
├── results/                        # Retrieved raw simulation bundle
└── analysis/<analysis-id>/
    ├── scripts/
    ├── figures/
    ├── data/
    ├── analysis_summary.md
    └── manifest.json
```

- At the first requested stage, choose a descriptive, filesystem-safe run ID.
  Create a new `output/<run-id>/`; add a timestamp or suffix if that ID exists.
  Pass the run ID and directory unchanged between stages. When explicitly
  continuing an existing run, reuse its directory and preserve its artifacts.
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
- For each new analysis, choose a unique analysis ID and create
  `analysis/<analysis-id>/` with the structure above. Reuse the run ID when
  analyzing that run's results. For external existing results, create a run
  directory for the new analysis and record the original source path without
  moving or duplicating the raw data.
- Return the run directory and relevant artifact paths at each handoff. Never
  silently overwrite an existing input bundle, result directory or analysis;
  use a new run ID for a new simulation and a new analysis ID for reanalysis.
