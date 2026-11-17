---
name: workflow
description: Coordinate OPALX accelerator workflows, including stage selection, artifact handoffs, study layout, completion and resumption. Use for full runs, multi-simulation studies or continuing a workflow; shared scope and layout also apply to standalone stages.
---

# Workflow

Coordinate the requested work through the specialist skills below. This skill
owns stage selection and handoffs; specialists own their procedures and checks.
It does not add execution permissions or authorize extra studies.

## Scope and setup

1. Read [workflow scope](references/workflow-scope.md) to select requested stages,
   necessary prerequisites and deliverables. Reuse valid existing evidence; an
   input-only, analysis-only or report-only request does not imply a full run.
2. Follow [run layout](references/run-layout.md) before creating artifacts. Keep
   one parent run for the task, including follow-ups and failed attempts. Save
   the prompt and record the selected stages, deliverables and any explicit
   acceptance criteria briefly in `progress/study.md`.
3. Load the next specialist skill and references needed for its current work.
   For standalone stages, use the shared scope/layout and that specialist directly.

## Stages and handoffs

| Stage | Owner | Evidence passed onward |
| --- | --- | --- |
| Generation | [lattice-generator](../lattice-generator/SKILL.md) | Portable input bundle, main input path, generation record with supplied/derived parameters and assumptions |
| Validation | [lattice-validator](../lattice-validator/SKILL.md) | Saved four-layer decision for that bundle, parser evidence and input digest |
| Simulation | [opalx-simulator](../opalx-simulator/SKILL.md) | Job ID, execution/retrieval status, actual result paths and execution record |
| Analysis | [beam-analyzer](../beam-analyzer/SKILL.md) | Summary, manifest, reproducible scripts, checked figures/data and limitations |
| Reporting | [scientific-reporting](../scientific-reporting/SKILL.md) | One final report when requested, sources, build record and PDF status |

At each handoff, carry the parent run path, selected simulation ID/directory
when applicable, actual artifact/evidence paths, status and unresolved issues.
Update `progress/study.md` with links and the next action; keep detailed evidence
in the owning stage's artifacts.

Before simulation submission, read the saved validation record: all four layers
must be `PASS` for the exact unchanged input bundle. Apply the validator's handoff
decision; a parser pass or successful Magnus command alone is insufficient.
Complete and save validation before invoking simulation, including for reruns.

Check required upstream evidence before each stage. If upstream work fails,
continue only with supported partial analysis or requested failure reporting,
explicitly qualifying usable evidence. Reporting consumes existing evidence;
route missing calculations to analysis only within the task's scope. Stop once
requested deliverables and checks are complete, and state which stages completed,
failed or were not performed.

## Failure and resumption

- Route input corrections to generation and revalidate changed bundles. Preserve
  failed attempts; use new simulation IDs for changed configurations or deliberate
  new executions. Follow the validator's repair limit and stop if unresolved.
- On resumption, read the study index and linked evidence. Inspect existing Magnus
  job status/results before any submission; reconnect or recover downloads using
  the existing job ID. Continue from the first incomplete required stage.
- If required work cannot complete, record the blocker and deliver supported
  findings. Include relevant failures in the final report when reporting is
  requested; do not imply missing stages succeeded.
