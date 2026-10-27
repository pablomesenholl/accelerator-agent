"""Acceptance harness checks with independent clean/corrupt synthetic outputs."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("fodo_acceptance", ROOT / "tests/postprocess/check_fodo.py")
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


def clean_outputs(root):
    """Write small independent SDDS/HDF5 populations, not simulator outputs."""
    root.mkdir()
    names = ["t", "s", "numParticles", "mean_x", "mean_y", "mean_s",
             "rms_x", "rms_y", "rms_s", "emit_x", "emit_y", "energy"]
    units = ["ns", "m", "1", "m", "m", "m", "m", "m", "m", "m", "m", "MeV"]
    header = ["SDDS1"]
    for name, unit in zip(names, units):
        header.append(f'&column name={name}, type={"long" if name == "numParticles" else "double"}, units={unit} &end')
    header.append("&data mode=ascii, no_row_counts=1 &end")
    u, v = np.array([-1., -1., 1., 1.]), np.array([-1., 1., -1., 1.])
    with h5py.File(root / "beam.h5", "w") as handle:
        handle.attrs["OPAL_version"] = np.bytes_("Synthetic acceptance population")
        for name in ("x", "y", "z", "SPOS", "centroid", "RMSX", "#varepsilon"):
            handle.attrs[name + "Unit"] = "m"
        for name in ("px", "py", "pz", "RMSP"):
            handle.attrs[name + "Unit"] = "#beta#gamma"
        handle.attrs["TIMEUnit"] = "s"
        for step in (0, 1):
            px, py = 2e-4*v + 1e-6, 3e-4*u + 2e-6
            columns = {"x": 1e-3*u + 1e-5 + step*.25*px/2,
                       "y": 2e-3*v - 2e-5 + step*.25*py/2,
                       "z": 3e-3*(u+v) + 3e-5,
                       "px": px, "py": py, "pz": np.full(4, 2.),
                       "q": np.full(4, 1e-12), "id": np.arange(4, dtype=np.int64)}
            group = handle.create_group(f"Step#{step}")
            for name, values in columns.items():
                group.create_dataset(name, data=values)
            means = [float(columns[c].mean()) for c in ("x", "y", "z")]
            rms = [float(columns[c].std()) for c in ("x", "y", "z")]
            group.attrs["centroid"] = means
            group.attrs["RMSX"] = rms
            group.attrs["RMSP"] = [columns[c].std() for c in ("px", "py", "pz")]
            group.attrs["#varepsilon"] = [2e-7, 6e-7, 0.]
            group.attrs["SPOS"] = [(step+1)*.25]
            group.attrs["TIME"] = [(step+1)*1e-9]
            header.append(" ".join(str(value) for value in
                                   [step+1, (step+1)*.25, 4, *means, *rms, 2e-7, 6e-7, 1.]))
    (root / "beam.stat").write_text("\n".join(header) + "\n")


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.run = self.root / "input"
        clean_outputs(self.run)

    def check(self, output="checked", **kwargs):
        return acceptance.check_fodo(self.run, self.root / output,
                                     confirm_z_longitudinal=True, plots=False, **kwargs)

    def test_clean_data_end_to_end_and_artifact_schema(self):
        report = self.check()
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["source_unchanged"])
        self.assertFalse(report["simulation_executed"])
        self.assertEqual(report["known_issues"], [])
        self.assertEqual(report["snapshot_steps"], [0, 1])
        self.assertEqual(report["stages"]["exports"], "passed")
        self.assertEqual(report["stages"]["plots"], "skipped_by_request")
        output = self.root / "checked"
        persisted = json.loads((output / "report.json").read_text())
        self.assertEqual(persisted["status"], report["status"])
        self.assertIn("series.metadata.json", persisted["artifacts"])
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(set(manifest["files"]), {"beam.stat", "beam.h5"})
        self.assertTrue(persisted["file_validation"]["skipped"])  # Optional timing absent.

    def test_unexpected_centroid_mismatch_fails_without_exception_profile(self):
        with h5py.File(self.run / "beam.h5", "r+") as handle:
            # Even a matching legacy revision and signature cannot waive the
            # bug without checksum verification of the exact reference files.
            handle.attrs["OPAL_version"] = "OPALX 0.9 # git rev. 33d444649e3379b08c4610290d948fa2a4f39c93"
            group = handle["Step#0"]
            group.attrs["centroid"] = [group[name][...].sum() for name in ("x", "px", "y")]
        report = self.check()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["stages"]["comparisons"], "failed")
        self.assertEqual(report["known_issues"], [])
        self.assertTrue(report["source_unchanged"])

    def test_headless_plots_are_real_png_artifacts(self):
        report = acceptance.check_fodo(self.run, self.root / "plots",
                                        confirm_z_longitudinal=True, plots=True)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["stages"]["plots"], "passed")
        for name in ("envelope.png", "normalized_emittance.png"):
            raw = (self.root / "plots" / name).read_bytes()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(len(raw), 1000)

    def test_unknown_clock_cannot_turn_skipped_comparisons_into_a_pass(self):
        path = self.run / "beam.stat"
        path.write_text(path.read_text().replace("units=ns", "units=1"))
        report = self.check()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["stages"]["comparisons"], "failed")
        self.assertTrue(report["snapshots"][0]["comparison"]["skipped"])

    def test_missing_inputs_and_bad_statistics_fail_before_analysis(self):
        (self.run / "beam.stat").unlink()
        report = self.check()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["stages"]["discovery"], "failed")
        self.assertEqual(report["stages"]["analysis"], "not_run")
        (self.run / "beam.stat").write_text("not SDDS")
        report = self.check(output="bad_stat")
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["stages"]["reading"], "failed")

    def test_profile_hash_mismatch_is_not_waived(self):
        profile = self.root / "reference.json"
        profile.write_text(json.dumps({"files": {"beam.stat": "wrong", "beam.h5": "wrong"},
                                       "known_centroid_bug_revision": "Synthetic"}))
        report = self.check(reference=profile)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["reference_verified"])
        self.assertIn("hash mismatch", report["errors"][0]["message"])

    def test_existing_output_and_output_inside_input_are_refused(self):
        self.check()
        with self.assertRaises(FileExistsError):
            self.check()
        with self.assertRaisesRegex(ValueError, "outside"):
            acceptance.check_fodo(self.run, self.run / "analysis", confirm_z_longitudinal=True, plots=False)
        with self.assertRaisesRegex(ValueError, "Confirm"):
            acceptance.check_fodo(self.run, self.root / "unconfirmed", plots=False)
        self.assertFalse((self.root / "unconfirmed").exists())

    def test_cli_exit_codes(self):
        args = ["--input", str(self.run), "--output", str(self.root / "cli"),
                "--confirm-z-longitudinal", "--no-plots"]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(acceptance.main(args), 0)
        with h5py.File(self.run / "beam.h5", "r+") as handle:
            handle["Step#0"].attrs["RMSX"] = [999., 999., 999.]
        args[3] = str(self.root / "cli_fail")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(acceptance.main(args), 1)


class LocalReferenceAcceptanceTests(unittest.TestCase):
    def test_checksum_pinned_fodo_known_issue_is_explicit(self):
        run = ROOT / "output/opalx-simulator/fodo-no-spacecharge"
        if not (run / "FODO-no-spacecharge.h5").exists() or not (run / "FODO-no-spacecharge.stat").exists():
            self.skipTest("Local FODO outputs unavailable")
        with TemporaryDirectory() as directory:
            report = acceptance.check_fodo(run, Path(directory) / "acceptance",
                confirm_z_longitudinal=True,
                reference=ROOT / "tests/postprocess/fixtures/fodo_reference.json", plots=False)
            self.assertEqual(report["status"], "passed_with_known_issue", report["errors"])
            self.assertTrue(report["reference_verified"])
            self.assertTrue(report["source_unchanged"])
            self.assertEqual(len(report["known_issues"]), 33)
            self.assertEqual(len(report["snapshots"]), 11)
            self.assertTrue(all(not item["comparison"]["is_valid"] for item in report["snapshots"]))


if __name__ == "__main__":
    unittest.main()
