# Input validation

<!-- Complete before simulation; replace placeholders with decisions and evidence. -->

- Overall status: <PASS / FAIL / INCONCLUSIVE>
- Parent run / simulation ID: <run-id> / <simulation-id>
- Purpose / changes from previous attempt: <brief description and link, or none>
- Specification / generation record: <links>
- Validated input bundle: <path>
- Main input: <path relative to bundle>
- Parser input digest: <input_digest from saved parser result>

## Four-layer assessment

| Layer | Decision | Supporting evidence / issues |
| --- | --- | --- |
| 1. Native syntax | <PASS / FAIL / INCONCLUSIVE> | <parser evidence link> |
| 2. Structural / semantic | <PASS / FAIL / INCONCLUSIVE> | <references, dependencies and configuration checks> |
| 3. Specification | <PASS / FAIL / INCONCLUSIVE> | <agreement with requested parameters and effects> |
| 4. Physical consistency | <PASS / FAIL / INCONCLUSIVE> | <units, normalization and relevant sanity checks> |

## Native parser evidence

- Magnus job ID / saved structured result: <ID and link>
- Command / OPALX version and revision: <values or linked result fields>
- Exit code / diagnostics: <code and exact success diagnostic or failure evidence>

## Handoff

- Blocking issues / warnings: <locations and proposed corrections, or none>
- Decision / next action: <permit unchanged bundle / return for correction / resolve incomplete checks>
- Study index: <link to parent progress/study.md>

Overall PASS requires all four layers PASS for this unchanged bundle; incomplete
checks are INCONCLUSIVE. Parser PASS alone does not permit simulation.
