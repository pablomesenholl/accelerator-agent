"""FODO parser checks. Generated files are confined to temporary directories."""

import argparse
import contextlib
import io
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
INPUTS = Path(__file__).parent / "inputs"
sys.path.insert(0, str(REPO / "scripts"))
import run_opalx_validation as validation
import yaml

OPTIONS = SimpleNamespace(docker=False, magnus=False, stage_runner=False, image="opalx:serial")
CASES = {
    "fodo.in": ("PASS", validation.SUCCESS_MESSAGE),
    "invalid-attribute.in": ("FAIL", "TYPO"),
    "missing-endtrack.in": ("FAIL", "ENDTRACK"),
    "missing-include.in": ("FAIL", "missing-fodo.in"),
    "invalid-include.in": ("FAIL", "invalid-attribute.in"),
    "runtime-references.in": ("PASS", validation.SUCCESS_MESSAGE),
}


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None
            for p in root.rglob("*")}


def blueprint_job(code, secret, input_file):
    jobs = []
    scope = {"Annotated": Annotated, "FileSecret": str,
             "JobType": SimpleNamespace(A2="A2"), "submit_job": lambda **job: jobs.append(job)}
    exec(compile(code, "opalx-validation", "exec"), scope)
    scope["blueprint"](secret, input_file)
    return jobs[0]


class RunnerTests(unittest.TestCase):
    def test_success_requires_zero_exit_and_standalone_marker(self):
        marker = validation.SUCCESS_MESSAGE
        error = '*** Parse error detected by function "OpalParser::parseAction()"'
        cases = [(0, marker, "PASS"), (0, "", "INCONCLUSIVE"),
                 (1, marker, "INCONCLUSIVE"), (156, error, "FAIL"),
                 (0, marker + "\n" + error, "INCONCLUSIVE"),
                 (1, 'Unknown argument "--parse-only"', "INCONCLUSIVE"),
                 (-9, error, "INCONCLUSIVE")]
        for code, output, expected in cases:
            with self.subTest(code=code, output=output):
                self.assertEqual(validation._status(code, output), expected)

    def test_command_provenance_and_unchanged_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(INPUTS, root / "input")
            root = root / "input"
            before = snapshot(root)
            output = ("OPAL-X> OPALX :: Version 1.0.0\n"
                      "OPAL-X> git rev. cb3b8ceea29645c9533233c3f6f14c3410c2b263\n"
                      + validation.SUCCESS_MESSAGE + "\n")
            with patch.object(validation.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output)) as run, contextlib.redirect_stdout(io.StringIO()):
                result = validation._run_opalx(root, root / "fodo.in")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["command"], ["opalx", "--parse-only", "--input", "fodo.in", "--info", "2"])
            self.assertEqual(run.call_count, 1)
            self.assertEqual(result["opalx_version"], "1.0.0")
            self.assertEqual(len(result["opalx_revision"]), 40)
            self.assertEqual(result["diagnostics"], output)
            self.assertEqual(snapshot(root), before)
            original = result["input_digest"]
            (root / "invalid-include.in").write_text('CALL, FILE="fodo.in";')
            self.assertNotEqual(original, validation._input_digest(root, "fodo.in"))
            self.assertEqual(json.loads(json.dumps(result)), result)

    def test_timeout_is_inconclusive_even_with_partial_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(INPUTS / "fodo.in", root)
            error = subprocess.TimeoutExpired(["opalx"], 60,
                                               output=validation.SUCCESS_MESSAGE.encode())
            with patch.object(validation.subprocess, "run", side_effect=error), contextlib.redirect_stdout(io.StringIO()):
                result = validation._run_opalx(root, root / "fodo.in")
            self.assertEqual(result["status"], "INCONCLUSIVE")
            self.assertFalse(result["success"])
            self.assertIsNone(result["returncode"])

    def test_main_handles_single_file_and_bundle_and_cleans_staging(self):
        for directory in (False, True):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result_file = root / "result.json"
                def download(secret, staging):
                    shutil.copytree(INPUTS, staging)
                    return staging if directory else staging / "fodo.in"
                with contextlib.chdir(root), patch.dict("os.environ", {"MAGNUS_RESULT": str(result_file)}), patch.object(sys, "argv", ["runner", "--input_secret", "test", "--input_file", "fodo.in"]), patch.object(validation, "_download_simulation", side_effect=download), patch.object(validation.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, validation.SUCCESS_MESSAGE)), contextlib.redirect_stdout(io.StringIO()):
                    validation.main()
                self.assertEqual(json.loads(result_file.read_text())["status"], "PASS")
                self.assertEqual(list(root.iterdir()), [result_file])

    def test_blueprint_works_after_magnus_strips_imports(self):
        from magnus.client import strip_imports
        code = yaml.safe_load((REPO / "src/blueprints/opalx-validation.yaml").read_text())["code"]
        secret, name = "secret's value; literal", "input's name.in"
        job = blueprint_job(strip_imports(code), secret, name)
        self.assertEqual(shlex.split(job["entry_command"]),
                         ["python3", "scripts/run_opalx_validation.py", "--input_secret", secret,
                          "--input_file", name])
        self.assertEqual(job["container_image"], "docker://opalx:serial")


class DockerTests(unittest.TestCase):
    def test_fodo_variants_without_output_or_input_changes(self):
        if not OPTIONS.docker:
            self.skipTest("Use --docker to test the OPALX image")
        for name, (expected, diagnostic) in CASES.items():
            with self.subTest(input=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copytree(INPUTS, root / "input")
                work = root / "input"
                before = snapshot(work)
                process = subprocess.run(
                    ["docker", "run", "--rm", "--network", "none", "--mount",
                     f"type=bind,source={work},target=/work", "--workdir", "/work",
                     "--entrypoint", "opalx", OPTIONS.image,
                     "--parse-only", "--input", name, "--info", "2"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
                self.assertEqual(validation._status(process.returncode, process.stdout), expected,
                                 process.stdout)
                self.assertIn(diagnostic, process.stdout)
                self.assertEqual(snapshot(work), before, "Parser changed inputs or wrote outputs")
                print(f"Docker {name}: {expected}", flush=True)


class MagnusTests(unittest.TestCase):
    def test_registered_blueprint_fodo_variants(self):
        if not OPTIONS.magnus:
            self.skipTest("Use --magnus to test the registered blueprint")
        import magnus
        from magnus.client import strip_imports
        client = magnus.default_client
        local = yaml.safe_load((REPO / "src/blueprints/opalx-validation.yaml").read_text())
        registered = client.get_blueprint("opalx-validation")
        self.assertEqual(registered["code"].strip(), strip_imports(local["code"]).strip())
        schema = {p["key"]: p["type"] for p in client.get_blueprint_schema("opalx-validation")}
        self.assertEqual(schema, {"simulation": "file_secret", "input_file": "text"})
        before = snapshot(INPUTS)
        with tempfile.TemporaryDirectory() as tmp:
            source_secret = None
            if OPTIONS.stage_runner:
                source = Path(tmp) / "runner-source"
                source.mkdir()
                for name in ("run_opalx_validation.py", "run_opalx_simulation.py"):
                    shutil.copy(REPO / "scripts" / name, source)
                source_secret = client.custody_file(str(source), expire_minutes=15,
                                                    max_downloads=len(CASES))
            secret = client.custody_file(str(INPUTS), expire_minutes=15, max_downloads=len(CASES))
            for name, (expected, diagnostic) in CASES.items():
                with self.subTest(input=name):
                    if source_secret:
                        # Test unpublished code without committing or changing backend caches.
                        bootstrap = (
                            "import magnus, shutil\nfrom pathlib import Path\n"
                            f"source=Path(magnus.download_file({source_secret!r}))\n"
                            "for name in ('run_opalx_validation.py','run_opalx_simulation.py'):\n"
                            "    shutil.copyfile(source/name, Path('scripts')/name)\n"
                            "shutil.rmtree(source)\n")
                        job = blueprint_job(registered["code"], secret, name)
                        job["entry_command"] = "python3 -B -c " + shlex.quote(bootstrap) + " && " + job["entry_command"]
                        job_id = client.submit_job(**job)
                    else:
                        job_id = client.launch_blueprint("opalx-validation",
                            args={"simulation": secret, "input_file": name}, save_preference=False)
                    print(f"Magnus {name}: submitted {job_id}", flush=True)
                    raw = client._poll_job_completion(job_id, timeout=180, execute_action_flag=False)
                    result = json.loads(raw) if isinstance(raw, str) else raw
                    self.assertEqual(result["status"], expected, result)
                    self.assertEqual(result["success"], expected == "PASS")
                    self.assertEqual(result["mode"], "parse-only")
                    self.assertEqual(result["input_file"], name)
                    self.assertEqual(result["input_digest"], validation._input_digest(INPUTS, name))
                    self.assertIn(diagnostic, result["diagnostics"])
                    self.assertIsNotNone(result["opalx_revision"])
                    self.assertIsNone(client.get_job_action(job_id), "Validation must not request output downloads")
                    print(f"Magnus {name}: {expected}, OPALX {result['opalx_revision']}", flush=True)
        self.assertEqual(snapshot(INPUTS), before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", action="store_true")
    parser.add_argument("--magnus", action="store_true")
    parser.add_argument("--stage-runner", action="store_true",
                        help="Stage uncommitted runners into isolated Magnus test jobs.")
    parser.add_argument("--image", default="opalx:serial")
    OPTIONS, remaining = parser.parse_known_args()
    if OPTIONS.stage_runner and not OPTIONS.magnus:
        parser.error("--stage-runner requires --magnus")
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
