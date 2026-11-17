# Next workflow improvements and capability evaluation

Planning review: 17 November 2026. Scope: accelerator-agent skills, shared
workflow, execution scripts and Magnus blueprints, postprocessing, and scientific
reporting, used through a declared host agent. The standalone `python-agent/`
implementation is excluded from this plan and its capability claims.

This complements `docs/workflow-improvement-plan.md`. It does not mark proposed
work implemented or authorize simulations. Preserve the existing study layout
and stage ownership; avoid creating a second workflow state system.

## Assessment of the recent changes

The workflow skill provides one entry point, lazy loading of specialist
instructions, explicit handoffs, scope limits and resumption instructions. The
validator now explicitly forbids chaining a parser success directly to simulation;
the simulator requires a saved four-layer PASS for the unchanged bundle. These
address the earlier instruction-level gaps. Whether agents reliably follow the
new instructions remains to be measured; a new orchestration engine is not the
next default step.

The report template supplies stable equation, table and figure patterns. The PDF
inspector verifies the build's PDF hash, renders every page, reads final logs and
distinguishes extraction from content/visual review. Its successful process exit
does not certify a report with unresolved findings; this is deliberate and is
documented. No additional viewer or compiler replacement is needed.

Review verification: all eight tests under `tests/scientific-reporting/` passed
offline, including template rendering, final-log findings, corrupt/hash-mismatched
PDFs, missing logs and overwrite refusal. This verifies those tool behaviors,
not future agents' scientific accuracy or visual-review compliance. No OPALX
simulations were launched for this review.

## Recommended implementation sequence

### 1. Close small scientific-reference gaps

Priority: high. Size: small. Complete before the evaluation candidate is frozen.

- In the lattice-generator OPALX reference, distinguish total optical focusing
  from normalized magnetic gradients. For an uncoupled ideal sector bend with
  the applicable conventions, document `kx = h² + K1`, `ky = -K1` and the
  assumptions/limits; verify against the supported OPALX revision. Explain that
  translating a supplied model must reproduce both focusing coefficients.
- Document magnetic rigidity explicitly, including momentum units and the charge
  convention, before quoting fields in tesla or gradients in T/m. Do not apply
  one element family's charge convention to another without verification.
- Clarify hard-edge settings and point to the actual bend documentation. Replace
  the current reference to an unspecified "detailed bend section" with a real
  local section or official link. Add a small topic index rather than lengthening
  every specialist skill.
- State that COF numerical example values are not universal defaults. Derive
  physical step length from speed and timestep; select settings from element
  scales, integration behavior and requested accuracy. Refinement should resolve
  an accuracy question, not automatically seek machine precision. A simultaneous
  change of two numerical controls is a joint sensitivity check, not independent
  convergence in each control.

Acceptance: reviewed, source-backed conventions with units and applicable version;
small offline numerical checks at multiple momenta, charges where supported, and
curvatures. No benchmark-specific target values in the reusable instructions.
These checks should test conversions/invariants rather than mirror prose.

### 2. Finish concise stage-record templates

Priority: high. Size: small. Complete before the evaluation candidate is frozen.

Keep templates with their owning skills; the workflow links to them. Keep
`progress/study.md` as the shared index. Use short fields/tables instead of
repeating full physics descriptions at each handoff:

- Generation: specification sources, supplied/derived values with units,
  assumptions, bundle/main-input path, unresolved items.
- Validation: explicit status/evidence for each layer, overall decision,
  parser job/result, digest convention, bundle identity and handoff decision.
- Execution: simulation and job IDs, submission/execution/retrieval status,
  input identity, logs/results, failure category and pending action.
- Analysis: input artifacts, requested observable/units, integrity checks,
  user-specified acceptance criteria and comparison outcome. Distinguish
  "not requested," "unavailable," "failed" and "passed."

Keep execution success, valid output data, achieved physics objectives and report
review as separate statements. A report about a failed simulation can itself be
complete and correct. Parser PASS cannot substitute for the other input checks.

Acceptance: examples covering a successful handoff, incomplete validation,
converged-but-off-target COF, failed execution with retrieved diagnostics, and
resume without resubmission. No retrospective PASS narrative for an input later
shown to violate the specification. Do not add another mandatory registry.

### 3. Define reusable result acceptance and run a small behavioral pilot

Priority: high. Size: small to medium. Establish before formal evaluation.

Use existing postprocess readers and validation functions. Add a small helper
only where reusable behavior is missing; do not build a general optimizer or
optics engine now. Separate data-integrity checks from task acceptance:

- Require reported stability only when the task requires it.
- Require both full tunes, their definitions and tolerances when requested;
  missing full tunes cannot be replaced by folded eigenvalue phases.
- Compare requested quantities only with compatible units and frames. Leave
  unsupported observables unavailable.
- Make an accepted-result check return a structured outcome and an appropriate
  failure exit when the required criteria fail. Diagnostic analyses can still
  complete successfully while clearly recording a failed physics attempt.
- Check appropriate invariants before rendering new analytic optics figures:
  positive beta, Twiss identity, periodic optics/dispersion closure, map
  symplecticity in established canonical coordinates. Do not invent such a model
  for every run; apply checks only when those calculations are requested.

For user-authorized design/matching work, make its position in the workflow clear:
save the reproducible calculation and assumptions before translating its selected
parameters into a deck. Generation, input validation and result analysis retain
their responsibilities. Do not add an autonomous design stage to ordinary runs.

Run a small pilot after offline checks, with explicit authorization for live
jobs. Include stage-only requests and interruption/recovery as well as a full
workflow. Check that agents actually read validation evidence before submission,
avoid extra studies, and inspect all pages of the final PDF.

Do not silently fix failures while collecting a formal score. During the pilot,
retain failures and make small repairs before creating the final frozen candidate.

Conditional follow-up: if the instruction gate still fails, introduce a narrow
client-side submission preflight that checks a saved four-layer decision and the
current bundle digest. It can enforce evidence presence/identity, not establish
the truth of an agent's physics review. If decorated Magnus output parsing remains
a measured problem, add a small SDK-based command emitting structured job/result
records. Reuse the existing backend; neither requires a new workflow engine.
Any registered blueprint update remains subject to the repository's permission
rule. Do not widen implementation merely to remove all agent discretion.

### 4. Freeze a reproducible evaluation candidate

Priority: essential. Do this after the bounded pilot, without waiting for every
possible workflow enhancement.

Record a clean commit and candidate tag after the current reporting changes and
chosen fixes are reviewed. Do not evaluate an unspecified dirty working tree.
Commit/tag creation is a separate release action; this plan does not perform it.

The reproducibility manifest must identify:

- Repository commit, benchmark-suite/scorer version and dependency lock hash.
- Host agent/version, exact provider/model identifier when available, system
  instructions, enabled tools/skills, context/reasoning/sampling settings, limits
  and approval policy. A repository commit alone does not define the agent.
- OPALX version/revision and container image digest; Magnus SDK/backend versions,
  actual registered blueprint definitions and the executed repository revision.
  The local `opalx:serial` tag and local YAML alone do not pin execution.
- Platform/resource allocation, reference-document policy, external access,
  report compiler/bundle and PDF renderer versions.
- Initial context, cache state, allowed runtime budgets and intervention rules.
  Record mutable or unavailable version information as a reproducibility limit.

Keep these fixed within an experiment. Hosted-model changes that cannot be pinned
must be disclosed with run dates and available provider response identifiers.
Evaluate the skills/workflow plus declared host configuration; do not attribute
one host/model's outcome to the repository alone.

### 5. Evaluate capabilities with independent criteria

Create the protocol and graders before running the formal suite. Reuse existing
benchmarks as development/regression cases, then reserve additional cases or
parameterized variants that were not used to tune the workflow. Keep reference
answers and grader internals outside the agent's accessible input material. Merely
renaming an existing lattice is not strong evidence of generalization.

| Capability | Representative task | Independent evidence |
| --- | --- | --- |
| Input generation | Supplied lattice/beam, input only | Parameter preservation, units, portable bundle, actual parser result |
| Validation | Valid, malformed and physically inconsistent inputs | Four-layer decisions, false PASS/FAIL, appropriately inconclusive infrastructure failures |
| Execution and recovery | Validated input, interrupted client/retrieval | Required handoff, one intended submission, correct job and retrieved artifact identity |
| Analysis | Existing particle or COF outputs | Observable definitions, frames/units, numerical agreement, honest treatment of absent diagnostics |
| Reporting | Fixed evidence including failed/partial runs | Supported claims, numerical traceability, compiled/inspected final PDF, readable content |
| End-to-end workflow | Transport, ring and collective-effect tasks | All required stages and scientific criteria, preservation of scope and evidence |

Include negative and scope cases: analysis-only must not launch simulations,
report-only must not compute new physics, changed input must invalidate its prior
validation, a failed/uncertain job must not be blindly resubmitted, and a converged
orbit with missing requested tunes must remain incomplete for tune acceptance.

Use analytic references, trusted independently generated numeric results, and
reviewed tolerance definitions where appropriate. Avoid grading purely from
agent-authored PASS fields or an LLM judge. Grade scientific content separately
from presentation. Human review remains appropriate for interpretations and PDF
readability; use a fixed rubric and adjudicate disagreements.

Record per attempt:

- Task success, per-stage outcomes and requirement coverage; fully autonomous
  completion separately from assisted completion.
- Physics/input errors, unsupported scientific claims, false completion claims,
  scope violations and missing provenance.
- Parser attempts, simulation submissions, repair attempts, duplicate jobs,
  report builds, tool calls and interventions.
- End-to-end wall time, model-request time, tool time, backend queue/compute,
  retrieval time and human waiting, with overlaps identified. Do not sum overlapping
  stages or subtract infrastructure failures without disclosure.
- Input/output/cached token usage and cost where available; mark unavailable
  metrics explicitly. Compare efficiency among successful tasks alongside the
  all-attempt resource usage, so failing quickly is not rewarded.

Use fresh sessions and isolated result directories. Choose budgets after the pilot
and fix them before formal runs. Report warm-cache and cold-cache conditions
explicitly. For stochastic reliability, start with at least five independent runs
per task/configuration where feasible; report counts and uncertainty, and expand
sampling if the estimates are too imprecise for the intended conclusions. Three
pilot runs do not establish a precise capability rate. Related variants/repetitions
are not all independent task families; report per-task results as well as any
aggregate, with an explicitly stated weighting scheme.

Infrastructure failures count toward end-to-end operational reliability; also
provide a separately labeled scientific-capability view for interpretable runs.
Preserve every attempt and its exclusion rationale. Do not select only successful
runs. No retries, assistance or budget extensions disappear from the results.

Completion: publish the frozen configuration, task inventory, rubrics/scorers,
all-attempt result table, accuracy/reliability and efficiency summaries, and
limitations. If comparing an improvement, rerun the same suite under matched
conditions rather than comparing only historical anecdotes.

## Work to defer until evidence justifies it

- A general workflow state engine, replacement execution backend or broad
  backend refactor.
- A general optics/design library, automatic optimization policy or mandatory
  convergence scans for all tasks.
- Additional report styling, automatic layout repair or another PDF dependency.
- Host-specific prompt/token tuning disguised as a universal workflow rule.
- Expanding the task collection indefinitely before measuring the first candidate.
- Any work on the standalone Python agent.

Recommended stopping point before formal evaluation: verified conversion guidance,
concise stage records, explicit acceptance criteria, passing reporting checks,
a bounded behavioral pilot, and a reproducible candidate manifest. Treat subsequent
failures as evaluation results and inputs to the next version, not a reason to
keep moving the frozen version.
