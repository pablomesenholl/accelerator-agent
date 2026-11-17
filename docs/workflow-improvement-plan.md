# Accelerator workflow improvement plan

Implement focused changes, preserve working behavior and scientific safeguards,
and verify each change before moving to the next. This plan extends the work
motivated by the MiniMax FODO diagnosis.

1. **Default scope for general runs — complete.** Clarify stage boundaries,
   baseline analysis and completion criteria. Produce one final scientific
   report for a full workflow, normally at most about three pages, with numerical
   result tables where useful. Additional analysis and additional reporting
   detail remain separate requests.
2. **Plotting coherence — complete.** Preserve outside axes and shared figure
   legends during export, with and without the logo. Add focused regression
   checks and checked layout examples.
3. **Multi-run study layout — complete.** One top-level run ID per prompt/workflow,
   with related simulations and failed attempts under `simulations/`, and one
   final report at the run root when reporting is requested. See the approved
   implementation below; do not reorganize existing outputs automatically.
4. **Workflow skill — complete.** [workflow](../src/skills/workflow/SKILL.md)
   selects requested stages and coordinates handoffs, completion and resumption.
   Its references own shared scope and layout, also linked by standalone stage
   skills. Specialists retain stage procedures and checks. Validation saves all
   four layer decisions before simulation; workflow and simulator check that
   evidence before submission. This is an instruction-level gate, without a new
   execution framework. Behavioral verification awaits the next benchmarks.
5. **Reference navigation and backend conventions.** Load references where they
   are needed and fill verified, version-specific documentation gaps. Reduce
   repeated source inspection without weakening checks for unresolved semantics.
6. **Lightweight report and stage-record templates.** Reduce repeated prose and
   formatting errors while preserving useful evidence and report flexibility.
7. **Reusable baseline analysis.** Build on the existing postprocess library to
   reduce run-specific code generation. Add tested analytical transport helpers
   only where justified by supported analysis needs.
8. **Resumable workflow state, if needed.** Record completed stages, job IDs,
   artifacts and pending work for recovery after interruption. Coordinate this
   with the study layout and workflow skill rather than introducing competing
   state conventions.

After the smaller changes, repeat a benchmark with explicit acceptance criteria
and record per-stage time, token use, correctness and interventions before
committing to larger automation work. Investigate MiniMax service connectivity
separately from repository workflow changes.

## Approved implementation of step 3

Use the same layout for single- and multi-simulation workflows:

```text
output/<run-id>/
├── prompt/
├── progress/study.md                 # Brief simulation index and overall status
├── simulations/
│   ├── 001-nominal/
│   │   ├── inputs/
│   │   ├── progress/                 # Generation, validation, jobs, logs, failures
│   │   ├── results/
│   │   └── analysis/<analysis-id>/
│   └── 002-displaced/                # Same structure, created as needed
├── analysis/<analysis-id>/           # Cross-simulation/design analysis, if needed
└── scientific-reports/               # One final report for the prompt/workflow
```

- Keep the timestamped top-level run ID for the entire task, including follow-up
  work continuing it. Independent new tasks get new run IDs. Use a short numbered
  simulation ID within the run for each configuration or deliberate new execution.
  FODO normally has one simulation; DBA COF may have nominal, displaced and
  adjusted attempts. Extra attempts remain within the originally authorized task.
- Preserve failed attempts and their inputs, validation evidence and job IDs.
  Give changed configurations and deliberate reruns new simulation directories;
  retain earlier parser-attempt evidence under distinct filenames. Reconnecting
  or recovering a download reuses the existing job and simulation directory.
- Record simulation ID, purpose/changes, status, job IDs and artifact links in
  `progress/study.md`. Keep this a short Markdown index, not a new state engine.
  Handoffs identify both the parent run and the selected simulation directory.
  Validation evidence must match the exact input bundle used by each simulation.
- Store per-simulation analysis locally and comparisons at the parent run level.
  Trace comparisons to specific simulation IDs, sources and analysis selections.
  Reporting uses the parent run's report directory and includes relevant failed
  attempts. Input-only and analysis-only requests retain their existing scope;
  this convention does not automatically trigger simulations or reports.
- First edit `src/skills/workflow/references/run-layout.md` as the authoritative layout.
  Align path examples and handoffs in the five stage skills, workflow-scope
  reference, README, and the affected OPALX-input and postprocess API references.
  Keep descriptions brief and link to the shared layout rather than repeating it.
- Leave existing outputs, historical fixtures, backend scripts and blueprints
  unchanged. The current backend accepts explicit input and download paths.
  Continue to support reading existing runs in their original layout.
- Verify skill structure and links, check for contradictory path instructions,
  and review single-simulation, nominal/displaced comparison, failed-attempt,
  reanalysis and reconnect scenarios. No simulation is needed to implement the
  documentation change. Run the requested FODO and DBA COF benchmarks afterward
  as separate tasks, each with its own top-level run directory.
