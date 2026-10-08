---
name: lattice-generator
description: Generate complete OPALX accelerator simulation input files and directories from natural-language specifications. Use this skill when the user wants to create or modify an accelerator lattice, beam configuration, particle distribution, or other OPALX simulation inputs. This skill prepares simulation inputs but does not validate or execute them.
---

# Lattice Generator

## Overview

This skill translates natural-language accelerator simulation specifications into complete OPALX simulation inputs using the OPALX extended MAD-inspired input language.

The generated simulation input consists of a main `.in` file and, when required, additional supporting files organized in a simulation directory.

The skill is general-purpose and should support arbitrary accelerator configurations described by the user, subject to the capabilities of OPALX.

This skill is responsible for input generation only.

- Input validation is delegated to the `lattice-validator` skill.
- Simulation execution and result retrieval are delegated to the `opalx-simulator` skill.
- Magnus job management is part of the `magnus` skill.

## Inputs

The skill accepts a natural-language description of an accelerator simulation, potentially including:

- **Lattice specification** — accelerator elements, their types, lengths, strengths, positions, and ordering.
- **Beam parameters** — particle species, reference energy or momentum, bunch charge, and particle count.
- **Particle distribution** — distribution type and initial phase-space parameters, or an external distribution file.
- **Simulation configuration** — space-charge settings, numerical tracking parameters, and output diagnostics.
- **Output location** — optional destination directory and name of the main OPALX input file.
- **Supporting files** — optional existing distribution files, field maps, or other external data required by the simulation.

Not all parameters must be explicitly provided. Use documented OPALX defaults when appropriate.

If essential information is missing and cannot be determined without making unsupported physical assumptions, request clarification from the user.

## Outputs

The skill produces a self-contained OPALX simulation input directory containing:

- **Main input file** — a complete `.in` file defining the requested OPALX simulation.
- **Supporting files** — any required auxiliary files, such as particle distributions, field maps, or additional OPALX input files.
- **Simulation directory path** — the location of the generated input directory.
- **Main input file path** — the path of the `.in` file relative to the simulation directory.

The output must be directly usable as input to the `opalx-simulator` skill.

For simulations requiring no auxiliary files, the directory may contain only the main `.in` file.

## Workflow

### Step 1: Interpret the simulation request

Extract the accelerator configuration and simulation requirements from the user's natural-language description.

Identify:

1. Accelerator lattice elements and their properties.
2. Element ordering and beamline geometry.
3. Beam species and reference parameters.
4. Initial particle distribution.
5. Field solver requirements, including whether space charge is enabled.
6. Tracking parameters and stopping conditions.
7. Requested diagnostics and output settings.

Distinguish explicitly specified parameters from derived values and assumptions.

If the request is incomplete, use documented defaults where appropriate. Ask for clarification when a missing parameter is essential to defining the requested physical system.

Do not introduce additional physical effects or lattice elements that the user did not request.

### Step 2: Consult OPALX documentation

Use **The OPALX Universe** as the primary reference for OPALX input syntax, commands, conventions, and supported physics.

Consult the relevant sections of the documentation before generating unfamiliar OPALX constructs.

Important topics include:

- Input language and command syntax.
- Physical units and coordinate conventions.
- Accelerator elements and beamlines.
- Beam and particle distribution definitions.
- Field solvers.
- Tracking commands and numerical settings.
- Output and diagnostic configuration.
- External file dependencies.

When available, consult `references/opalx-input-reference.md` for a concise summary of relevant OPALX syntax and examples.

For syntax not covered by the local reference, consult the full OPALX documentation.

The official OPALX repository and its maintained regression examples may be consulted to resolve ambiguities or identify changes to the documented input interface.

References:

- [OPALX GitHub repository](https://github.com/OPALX-project/OPALX)
- [OPALX documentation repository](https://github.com/OPALX-project/opalx-manual)
- [OPALX regression tests](https://github.com/OPALX-project/regression-tests-x)

**Important:** Distinguish current OPALX syntax from legacy OPAL syntax. Do not assume that historical OPAL commands or parameters remain supported by OPALX.

Do not invent undocumented commands, attributes, or physical models.

### Step 3: Construct the OPALX input file

Generate a complete OPALX `.in` file describing the requested accelerator simulation.

Depending on the specification, the file may contain:

1. Global options and simulation title.
2. Constants, parameters, and derived quantities.
3. Accelerator element definitions and placements.
4. Beamline or lattice definitions.
5. Particle distribution and emission source definitions.
6. Beam definitions.
7. Field solver configuration.
8. Tracking configuration and simulation commands.
9. Output and diagnostic settings.
10. Input termination statement.

Use the syntax and structures appropriate to the selected OPALX configuration.

Follow these principles:

- Define parameters and reusable quantities clearly.
- Use descriptive names for elements and beamlines.
- Preserve the requested lattice geometry and element order.
- Respect documented OPALX unit conventions.
- Use documented expressions and parameter relationships when deriving quantities.
- Include the OPALX statements necessary for the requested simulation configuration.
- Use comments to clarify non-obvious parameters, unit conversions, or assumptions.
- Prefer readable, organized input files over unnecessarily compact representations.

Do not restrict input construction to a fixed template or predefined lattice topology.

### Step 4: Prepare the simulation directory

Create a dedicated directory for the generated simulation input.

Place the main `.in` file and all necessary supporting files inside this directory.

For example:

```text
simulation/
├── simulation.in
└── supporting-files/
    └── ...
```

The exact directory structure may depend on the simulation.

Ensure that file references within the input use appropriate paths relative to the simulation directory.

If external data files are required:

- Include user-provided files when available.
- Generate supporting files when their construction is specified and supported.
- Do not fabricate missing field maps, measurement data, or other physical input data.
- Request required external data when it cannot be generated from the available information.

The resulting directory should be self-contained and portable to the OPALX execution environment.

### Step 5: Return the generated input

Report the generated simulation input to the user or calling agent.

Provide:

- The simulation directory path.
- The relative path of the main `.in` file.
- A brief summary of the generated lattice and simulation configuration.
- Any assumptions or documented defaults used.
- Any unresolved dependencies or limitations.

The output paths must be compatible with the `opalx-simulator` interface:

- `simulation` — path to the complete simulation directory.
- `input_file` — relative path to the main `.in` file inside that directory.

Do not launch the simulation.

Do not perform syntax validation, physical consistency checks, or numerical verification. These responsibilities belong to the `lattice-validator` skill.

## Usage

This skill is invoked when a user or agent requests the preparation of an OPALX simulation input.

For example:

> Generate an OPALX input for a single FODO cell consisting of focusing and defocusing quadrupoles separated by drifts. Use the specified beam and lattice parameters, disable space charge, and prepare the complete input directory for subsequent simulation.

The skill should produce the required files without executing OPALX.

The prepared simulation can subsequently be passed to the `lattice-validator` skill and, after validation, to the `opalx-simulator` skill.

## Error Handling

If input generation cannot be completed:

1. **Missing parameters** — identify the essential information required and request clarification.
2. **Unsupported OPALX feature** — explain which requested functionality is unsupported or cannot be confirmed from the available documentation.
3. **Missing auxiliary files** — identify required external dependencies and request the necessary files.
4. **Ambiguous syntax** — consult the official OPALX documentation and maintained regression examples. Do not guess unsupported syntax.
5. **File creation failure** — report the affected file or directory and the reason it could not be created.

Do not silently replace unsupported features with different physical models.

Do not claim that an input has been validated or successfully simulated. Report generation completion separately from validation and execution status.

## Examples

### Minimal example: Single FODO cell without space charge

**Request:**

Generate an OPALX input for one FODO cell with specified quadrupole strengths, quadrupole lengths, and drift lengths. Track the specified particle beam through the cell without space charge.

**Expected behavior:**

- Interpret the lattice specification.
- Construct the necessary quadrupole and drift elements.
- Define the FODO beamline.
- Configure the beam and initial distribution.
- Configure tracking without space charge.
- Create the complete OPALX input directory.
- Return the directory and main input file paths.

The input is then available for independent validation and execution.

### Typical example: Accelerator simulation with auxiliary files

**Request:**

Generate an OPALX input for a beamline containing drifts, quadrupoles, and an RF cavity using a supplied field map. Use the requested beam distribution and tracking settings.

**Expected behavior:**

- Construct the requested beamline using documented OPALX elements.
- Configure the beam, distribution, and tracking parameters.
- Include the supplied field map in the simulation directory.
- Reference the field map using a portable relative path.
- Produce a complete OPALX input directory.
- Return the main input file path and simulation directory location.

## Reference Documentation

Primary reference:

- **The OPALX Universe** — OPALX user guide, physics manual, and input language reference.

Skill-specific reference:

- `references/opalx-input-reference.md` — concise OPALX syntax guide and usage conventions (to be added).

The reference documentation supports input generation but does not replace the official OPALX documentation for unfamiliar or evolving features.
