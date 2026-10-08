---
name: opalx-simulator
description: Run prepared OPALX accelerator simulations through the Magnus backend and retrieve their results. Use this skill when the user wants to execute an OPALX simulation, inspect the run result, or recover the generated simulation outputs.
---

# OPALX Simulator

## Overview

This skill executes a prepared OPALX simulation through the `opalx-simulation` Magnus blueprint.

A simulation may consist of a single OPALX input file or a simulation directory containing the main input file together with required supporting files.

The skill is responsible for simulation execution and result retrieval. It assumes that the OPALX simulation input has already been prepared. It does not generate or modify the OPALX model in this first version.

Use the `magnus` skill for generic Magnus configuration, job management, status checks, output retrieval, and backend error recovery.

## Inputs

The `opalx-simulation` blueprint accepts:

- `simulation` — required Magnus `FileSecret` containing either a single OPALX input file or a simulation directory with the input file and any required auxiliary files.
- `input_file` — required name or relative path of the OPALX `.in` file to execute inside the simulation input.
- `output` — local path where Magnus downloads the completed simulation directory. Default: `opalx-output`.

`input_file` must remain inside the uploaded simulation input. For a single-file upload, it must identify that uploaded file.

## Outputs

The Magnus job result may contain:

- `success` — whether the complete simulation workflow succeeded.
- `message` — execution summary.
- `returncode` — OPALX process return code when OPALX was launched.
- `input_file` — relative input file that was executed.
- `output_path` — requested local download path when output publication succeeds.
- `output_secret` — Magnus file reference for the published simulation directory.

The complete simulation directory is published as the output, including the original inputs and any files produced or modified during the OPALX run. The exact OPALX output files depend on the commands and diagnostics configured in the input.

OPALX stdout/stderr are available through the Magnus job logs.

## Workflow

### Step 1: Check the input

Confirm that the requested OPALX simulation input exists.

If a simulation directory is provided, identify the main OPALX `.in` file and confirm that required supporting files are present. Use its path relative to the simulation directory as `input_file`.

Do not rewrite or alter the physics configuration unless the user explicitly asks for a change. Input generation and modification belong to the corresponding model/lattice skill.

### Step 2: Prepare the blueprint invocation

Use the `opalx-simulation` blueprint with:

- `--simulation` for the prepared OPALX file or simulation directory.
- `--input_file` for the name or relative path of the `.in` file inside the simulation input.
- `--output` for the desired local output path.

If the installed blueprint interface appears inconsistent with this skill, verify the current schema with:

```bash
magnus blueprint schema opalx-simulation
```

### Step 3: Run the simulation

Submit the simulation through the `opalx-simulation` blueprint:

```bash
magnus run opalx-simulation -- \
  --simulation path/to/simulation \
  --input_file path/to/input.in \
  --output path/to/results
```

For a single-file simulation, `--simulation` points to the `.in` file and `--input_file` is that file's name.

For a simulation directory, `--simulation` points to the directory and `--input_file` is the `.in` file path relative to that directory.

Use an explicit `--output` path for reproducible result placement, even though the blueprint default is `opalx-output`.

Capture the job ID printed by Magnus.

### Step 4: Check the result and retrieve outputs

Inspect the Magnus result and confirm:

- `success` is `true`.
- `returncode` is `0` when OPALX was launched.
- the expected `input_file` was executed.
- `output_path` is present and the simulation directory was retrieved.

If the user requested a specific diagnostic or downstream analysis, verify that the corresponding output file exists before handing the result to another skill.

A failed OPALX run may still produce a retrieved simulation directory. Inspect it together with the Magnus logs when diagnosing failures.

## Usage

Single-file simulation:

```bash
magnus run opalx-simulation -- \
  --simulation path/to/fodo.in \
  --input_file fodo.in \
  --output results/fodo
```

Simulation directory:

```bash
magnus run opalx-simulation -- \
  --simulation path/to/simulation/ \
  --input_file inputs/fodo.in \
  --output results/fodo
```

Generic Magnus behavior is documented in the `magnus` skill.

## Error Handling

If execution fails, first inspect the Magnus job result and OPALX logs using the `magnus` skill.

Distinguish between:

1. **Input preparation failure** — for example, the `.in` file is missing, `input_file` is absolute, escapes the simulation directory, or does not match a single-file upload.
2. **OPALX failure** — OPALX was launched but returned a nonzero `returncode`. Use the OPALX diagnostics in the Magnus logs and inspect any retrieved simulation outputs.
3. **Output publication failure** — OPALX may have completed successfully, but the simulation directory could not be published or downloaded. Check `output_upload_error` if present.

Do not repeatedly resubmit an unchanged failing simulation.

## Examples

### Single-file simulation

```bash
magnus run opalx-simulation -- \
  --simulation examples/fodo.in \
  --input_file fodo.in \
  --output results/fodo
```

### Simulation directory

```bash
magnus run opalx-simulation -- \
  --simulation examples/fodo-bundle/ \
  --input_file fodo.in \
  --output results/fodo-bundle
```
