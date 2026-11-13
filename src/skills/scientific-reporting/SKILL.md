---
name: scientific-reporting
description: Produce LaTeX/PDF reports explaining OPALX inputs, assumptions, physics, and existing analysis results. Use for input-physics reports, completed runs, or a final report covering a design, optimization, or numerical-tuning study.
---

# Scientific Reporting

## Scope

Explain the configured physics, documented derivations, results, and their limitations using existing workflow artifacts. Follow the [default workflow scope](../references/workflow-scope.md) and the requested report timing:

- **Standalone run:** for a full workflow, produce one final report using the available generation, validation, simulation and analysis evidence. Produce a separate input-physics report after generation and validation only when requested.
- **Design, optimization, or numerical-tuning study:** when the study ends, produce one final report covering its iterations and relevant failed attempts, even if no acceptable configuration was found. Use stage records as evidence during the study; do not generate separate input-stage or per-simulation reports unless explicitly requested.

For general runs, target a short scientific report of at most about three pages in total, including figures and references. Many requested figures or explicitly requested detail may justify additional pages. Prioritize the objective, essential configuration and physical model, numerical findings, selected figures, interpretation and material limitations. Link detailed stage evidence; do not add appendices by default to bypass the target or sacrifice readability or necessary qualifications to meet it.

The `opalx-simulator` skill owns execution and retrieval; `beam-analyzer` owns analysis and figures. Reporting presents and interprets existing artifacts. Do not submit simulations, alter source inputs or results, or change reusable code. Do not derive new models for the setup, evaluate proxies, calculate new observables, or perform numerical comparisons; these belong to the physics or analysis stage.

Before creating artifacts, follow the shared [run layout](../references/run-layout.md).

## Inputs and outputs

- **Inputs:** user specification; local input bundles and generation/validation records; available execution records, analysis summaries, manifests, data, and figures. Include documented assumptions, derivations, constraints, and iteration records.
- **Outputs:** report source, supporting assets, compiled PDF when possible, and a build note identifying sources and the compilation command.

Write to `output/<run-id>/scientific-reports/`, outside the raw simulation directory. Create it if needed; reuse it when continuing an existing run, preserving earlier report versions.

For a multi-simulation study, use this parent run's report directory unless the user specifies another location. Each attempt's source artifacts remain under `simulations/<simulation-id>/`; comparison analysis belongs at the parent run level. Existing studies retain their original layout and source paths.

Use descriptive, stable filenames; do not silently overwrite a previous report. Keep source input, result, and analysis files read-only.

## Workflow

### 1. Gather evidence and establish scope

Read the specification and parent `progress/study.md` where available, then the relevant simulation input bundles, stage records in their `progress/` directories, individual/comparison analysis summaries, manifests, data and figures. Identify the parent run ID, covered simulation and analysis IDs, source paths and available job IDs; use actual paths for existing layouts.

Establish which stages completed and which scientific questions the evidence can answer. Match results to executed inputs using available digests and execution records; do not assume the current input bundle was executed. Distinguish input validation, simulation completion, and analysis validity: result files or a parser pass alone do not establish physical correctness.

### 2. Prepare the input-physics account

Explain the scientific objective and configured model. Cover the lattice layout and sequence, species, reference energy or momentum, and, where applicable, initial distribution and correlations, modeled effects, boundary conditions, and relevant numerical settings. Describe omissions and defaults only when supported by the configuration or documentation.

Use a parameter table with units, distinguishing supplied values, derived quantities, and technical defaults. Explain documented derivations and their assumptions without changing supplied parameters. Consult the [local OPALX input reference](../lattice-generator/references/opalx-input-reference.md) before official documentation for unclear configuration semantics. Cite substantive theoretical and software claims.

Include a concise **Physical basis and model** section in every scientific report, assuming familiarity with basic mechanics and electromagnetism. Read [Mathematical model descriptions](references/mathematical-model-descriptions.md) before writing it. Connect the scientific question to the configured elements, included or omitted effects, and observables. Briefly define necessary accelerator concepts and select the established equations needed to explain the findings, defining their symbols and approximations. A generic equation without a connection to the setup is insufficient. Reserve extended tutorials and derivations for explicitly requested detail, using existing evidence without new scientific calculations. If a suitable formulation cannot be established, identify the gap and provide the supported physical explanation.

Summarize validation outcomes and unresolved issues; label unavailable results as pending or unavailable.

### 3. Complete the results report

Incorporate the input-physics account and select existing figures and tables that address the objective. Captions should explain observables, units, selected locations or snapshots, relevant conditions, and the supported findings. Trace figures and numerical claims to source artifacts.

Prefer compact tables for comparable numerical results instead of scattering values through prose. Choose columns suited to the question, such as quantity, unit, initial/final location or value, and available change or comparison. For COF results, use convergence and closure quantities rather than imposing initial/final beam columns. Preserve source definitions, comparison conventions and validity qualifications; identify unavailable values explicitly. Use prose to explain the findings rather than repeat each entry, and do not calculate missing table values in this stage.

Read the analyzer's [physics conventions](../beam-analyzer/references/physics-conventions.md) when interpreting observables. Preserve definitions, frames, units, population selections, and distinctions between OPALX-reported and calculated quantities. Discuss existing comparisons only when definitions and sampling conditions are compatible.

Explain trends in relation to the objective, separating observations from hypotheses. Discuss available uncertainty estimates, losses or population changes, model limitations, and unresolved anomalies where relevant. State when uncertainty or convergence studies were not performed. Conclude with supported findings and unanswered questions.

### 4. Document iterations when applicable

Describe the objective, constraints, varied parameters, and selection criteria. Distinguish physical design changes from numerical adjustments. Summarize attempts with simulation IDs within the parent run (or source run IDs for existing layouts), changed settings, outcomes, available diagnostics, and documented reasons for subsequent adjustments; link to each attempt's stage records.

Discuss scientifically informative failures in the main text; group repetitive infrastructure failures concisely with links to their records. For a closed-orbit study, distinguish failure to converge from a converged orbit found to be unstable, and include available closure residuals with units. Attribute a failure to numerical settings only when supported by evidence; otherwise describe it as an unresolved cause or hypothesis.

Explain the evidence for any selected configuration, disclose differences that limit comparisons, and avoid claiming global optimality beyond explored cases or numerical convergence without supporting checks.

### 5. Build and review the deliverables

Package each report's `.tex`, required figures, and bibliography using relative paths. Use distinct filenames or versioned subdirectories for delivered versions. Include parent run, covered simulation and analysis IDs, source artifact paths, and the compilation command in the build note.

Compile using the project's pinned toolchain, choosing a new build directory for each attempt:

```bash
.venv/bin/python scripts/compile_report.py \
  output/<run-id>/scientific-reports/report.tex \
  --outdir output/<run-id>/scientific-reports/build-v1
```

Use bundled fonts and BibTeX-compatible bibliographies. See
[compiler setup and troubleshooting](../../../README.md#latex-report-compilation)
if needed.

Compile at delivery and inspect the PDF for readable figures and tables, unclipped content, correct equations and units, resolved citations and cross-references, and agreement with source values. Batch corrections and rebuild as needed for substantive errors or readability problems. Harmless formatting warnings alone do not require another build. Report any compilation or visual-review limitations.

Before delivery, check that the concise model account explains the actual accelerator problem and its observables, with central equations displayed where useful. Identify any missing mathematical account explicitly. The report is complete when its supported claims agree with the source evidence, the PDF compiles, and the content is readable without unresolved substantive errors; follow failure handling if these conditions cannot be met.

Return links to the report source and any successfully compiled PDF, briefly state the main scientific findings, and identify completed stages and remaining limitations. Update the parent study index with the report status and links. For an input-only report, make clear that simulation and results interpretation are pending.

## Failure handling

- **Missing evidence, figures, or calculations:** Deliver the supported content and identify gaps, their consequences, and required upstream work. Do not fabricate results, substitute zero for missing values, or imply skipped stages completed.
- **Failed validation, simulation, or analysis:** Include the status, warnings, and useful diagnostics. Distinguish usable partial evidence from unreliable quantities. Explain an unsuccessful study outcome without weakening validation.
- **Conflicting values or uncertain conventions:** Identify unresolved discrepancies and refer corrections to the owning stage; do not guess units, frames, or definitions.
- **Unavailable or failed LaTeX compilation:** Deliver source, assets, build instructions, and diagnostics, explicitly stating that no PDF was produced.
