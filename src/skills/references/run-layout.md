# Run artifact layout

Read this reference before creating artifacts for any accelerator workflow stage.
All paths below are relative to the repository root; `output/` is not a filesystem-root directory.

Use the [default workflow scope](workflow-scope.md) to select stages and reports.
Stage records document evidence; a full workflow produces one final scientific
report, with separate input-stage or per-simulation reports only when requested.

The **run ID** identifies one prompt/workflow, including its comparisons and
failed attempts. A **simulation ID** identifies one configuration or execution
attempt within that run. Use this layout even for a single simulation:

```text
output/<run-id>/
├── prompt/                              # Original prompt and relevant follow-ups
├── progress/study.md                    # Simulation index and overall status
├── simulations/
│   ├── 001-nominal/
│   │   ├── inputs/                      # Portable OPALX input bundle
│   │   ├── progress/
│   │   │   ├── generation.md
│   │   │   ├── validation.md
│   │   │   ├── native-parser-<job-id>.json
│   │   │   ├── simulation.md            # Job IDs, execution/retrieval status
│   │   │   └── ...                      # Logs and failure evidence
│   │   ├── results/                     # Unchanged retrieved simulation bundle
│   │   └── analysis/<analysis-id>/
│   └── 002-displaced/                   # Same structure, created as needed
├── analysis/<analysis-id>/              # Cross-simulation/design analysis, if needed
└── scientific-reports/                  # One final report for the workflow
```

- At the first requested stage of a new physics task, create
  `output/<descriptive-slug>-<YYYYMMDDTHHMMSSZ>/`, for example
  `output/dba-cof-20261103T173126Z/`. Use a short lowercase description with
  hyphens between words and the actual directory-creation time in UTC, to second
  precision; `Z` denotes UTC. If the complete ID exists, append `-02`, `-03`,
  etc. rather than overwriting it. Choose the ID once and pass it unchanged
  between stages. Follow-ups continuing the task, additional simulations,
  reanalysis and reporting reuse this directory. An independent task gets a new
  run ID. Development-output directories need not follow this naming convention.
- Within the run, choose unique numbered simulation IDs with short descriptions,
  such as `001-main`, `002-displaced`, or `003-refined`. Prepare each changed
  configuration or deliberate new execution in a new simulation directory.
  Preserve failed attempts, including input-generation and validation failures;
  missing results do not erase an attempt. Extra simulations still require scope
  authorization from the task. Reconnecting to a job or recovering retrieval
  reuses its simulation directory and job ID; do not resubmit a completed job.
- Keep generated inputs, reports, saved logs, results and analysis artifacts
  inside the parent run directory. Create stage directories as needed; do not
  imply that an unexecuted stage completed. Save the original prompt in `prompt/`.
- Maintain a concise `progress/study.md` at the parent run level. Record overall
  status and a table of simulation ID, purpose/changed settings, stage status,
  parser/simulation job IDs and artifact links. Update it as stages progress;
  distinguish planned, failed and completed work. Use links to detailed records
  rather than duplicating them; this is not a separate state-management system.
- Within each `simulations/<simulation-id>/`, put the main `.in` and required
  supporting files in `inputs/`, stage records and logs in `progress/`, and the
  complete retrieved bundle in `results/`. Upload only `inputs/`, not the study
  directory or stage records. Keep retrieved raw files unchanged.
- Keep parser evidence in that simulation's
  `progress/native-parser-<job-id>.json`, linked from its `validation.md`. Retain
  distinct parser attempts and match validation evidence to the exact input
  bundle submitted for execution. Changed inputs require revalidation.
- For each new analysis, choose a unique analysis ID. Use
  `simulations/<simulation-id>/analysis/<analysis-id>/` for individual analysis
  and the parent `analysis/<analysis-id>/` for comparisons or design analysis.
  Both contain `scripts/`, `figures/`, `data/`, `analysis_summary.md` and
  `manifest.json`. Record source simulation IDs, paths and selections; discover
  files within each simulation's results, not across the whole study implicitly.
  Reanalysis creates a new analysis ID, not a new simulation. For external existing
  results, record source paths without moving or duplicating the raw data; an
  analysis-only task need not create simulation directories.
- Use [scientific-reporting](../scientific-reporting/SKILL.md) for user-facing
  input-physics and completed-run reports in the parent `scientific-reports/`.
  Produce one final report for the prompt/workflow when requested, including
  comparisons and relevant failed attempts; separate simulation reports require
  an explicit request. Keep LaTeX
  sources, required assets, build notes, and successfully compiled PDFs there.
  Record compilation failures explicitly when a PDF cannot be produced. Reuse
  this directory when continuing a run and preserve earlier reports with distinct
  filenames or versioned subdirectories.
- At each handoff, return the parent run directory, selected simulation ID and
  directory when applicable, and actual input/result/evidence paths. The Magnus
  `simulation` argument points to the selected `inputs/` bundle (or its single
  `.in` file), not its parent simulation directory. Never silently overwrite an
  existing input bundle, result directory or analysis.
- Apply this convention to new workflows. Read and continue existing runs in
  their original layout, recording actual source paths. Do not reorganize old
  outputs, historical fixtures or references automatically. The directory
  convention does not change input-only or analysis-only task scope.
