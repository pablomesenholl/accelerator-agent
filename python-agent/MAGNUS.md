# Magnus integration (Phase 3)

The standalone agent can now use the existing `opalx-simulation` Magnus blueprint.
No skills, blueprints, simulation scripts, or dependencies were changed. The
adapter uses the installed Magnus SDK and its existing connection configuration.
It never invokes a shell, registers a blueprint, or executes `MAGNUS_ACTION`.

Magnus tools are opt-in, so ordinary generation tasks keep their smaller tool list.
For future LLM tasks, use `agent.py --enable-magnus`. Submission additionally needs
`--allow-simulation --validation-report validation.json`. The report is relative
to the workspace and is read before the model starts. The operator must review
it; the model cannot enable execution or replace that initial report during a task.
Native parser-only validation is still unavailable. A report is evidence supplied
by the operator, not proof produced by a new validation engine.

## Use without Qwen

All examples below run the adapter directly, without an LLM. Run from the repository
root, with Magnus/Docker running and a prepared input under the chosen workspace.

Check the registered blueprint (read-only):

```bash
.venv/bin/python python-agent/magnus_cli.py --workspace output/my-run inspect
```

Check a prepared input bundle and compute its digest (no physics validation):

```bash
.venv/bin/python python-agent/magnus_cli.py --workspace output/my-run input input lattice.in
```

Here `output/my-run/input/` contains `lattice.in` and any auxiliary files. A single
file is also supported: use `input/lattice.in lattice.in`. Input paths must stay
inside the workspace. Bundles cannot contain links, special files, or the workspace
root itself. The digest covers the selected main input path and all bundle files.

After reviewing the input and the original specification, the operator prepares
`output/my-run/validation.json` using the paths/digest returned above:

```json
{
  "status": "PASS",
  "simulation": "input",
  "input_file": "lattice.in",
  "input_digest": "COPY_THE_REVIEWED_BUNDLE_DIGEST_HERE",
  "checks": {
    "structure": "PASS",
    "specification": "PASS",
    "physics": "PASS",
    "native_parser": "SKIPPED_NOT_AVAILABLE"
  }
}
```

Use `PASS` only for checks actually completed. The native-parser skip records the
current exception explicitly allowed in the local validator skill; it does not
claim native syntax validation. Keep the report outside the input bundle, otherwise
writing the report changes the bundle digest. Changing any input requires review
and a matching new report.

Submit explicitly after review:

```bash
.venv/bin/python python-agent/magnus_cli.py --workspace output/my-run \
  --allow-simulation --validation-report validation.json submit input lattice.in
```

Submission returns a job ID without waiting for tracking. Use that exact ID:

```bash
.venv/bin/python python-agent/magnus_cli.py --workspace output/my-run status JOB_ID
.venv/bin/python python-agent/magnus_cli.py --workspace output/my-run logs JOB_ID
.venv/bin/python python-agent/magnus_cli.py --workspace output/my-run fetch JOB_ID
```

Log output is bounded; `logs` accepts `--page` and `--start` to continue. The model
has the same operations as ADK tools: `inspect_opalx_backend`,
`inspect_simulation_input`, `submit_opalx_simulation`, `get_opalx_job_status`,
`read_opalx_job_logs`, and `retrieve_opalx_outputs`.

## Job records and results

Records are persisted under the workspace's `.magnus-jobs/`. General agent file
tools cannot modify this directory. Only recorded job IDs can be inspected through
this adapter; restarting the client with the same workspace reconnects to them.
Keep the workspace private and use the same configured Magnus backend when resuming.
Avoid concurrent clients changing the same workspace.

Repeated submission of the same input paths/digest returns the recorded job ID,
including after completion or failure. It never silently reruns unchanged inputs.
For an intentional independent rerun, use a separate workspace. If submission loses
its response, its record is marked uncertain and blocks automatic retries. Inspect
Magnus's jobs and reconcile the record manually; the backend job may already exist.
This cannot guarantee exactly-once backend execution across a lost response, but it
prevents an automatic second submission. Client cancellation does not kill a job.

Status queries distinguish backend terminal status, OPALX return code and reported
input, and downloaded outputs. Failed OPALX jobs can still publish useful files.
Results go to `magnus-results/<record-id>/`; existing destinations are not
overwritten. Downloaded tar bundles reject absolute/traversal paths, links and
special members before extraction. The SDK's automatic action execution is bypassed.
The adapter persists the result and file reference, but never sends credentials or
download secrets to the model. Expired/unavailable output references are reported
as retrieval errors, not simulation failures.

Read-only status/log polling is exempt from the identical-call guard. Submission
is not exempt. Each check is one bounded backend request; there is no autonomous
long polling loop. The model can return the job ID and let another task resume it.

## Verification and next step

37 offline tests passed, with the live Ollama test skipped. Adapter tests use a
fake backend and cover submission gates, changed inputs, duplicate/uncertain
submissions, reconnecting, bounded logs, failed-job outputs, and archive/path rules.
The real read-only `inspect` command also confirmed the registered schema is
compatible. An initial sandbox run stalled at thread/event-loop wakeup; the suite
and backend inspection completed outside that sandbox.

A real non-LLM smoke test passed on 2026-10-21 in about 39 seconds. Job
`bab44fba338aa7d6` returned backend `Success`, OPALX code 0, and the expected input
filename. A new adapter instance reused its job ID without submitting a second job.
Logs and outputs were retrieved; the original input hash was preserved, the SDDS
statistics file was nonempty, and the HDF5 file contained 11 particle snapshots.
Artifacts are under `output/python-agent/magnus-smoke-20261021T174437370282Z/`.
No Qwen requests, blueprint changes, or skill/script changes were involved.

## Repeat the non-LLM integration smoke test

The harness uses the existing reviewed validator FODO fixture, not generated model
output. `tests/python_agent/fixtures/reviewed_fodo.json` pins the hashes of its
input, original specification, and validation report. A changed fixture is rejected
until it is reviewed and the manifest is deliberately updated. It reuses the
existing current-policy validation (including the explicit native-parser skip),
without claiming a general-purpose automatic validator.

Prepare a fresh workspace without contacting Magnus:

```bash
.venv/bin/python tests/python_agent/smoke_magnus.py
```

Explicitly submit and exercise the real backend:

```bash
.venv/bin/python tests/python_agent/smoke_magnus.py --execute
```

This uses a new workspace by default. To resume a recorded job instead of creating
an independent run, supply the workspace printed by that run:

```bash
.venv/bin/python tests/python_agent/smoke_magnus.py --execute \
  --workspace output/python-agent/magnus-smoke-TIMESTAMP
```

The harness writes `report.json`, `events.jsonl`, `logs.json`, the reviewed inputs
and evidence, and downloaded results. `--wait-seconds` controls the bounded polling
period (default 600 seconds); expiry stops the client wait without killing or
resubmitting the backend job. Reported stages distinguish preparation, current-policy
validation, submission, reconnection, simulation, retrieval, and output checks.
Checking output readability is not an optics analysis or a full scientific
validation of the simulated beam.

Phase 3's deterministic backend path is verified. A Qwen-driven ADK execution
test was attempted but failed to advance to backend operations (see below).
Native parser-only validation remains unavailable; it was explicitly
skipped rather than implemented as part of this phase. Advanced analysis and
autonomous repair loops remain outside the Phase 3 scope.

## Qwen-driven execution smoke test

This separate test uses the existing file in
`tests/lattice-generator/fodo-no-spacecharge/input/`, after checking that it is
byte-identical to the pinned reviewed fixture. It does not ask Qwen to generate
an input. The operator report is prepared before Qwen starts; Qwen must discover
and consult the execution skills and actually invoke the backend tools.

```bash
ACCELERATOR_AGENT_MODEL=ollama_chat/qwen3.5:2b \
ACCELERATOR_AGENT_TIMEOUT=1200 \
.venv/bin/python tests/python_agent/smoke_qwen_execution.py --execute
```

The default response budget for this execution-only test is 512 tokens, with
explicit environment overrides respected. The model has up to 16 requests.
A final text claim alone cannot pass: the harness checks recorded skill loads,
backend inspection, one unique submitted job, status/log queries, successful
retrieval, unchanged input bytes, and readable SDDS/HDF5 outputs. No hidden helper
submits the job or retrieves results on the model's behalf.

Artifacts are saved in a new `output/python-agent/qwen-execution-TIMESTAMP/`
directory: `trace.jsonl`, `task.md`, `response.txt` when available, and
`qwen-report.json` (including failures and token usage). The preparation-only
`report.json` is separate. To resume after a failure, use `--workspace` with that
same directory; prior job IDs are supplied to Qwen and the adapter still prevents
duplicate submissions. A backend job can outlive a failed model task.

The first Qwen 2B execution attempt on 2026-10-21 failed after about 490 seconds
and 14 model responses. It loaded both execution skills, read the review and
specification, then repeatedly alternated between `read_file(validation.json)`
and `list_files(input)`. It ended with text announcing another read, without
calling backend inspection, submission, status, logs, or retrieval. No job was
submitted and the input was unchanged. The harness correctly rejected the run;
this was not a backend error or model timeout. Reported prompt usage grew from
2,116 to 8,015 tokens. The guard at that time did not detect alternating patterns.
Artifacts: `output/python-agent/qwen-execution-20261021T175348993433Z/`.

The follow-up fix detects exact two-call and three-call cycles repeated three
times, stopping before the last call executes. Status/log polling remains exempt.
This bounds wasted inspection; it does not force the model to advance. Longer or
changing cycles still rely on the overall request limit.

When Magnus is enabled, the system instructions now include an execution handoff
from the operator configuration already snapshotted by the adapter: submission
enablement, report status, input directory/file, and digest. The model is told to
consult the execution skills once, inspect backend compatibility, submit the exact
approved input, then use its job ID for status/logs/retrieval. Reading the report
again is unnecessary for authorization. All existing report/digest gates remain
enforced by the submission tool. Disabled submission or a missing PASS report
must be reported instead of submitting.

Follow-up verification: 30 focused offline tests passed across task control,
Magnus, and progress output, including cycle detection, polling exemptions,
handoff configuration and the actual ADK request/tool chain. Qwen was not rerun.
Retry manually using the command above; reliable model-driven execution is still
unverified.

Phase 3 now has 15 focused offline regression/unit tests. The added ADK integration
test uses a scripted offline model and fake backend to verify that the actual model
request exposes the Magnus tools and that their submission/status/log/retrieval
chain executes. The focused suite passed. This confirms the ADK wiring, but does
not establish that Qwen will reliably choose the right next operation. Reliable
model-driven execution remains the outstanding Phase 3 verification item.
