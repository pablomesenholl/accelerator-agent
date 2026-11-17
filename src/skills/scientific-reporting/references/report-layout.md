# Report layout and inspection

Copy the report template into `scientific-reports/`; replace all example content.
Use verified stage evidence, relative figure paths and a local bibliography.

- Split long equations with `aligned`; avoid new physics macros for routine reports.
- Use `tabularx` wrapping columns for long labels and qualifications. Keep numbers
  at precision justified by the evidence and put units in headers or a unit column.
- Use the template's width/height limits with `keepaspectratio` for figures.
  Prefer normal `[htbp]` placement; avoid forced placement and manual spacing.
- Meet the normal length target by selecting content. Do not shrink fonts or
  repeatedly tune spacing to force a page count. Studies may need more pages.

Run the compiler directly, then `scripts/inspect_report.py <build-directory>`.
Use `--offline` on the compiler once the template's resources are cached. The
inspector verifies the PDF hash and creates a fresh `inspection/` with JSON,
page text and page PNGs (150 dpi). It never overwrites an existing inspection.

`status=completed` means extraction, rendering and log checks ran successfully;
findings can still require correction. Failed/incomplete inspection exits nonzero.
Inspect the findings rather than treating the process exit code as report approval:

| Finding | Action |
| --- | --- |
| Unresolved references/citations or bibliography errors | Correct before delivery |
| Overfull boxes | Inspect the affected equation/table/text and correct visible overflow |
| Underfull boxes or float-placement notices | Advisory; change only for a readability problem |
| Missing logs or failed rendering | Review incomplete; record the limitation |

View all page PNGs from the final build and check content against upstream
artifacts. Text extraction is useful for locating content, not checking layout.
Rendering cannot automatically certify absence of clipping or scientific validity.
The helper leaves `content_review` and `visual_review` as `not_performed`; record
the actual review, PDF hash, material findings and limitations in the build note.
Batch corrections before rebuilding. Keep the current final sources/assets and
retain build evidence; a later build needs its own inspection.
