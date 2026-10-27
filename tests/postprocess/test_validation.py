"""Validation tests use analytic populations and optional local FODO outputs."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from postprocess import (
    analyze_snapshot, compare_diagnostics, validate_analysis, validate_run_files,
    validate_snapshot, validate_statistics, validate_timing,
)
from postprocess.models import (
    AnalysisResult, FieldMetadata, ParticleSnapshot, RunFiles,
    SourceMetadata, StatisticsTable, TimingData, ValidationIssue, ValidationReport,
)
from postprocess.readers import discover_run, list_snapshots, read_snapshot, read_stat, read_timing


def particle_data():
    u = np.array([-1., -1., 1., 1.])
    v = np.array([-1., 1., -1., 1.])
    columns = {"x": 2*u, "px": 3*u + 4*v, "y": 3*v, "py": u - 2*v,
               "z": u + v, "pz": np.full(4, 2.), "q": np.full(4, -1e-12),
               "id": np.arange(4, dtype=np.int64), "sp": np.ones(4, dtype=int)}
    fields = {name: FieldMetadata("p/(mc)" if name.startswith("p") else "m")
              for name in ("x", "px", "y", "py", "z", "pz")}
    return ParticleSnapshot(3, "Step#3", columns, SourceMetadata(Path("beam.h5")), fields, s=1., time=2e-9)


def statistics(data, result):
    columns = {"t": np.array([2.]), "s": np.array([100.]), "numParticles": np.array([4])}
    fields = {"t": FieldMetadata("ns"), "s": FieldMetadata("cm"), "numParticles": FieldMetadata("1")}
    for plane in ("x", "y"):
        for prefix, calculated in (("mean", "centroid"), ("rms", "rms"), ("emit", "emit_n")):
            key = prefix + "_" + plane
            name = calculated + plane if calculated == "emit_n" else calculated + "_" + plane
            columns[key] = np.array([result.quantities[name].value])
            fields[key] = FieldMetadata("m")
    return StatisticsTable(columns, SourceMetadata(Path("beam.stat")), fields)


def codes(report):
    return {issue.code for issue in report.issues}


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = particle_data()
        self.result = analyze_snapshot(self.data, longitudinal_axis="z")

    def test_valid_population_and_calculations_do_not_mutate_inputs(self):
        before = deepcopy(self.data)
        self.assertTrue(validate_snapshot(self.data, longitudinal_axis="z").is_valid)
        self.assertTrue(validate_analysis(self.result, longitudinal_axis="z").is_valid)
        for name, values in before.columns.items():
            np.testing.assert_array_equal(self.data.columns[name], values)
        self.assertEqual(self.result.issues, [])
        self.assertTrue(validate_analysis(analyze_snapshot(self.data)).is_valid)

    def test_missing_empty_malformed_and_nonfinite_datasets(self):
        del self.data.columns["z"]
        self.data.columns["x"] = np.array([np.nan]*4)
        self.data.columns["py"] = np.ones((4, 1))
        self.data.columns["pz"] = np.ones(3)
        report = validate_snapshot(self.data)
        self.assertFalse(report.is_valid)
        self.assertTrue({"missing_field", "nonfinite_data", "invalid_dimensions", "inconsistent_dimensions"} <= codes(report))
        self.assertTrue(all(issue.source == self.data.source.path and issue.step == 3 for issue in report.issues))
        self.data.columns = {"x": np.array([])}
        self.assertIn("empty_data", codes(validate_snapshot(self.data)))

    def test_physical_checks_respect_signs_and_forward_axis(self):
        self.data.columns["pz"] *= -1
        self.assertTrue(validate_snapshot(self.data).is_valid)  # Not inherently invalid in arbitrary axes.
        self.assertIn("invalid_longitudinal_momentum", codes(validate_snapshot(self.data, longitudinal_axis="z")))
        self.data.columns["m"] = np.full(4, -1.)
        self.data.columns["id"][1] = self.data.columns["id"][0]
        self.assertTrue({"invalid_mass", "duplicate_ids"} <= codes(validate_snapshot(self.data)))
        self.data.columns["id"] = np.arange(4, dtype=float)
        self.assertIn("invalid_ids", codes(validate_snapshot(self.data)))

    def test_unknown_units_weighting_and_species_are_visible_warnings(self):
        self.data.fields["x"].unit = None
        self.data.fields["pz"].unit = "1"
        self.data.columns["q"] *= np.arange(1, 5)
        self.data.columns["sp"][0] = 2
        report = validate_snapshot(self.data)
        self.assertTrue(report.is_valid)
        self.assertTrue({"unknown_unit", "unknown_convention", "unequal_charges", "mixed_species"} <= codes(report))
        self.assertTrue(all(issue.severity == "warning" for issue in report.issues))

    def test_statistics_ranges_counts_and_restart_times(self):
        table = statistics(self.data, self.result)
        self.assertTrue(validate_statistics(table).is_valid)
        for name, bad, code in (("numParticles", -1., "invalid_count"),
                                ("numParticles", 1.5, "invalid_count"),
                                ("rms_x", -1., "negative_observable"),
                                ("energy", -1., "negative_observable"),
                                ("xpx", 2., "invalid_correlation")):
            changed = deepcopy(table)
            changed.columns[name] = np.array([bad])
            with self.subTest(name=name, bad=bad):
                self.assertIn(code, codes(validate_statistics(changed)))
        table.columns = {name: np.repeat(value, 2) for name, value in table.columns.items()}
        table.columns["s"] = np.array([100., 90.])  # Path need not increase.
        report = validate_statistics(table)
        self.assertTrue(report.is_valid)
        self.assertIn("nonmonotonic_time", codes(report))

    def test_missing_outputs_and_optional_timing(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            files = RunFiles(root)
            self.assertFalse(validate_run_files(files).is_valid)
            for name in ("beam.stat", "beam.h5"):
                (root / name).write_text("not parsed by this check")
            files.statistics = [Path("beam.stat")]
            files.snapshots = [Path("beam.h5")]
            report = validate_run_files(files)
            self.assertTrue(report.is_valid)
            self.assertIn("Optional timings output is absent", report.skipped)
            (root / "timing.dat").touch()
            files.timings = [Path("timing.dat")]
            self.assertTrue(validate_run_files(files).is_valid)
            self.assertFalse(validate_run_files(files, required=("timings",)).is_valid)
            (root / "empty.h5").touch()
            files.snapshots.append(Path("empty.h5"))
            self.assertTrue({"multiple_candidates", "empty_output"} <= codes(validate_run_files(files)))
            files.snapshots = [Path("../escape.h5")]
            self.assertIn("invalid_output_path", codes(validate_run_files(files)))
            files.snapshots = [Path("gone.h5")]
            self.assertIn("missing_output", codes(validate_run_files(files)))

    def test_timing_empty_warns_without_numeric_interpretation(self):
        report = validate_timing(TimingData(self.data.source, ""))
        self.assertTrue(report.is_valid)
        self.assertIn("empty_timing", codes(report))
        self.assertTrue(report.skipped)

    def test_result_missing_invalid_and_failed_observables(self):
        for variant, code in (("missing", "missing_quantity"), ("nan", "invalid_quantity"),
                              ("negative", "negative_observable"), ("count", "invalid_count")):
            result = deepcopy(self.result)
            if variant == "missing":
                del result.quantities["rms_x"]
            elif variant == "nan":
                result.quantities["rms_x"].value = np.inf
            elif variant == "negative":
                result.quantities["rms_x"].value = -1
            else:
                result.quantities["num_particles"].value = 1.5
            with self.subTest(variant=variant):
                self.assertIn(code, codes(validate_analysis(result, longitudinal_axis="z")))
        failed = AnalysisResult(self.data.source, "failed", issues=[ValidationIssue("calculation_failed", "failed", "error")])
        self.assertFalse(validate_analysis(failed).is_valid)
        self.assertIn("calculation_failed", codes(validate_analysis(failed)))
        self.result.status = "partial"
        self.assertIn("inconsistent_status", codes(validate_analysis(self.result)))

    def test_matrix_symmetry_psd_scaling_and_mutated_shapes(self):
        for values, code in (([[4., 6.], [5., 25.]], "asymmetric_covariance"),
                             ([[4., 12.], [12., 25.]], "nonpositive_covariance"),
                             ([[-1., 0.], [0., 1.]], "negative_variance"),
                             ([[0., 1.], [1., 1.]], "nonpositive_covariance"),
                             ([[np.nan, 0.], [0., 1.]], "nonfinite_covariance"),
                             ([[1.]], "invalid_covariance")):
            changed = deepcopy(self.result)
            changed.covariances["x_normalized"].values = np.array(values)
            with self.subTest(code=code):
                self.assertIn(code, codes(validate_analysis(changed)))
        # Tiny dimensional entries must not hide a non-PSD correlation matrix.
        changed = deepcopy(self.result)
        changed.covariances["x_normalized"].values = np.array([[1e-30, 2e-20], [2e-20, 1e-10]])
        self.assertIn("nonpositive_covariance", codes(validate_analysis(changed)))
        self.assertTrue(validate_analysis(self.result).is_valid)  # Constant pz gives a valid singular full matrix.

    def test_rms_emittance_twiss_and_units_consistency(self):
        for name, bad, code in (("rms_x", 3., "inconsistent_rms"),
                                ("emit_nx", 20., "inconsistent_emittance"),
                                ("alpha_x", 10., "inconsistent_twiss"),
                                ("emit_x", 0., "undefined_twiss")):
            changed = deepcopy(self.result)
            changed.quantities[name].value = bad
            with self.subTest(name=name):
                self.assertIn(code, codes(validate_analysis(changed, longitudinal_axis="z")))
        self.result.quantities["beta_x"].unit = "mm"
        self.assertIn("inconsistent_units", codes(validate_analysis(self.result)))

    def test_nearly_singular_valid_result_and_zero_emittance(self):
        u = np.array([-1., -1., 1., 1.])
        v = np.array([-1., 1., -1., 1.])
        self.data.columns["x"], self.data.columns["px"] = u, u + 1e-10*v
        near = analyze_snapshot(self.data, longitudinal_axis="z")
        self.assertTrue(validate_analysis(near, longitudinal_axis="z").is_valid)
        self.data.columns["px"] = u
        degenerate = analyze_snapshot(self.data, longitudinal_axis="z")
        self.assertIn("undefined_twiss", codes(validate_analysis(degenerate, longitudinal_axis="z")))

    def test_projected_covariance_matches_full_matrix_and_metadata(self):
        changed = deepcopy(self.result)
        changed.covariances["x_normalized"].values[0, 1] = 0
        changed.covariances["x_normalized"].values[1, 0] = 0
        self.assertIn("inconsistent_covariance", codes(validate_analysis(changed)))
        changed = deepcopy(self.result)
        changed.covariances["phase_space"].coordinates = tuple(reversed(changed.covariances["phase_space"].coordinates))
        self.assertIn("inconsistent_axes", codes(validate_analysis(changed)))
        changed = deepcopy(self.result)
        del changed.covariances["phase_space"]
        self.assertIn("missing_covariance", codes(validate_analysis(changed)))

    def test_comparison_requires_confirmation_and_same_provenance(self):
        report = compare_diagnostics(self.data, self.result)
        self.assertIn("comparison_not_performed", codes(report))
        self.assertTrue(report.skipped)
        self.result.step = 99
        self.assertIn("provenance_mismatch", codes(compare_diagnostics(self.data, self.result, frame_confirmed=True)))

    def test_comparison_unit_conversion_and_reported_mismatch(self):
        table = statistics(self.data, self.result)
        attrs = self.data.source.attributes
        attrs["RMSX"] = np.array([2., 3., np.sqrt(2)]) * 100
        attrs["file_attributes"] = {"RMSXUnit": b"cm"}
        report = compare_diagnostics(self.data, self.result, table, frame_confirmed=True)
        self.assertTrue(report.is_valid, report.issues)
        self.assertTrue(any("row 0" in check for check in report.checks))
        table.columns["mean_x"][0] = 1
        report = compare_diagnostics(self.data, self.result, table, frame_confirmed=True)
        self.assertIn("reported_mismatch", codes(report))
        self.assertTrue(any(issue.field_name == "mean_x[0]" for issue in report.issues))

    def test_comparison_never_uses_unmatched_or_ambiguous_rows(self):
        table = statistics(self.data, self.result)
        table.columns["t"][0] = 3
        self.assertIn("unmatched_coordinates", codes(compare_diagnostics(self.data, self.result, table, frame_confirmed=True)))
        table.columns["t"][0] = 2
        table.columns = {name: np.repeat(values, 2) for name, values in table.columns.items()}
        report = compare_diagnostics(self.data, self.result, table, frame_confirmed=True)
        self.assertIn("ambiguous_match", codes(report))
        self.assertFalse(any("against centroid_x" in check for check in report.checks))

    def test_comparison_skips_unknown_units_and_rejects_path_mismatch(self):
        table = statistics(self.data, self.result)
        table.columns["s"][0] = 101
        report = compare_diagnostics(self.data, self.result, table, frame_confirmed=True)
        self.assertIn("coordinate_mismatch", codes(report))
        table.columns["s"][0] = 100
        table.fields["mean_x"].unit = None
        self.data.source.attributes.update({"RMSX": np.array([2., 3., 1.])})
        report = compare_diagnostics(self.data, self.result, table, frame_confirmed=True)
        self.assertIn("unknown_unit", codes(report))
        self.assertTrue(any("mean_x" in check for check in report.skipped))

    def test_malformed_reported_values_and_missing_clock_are_not_compared(self):
        table = statistics(self.data, self.result)
        self.data.source.attributes["RMSX"] = np.array([np.nan, 2., 3.])
        table.columns["rms_x"] = np.array([np.inf])
        report = compare_diagnostics(self.data, self.result, table, frame_confirmed=True)
        self.assertTrue({"invalid_reported_metadata", "invalid_reported_data"} <= codes(report))
        self.data.time = None
        report = compare_diagnostics(self.data, self.result, table, frame_confirmed=True)
        self.assertIn("unmatched_coordinates", codes(report))
        self.assertFalse(any("against centroid_x" in check for check in report.checks))

    def test_report_defaults_and_invalid_options(self):
        first, second = ValidationReport(), ValidationReport()
        first.skipped.append("one")
        self.assertEqual(second.skipped, [])
        for rtol in (-1., np.nan, np.inf):
            with self.assertRaises(ValueError):
                validate_analysis(self.result, rtol=rtol)
        with self.assertRaises(ValueError):
            validate_snapshot(self.data, longitudinal_axis="x")


class FodoValidationTests(unittest.TestCase):
    def test_local_fodo_passes_calculations_and_reports_bad_centroid_metadata(self):
        root = Path(__file__).resolve().parents[2] / "output/opalx-simulator/fodo-no-spacecharge"
        h5, stat = root / "FODO-no-spacecharge.h5", root / "FODO-no-spacecharge.stat"
        if not h5.exists() or not stat.exists():
            self.skipTest("Local FODO outputs unavailable")
        self.assertTrue(validate_run_files(discover_run(root)).is_valid)
        table = read_stat(stat)
        self.assertTrue(validate_statistics(table).is_valid)
        self.assertTrue(validate_timing(read_timing(root / "timing.dat")).is_valid)
        for step in list_snapshots(h5):
            with self.subTest(step=step):
                data = read_snapshot(h5, step)
                result = analyze_snapshot(data, longitudinal_axis="z")
                self.assertTrue(validate_snapshot(data, longitudinal_axis="z").is_valid)
                report = validate_analysis(result, longitudinal_axis="z")
                self.assertTrue(report.is_valid, report.issues)
                original = data.source.attributes["centroid"].copy()
                compared = compare_diagnostics(data, result, table, frame_confirmed=True)
                errors = [issue for issue in compared.issues if issue.severity == "error"]
                self.assertEqual(len(errors), 3, errors)
                self.assertTrue(all(issue.code == "reported_mismatch" and issue.field_name.startswith("centroid[")
                                    for issue in errors))
                self.assertTrue(any("mean_x" in check for check in compared.checks))
                np.testing.assert_array_equal(data.source.attributes["centroid"], original)


if __name__ == "__main__":
    unittest.main()
