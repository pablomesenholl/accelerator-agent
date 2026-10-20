# Development guidance

This repository develops an accelerator beam dynamics agent based on the
ColliderAgent architecture. Keep changes small and consistent with its separation
of reusable skills, Magnus blueprints, and execution scripts.

- Put workflow instructions in `src/skills/`, backend job definitions in
  `src/blueprints/`, and execution code in `scripts/`. Keep detailed OPALX syntax
  in the lattice-generator reference rather than duplicating it here.
- Use the project `.venv` for Python and Magnus commands. See `README.md` for
  setup with `uv sync --locked`.
- Distinguish development requests from physics runs. For a physics run, follow
  the relevant skills and write the requested inputs and results; do not change
  reusable skills, blueprints, or execution code unless development work is
  requested. Report framework defects separately.
- Preserve the workflow boundaries: input generation, validation, simulation,
  and analysis are separate stages. Report which stages actually completed.
- Preserve supplied physics parameters, document derived quantities and
  assumptions, and use the local OPALX reference before consulting official
  documentation for missing or ambiguous features.
- Use `tests/` for development examples and checks, and `output/` for generated
  run results. Run checks appropriate to the change, if asked for in developement; describe what was checked and any limitations. Do not launch simulations merely for a documentation edit.
- Local blueprint edits do not update Magnus automatically. When execution
  requires a blueprint change, inspect the registered version and register the
  intended update explicitly, but ask for permission by the developer; otherwise reuse the existing blueprint.
- Preserve unrelated local changes and avoid committing generated outputs or
  changing dependencies unless the task calls for it.
