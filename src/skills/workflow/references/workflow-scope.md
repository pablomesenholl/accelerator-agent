# Default workflow scope

Use this scope when selecting stages and deliverables for a general run. Explicit
user requests take precedence; additional analysis and additional reporting detail
are separate choices.

- Run only the requested stages and their necessary prerequisites. An input-only
  request ends with generation and any requested validation; analyzing existing
  results does not require a new simulation or automatically require a PDF.
- A full workflow covers generation, validation, simulation, baseline analysis,
  and one final scientific report. Keep related simulations and failed attempts
  under one prompt/workflow run ID, following the [run layout](run-layout.md).
  Use stage records as evidence; produce separate input-stage or per-simulation
  scientific reports only when requested. If a stage fails, report the actual
  completion status and supported findings.
- Derive quantities needed to construct the requested setup and perform the
  required correctness checks. Resolve ambiguities that affect the input or
  interpretation; do not independently redesign or rematch a supplied setup.
- Extend analysis for specifically requested observables or studies, or for a
  material discrepancy that must be investigated to answer the question reliably.
  A request for more reporting detail expands explanation of existing evidence;
  it does not authorize new calculations or simulations in the reporting stage.
- Use the local references first. Consult source code for a concrete unresolved
  semantic question or discrepancy, rather than auditing the backend by default.
  Record framework defects separately and state their effect on usable results;
  a full implementation investigation is not a default run deliverable.
- Keep stage records concise: status, artifact paths, necessary assumptions or
  derivations, checks and material findings. Link detailed evidence rather than
  repeating it across records and the scientific report.
- Finish each stage when its requested artifacts and required checks are complete,
  or explicitly report why it could not complete. Batch presentation corrections;
  harmless formatting warnings or cosmetic refinements alone should not prolong
  delivery. Preserve scientific validity, readability and material limitations.
