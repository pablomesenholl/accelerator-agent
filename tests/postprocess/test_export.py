"""Agent-facing numerical adapters and portable export contracts."""

from copy import deepcopy
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from postprocess import (
    analyze_snapshot, list_snapshots, read_snapshot, read_stat, results_to_dataframe,
    to_dataframe, to_summary, validate_analysis, validate_statistics,
    write_json, write_statistics_csv,
)
from postprocess.models import (
    AnalysisResult, FieldMetadata, ParticleSnapshot, Quantity, RunFiles,
    SourceMetadata, StatisticsTable, TimingData, ValidationIssue, ValidationReport,
)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = SourceMetadata(Path("beam.stat"), "OPALX test", {
            "species": np.bytes_("PROTON"), "processors": np.int32(2),
            "raw": np.array([1., 2.]), "flag": np.bool_(True),
        })
        self.table = StatisticsTable(
            {"s": np.array([0., 1.]), "id": np.array([2**53+1, 2**53+2], dtype=np.int64),
             "rms_x": np.array([1e-3, 2e-3], dtype=np.float32)}, self.source,
            {"s": FieldMetadata("m", "Path length"), "id": FieldMetadata("1"),
             "rms_x": FieldMetadata("m", "Beam size")},
        )
        self.report = ValidationReport(
            issues=[ValidationIssue("example", "Check this field", "warning", self.source.path)],
            checks=["example check"], skipped=["example skip"],
        )

    def result(self, *, step=0, status="success", s=0., time=1e-9):
        return AnalysisResult(self.source, status, step=step,
                              quantities={"rms_x": Quantity(1e-3, "m", "std(x, ddof=0)")},
                              assumptions=["Equal weights"], s=s, time=time)

    def test_compact_summary_metadata_units_and_numpy_values(self):
        summary = to_summary(self.table, validation=self.report)
        self.assertEqual(summary["schema_version"], 1)
        self.assertEqual(summary["kind"], "statistics")
        self.assertEqual(summary["row_count"], 2)
        self.assertEqual(summary["source"]["attributes"]["species"], "PROTON")
        self.assertEqual(summary["source"]["attributes"]["processors"], 2)
        self.assertEqual(summary["source"]["attributes"]["raw"], [1., 2.])
        self.assertEqual(summary["source"]["path"], "beam.stat")
        self.assertEqual(summary["units"]["s"], "m")
        self.assertNotIn("values", summary["columns"]["id"])
        self.assertEqual(summary["columns"]["id"]["first"], 2**53+1)
        self.assertEqual(summary["columns"]["id"]["dtype"], "int64")
        self.assertEqual(summary["validation"]["skipped"], ["example skip"])
        json.dumps(summary, allow_nan=False)

    def test_explicit_array_summary_and_unknown_units(self):
        del self.table.fields["rms_x"]
        summary = to_summary(self.table, include_arrays=True)
        self.assertEqual(summary["columns"]["id"]["values"], [2**53+1, 2**53+2])
        self.assertIsNone(summary["columns"]["rms_x"]["unit"])
        summary["columns"]["s"]["values"][0] = 99
        self.assertEqual(self.table.columns["s"][0], 0)

    def test_nonfinite_numbers_are_explicit_nulls_in_strict_json(self):
        self.table.columns["s"] = np.array([np.nan, np.inf, -np.inf])
        self.table.columns["id"] = np.arange(3, dtype=np.int64)
        self.table.columns["rms_x"] = np.zeros(3)
        summary = to_summary(self.table, include_arrays=True)
        self.assertEqual(summary["columns"]["s"]["values"], [None, None, None])
        self.assertEqual(summary["columns"]["s"]["nonfinite_count"], 3)
        self.assertIsNone(summary["columns"]["s"]["finite_min"])
        self.assertEqual({item["kind"] for item in summary["serialization_issues"]},
                         {"nan", "positive_infinity", "negative_infinity"})
        json.loads(json.dumps(summary, allow_nan=False))
        with self.assertRaisesRegex(ValueError, "Nonfinite number"):
            to_summary(self.table, include_arrays=True, nonfinite="raise")

    def test_invalid_objects_do_not_silently_stringify(self):
        for value in ({"unsupported": object()}, {1: "non-string key"}):
            with self.assertRaises(TypeError):
                to_summary(value)
        with self.assertRaises(ValueError):
            to_summary(self.table, nonfinite="ignore")
        with self.assertRaises(UnicodeDecodeError):
            to_summary({"binary": b"\xff"})

    def test_dataframe_selection_copy_dtypes_and_validation_metadata(self):
        frame = to_dataframe(self.table, columns=["id", "rms_x"], validation=self.report)
        self.assertEqual(list(frame), ["id", "rms_x"])
        self.assertEqual(frame["id"].dtype, np.dtype("int64"))
        self.assertEqual(frame["rms_x"].dtype, np.dtype("float32"))
        self.assertEqual(int(frame["id"].iloc[0]), 2**53+1)
        self.assertEqual(frame.attrs["units"], {"id": "1", "rms_x": "m"})
        self.assertEqual(set(frame.attrs["columns"]), {"id", "rms_x"})
        self.assertTrue(frame.attrs["validation"]["is_valid"])
        frame.loc[0, "id"] = 0
        self.assertEqual(self.table.columns["id"][0], 2**53+1)

    def test_dataframe_nonfinite_metadata_and_particle_coordinates(self):
        self.table.columns["s"][0] = np.nan
        frame = to_dataframe(self.table)
        self.assertTrue(np.isnan(frame["s"].iloc[0]))
        self.assertTrue(frame.attrs["serialization_issues"])
        data = ParticleSnapshot(10, "Step#10", {"x": np.array([1., 2.])},
                                self.source, {"x": FieldMetadata("m")}, s=2., time=3e-9)
        frame = to_dataframe(data)
        self.assertEqual(frame.attrs["step"], 10)
        self.assertEqual(frame.attrs["coordinate_units"], {"s": "m", "time": "s"})
        self.assertEqual(frame.attrs["s"], 2.)

    def test_bad_selections_and_mutated_dimensions_are_rejected(self):
        for selection, error in (("s", TypeError), ([], ValueError),
                                 (["s", "s"], ValueError), (["absent"], KeyError)):
            with self.subTest(selection=selection), self.assertRaises(error):
                to_dataframe(self.table, columns=selection)
        self.table.columns["s"] = np.ones(3)
        with self.assertRaises(ValueError):
            write_statistics_csv(self.table, self.root / "bad.csv")
        self.assertFalse((self.root / "bad.csv").exists())

    def test_result_series_preserves_order_failures_missing_values_and_units(self):
        first = self.result(step=10, s=2.)
        second = self.result(step=2, s=1., status="partial")
        second.quantities = {}
        second.issues.append(ValidationIssue("calculation_failed", "Missing RMS", "error"))
        third = self.result(step=3, s=None, time=None, status="failed")
        third.quantities = {}
        frame = results_to_dataframe([first, second, third], validation_reports=[self.report]*3)
        self.assertEqual(frame["step"].tolist(), [10, 2, 3])
        self.assertEqual(frame["status"].tolist(), ["success", "partial", "failed"])
        self.assertTrue(np.isnan(frame["rms_x"].iloc[1]))
        self.assertTrue(np.isnan(frame["s"].iloc[2]))
        self.assertEqual(frame.attrs["units"]["rms_x"], "m")
        self.assertEqual(frame.attrs["results"][1]["issues"][0]["code"], "calculation_failed")
        self.assertEqual(frame.attrs["results"][0]["assumptions"], ["Equal weights"])
        self.assertEqual(frame.attrs["results"][0]["coordinate_units"]["time"], "s")

    def test_result_series_rejects_mixed_definitions_units_and_array_quantities(self):
        first, second = self.result(), self.result(step=1)
        for attribute, value in (("unit", "mm"), ("definition", "different estimator"),
                                 ("value", np.array([1., 2.]))):
            changed = deepcopy(second)
            setattr(changed.quantities["rms_x"], attribute, value)
            with self.subTest(attribute=attribute), self.assertRaises(ValueError):
                results_to_dataframe([first, changed])
        second.quantities = {"status": Quantity(1., "1", "conflicting name")}
        with self.assertRaises(ValueError):
            results_to_dataframe([second])
        with self.assertRaises(ValueError):
            results_to_dataframe([first], validation_reports=[])

    def test_empty_tables_and_series_are_usable(self):
        empty = StatisticsTable({}, self.source)
        self.assertTrue(to_dataframe(empty).empty)
        self.assertEqual(to_summary(empty)["row_count"], 0)
        self.assertTrue(results_to_dataframe([]).empty)
        result = self.result(step=None)
        frame = results_to_dataframe([self.result(step=2**53+1), result])
        self.assertEqual(int(frame["step"].iloc[0]), 2**53+1)
        self.assertTrue(frame["step"].isna().iloc[1])

    def test_json_file_keeps_failed_status_and_standalone_reports(self):
        result = self.result(status="failed")
        result.quantities = {}
        result.issues = [ValidationIssue("empty_data", "No particles", "error", Path("beam.h5"), 0)]
        path = write_json(result, self.root / "analysis/result.json", validation=self.report)
        stored = json.loads(path.read_text())
        self.assertEqual(stored["status"], "failed")
        self.assertEqual(stored["quantities"], {})
        self.assertEqual(stored["issues"][0]["code"], "empty_data")
        self.assertEqual(stored["s"], 0.)
        self.assertEqual(stored["time"], 1e-9)
        self.assertEqual(to_summary(self.report)["checks"], ["example check"])
        self.assertEqual(to_summary(TimingData(self.source, "raw\r\ntext"))["text"], "raw\r\ntext")
        self.assertEqual(to_summary(RunFiles(Path("run")))["root"], "run")

    def test_existing_summary_round_trips_without_losing_diagnostics(self):
        result = self.result()
        result.quantities["rms_x"].value = np.nan
        summary = to_summary(result, validation=self.report)
        before = deepcopy(summary)
        path = write_json(summary, self.root / "already_summarized.json")
        self.assertEqual(json.loads(path.read_text()), summary)
        self.assertEqual(summary, before)
        self.assertTrue(json.loads(path.read_text())["serialization_issues"])

    def test_result_coordinates_are_checked_before_plot_export(self):
        result = self.result(s=np.inf)
        report = validate_analysis(result)
        self.assertIn("invalid_coordinate", {issue.code for issue in report.issues})
        summary = to_summary(result, validation=report)
        self.assertIsNone(summary["s"])
        self.assertFalse(summary["validation"]["is_valid"])

    def test_serialization_errors_do_not_create_files_or_overwrite(self):
        path = self.root / "result.json"
        write_json(self.table, path)
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            write_json(self.result(), path)
        self.assertEqual(path.read_bytes(), before)
        write_json(self.result(), path, overwrite=True)
        self.assertEqual(json.loads(path.read_text())["kind"], "analysis_result")
        with self.assertRaises(TypeError):
            write_json({"bad": object()}, self.root / "bad.json")
        self.assertFalse((self.root / "bad.json").exists())

    def test_csv_and_metadata_preserve_integer_precision_and_nonfinite_cells(self):
        self.table.columns["rms_x"][0] = np.nan
        path, sidecar = write_statistics_csv(self.table, self.root / "tables/stats.csv",
                                             columns=["id", "rms_x"], validation=self.report)
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(int(rows[0]["id"]), 2**53+1)
        self.assertEqual(rows[0]["rms_x"], "nan")
        restored = np.array([float(row["rms_x"]) for row in rows], dtype=np.float32)
        np.testing.assert_array_equal(restored, self.table.columns["rms_x"])
        metadata = json.loads(sidecar.read_text())
        self.assertEqual(sidecar.name, "stats.csv.metadata.json")
        self.assertEqual(metadata["columns"]["id"]["dtype"], "int64")
        self.assertEqual(metadata["units"], {"id": "1", "rms_x": "m"})
        self.assertEqual(metadata["columns"]["rms_x"]["nonfinite_count"], 1)
        self.assertTrue(metadata["serialization_issues"])
        self.assertFalse(metadata["export"]["units_converted"])

    def test_sidecar_collision_prevents_creating_csv(self):
        path = self.root / "stats.csv"
        sidecar = self.root / "stats.csv.metadata.json"
        sidecar.write_text("existing")
        with self.assertRaises(FileExistsError):
            write_statistics_csv(self.table, path)
        self.assertFalse(path.exists())
        self.assertEqual(sidecar.read_text(), "existing")
        write_statistics_csv(self.table, path, overwrite=True)
        self.assertTrue(path.exists())


class FodoExportTests(unittest.TestCase):
    def test_local_outputs_to_plot_arrays_json_and_csv(self):
        root = Path(__file__).resolve().parents[2] / "output/opalx-simulator/fodo-no-spacecharge"
        h5, stat = root / "FODO-no-spacecharge.h5", root / "FODO-no-spacecharge.stat"
        if not h5.exists() or not stat.exists():
            self.skipTest("Local FODO outputs unavailable")
        table = read_stat(stat)
        frame = to_dataframe(table, columns=["s", "rms_x", "emit_x"])
        np.testing.assert_array_equal(frame["s"].to_numpy(), table.columns["s"])
        results = []
        for step in list_snapshots(h5):
            data = read_snapshot(h5, step)
            results.append(analyze_snapshot(data, longitudinal_axis="z"))
        series = results_to_dataframe(results)
        self.assertEqual(len(series), 11)
        self.assertTrue(series["s"].is_monotonic_increasing)
        np.testing.assert_allclose(series["s"].iloc[-1], data.s)
        np.testing.assert_allclose(series["time"].iloc[-1], data.time)
        with TemporaryDirectory() as directory:
            path, metadata = write_statistics_csv(table, Path(directory) / "stats.csv",
                                                  validation=validate_statistics(table))
            self.assertTrue(json.loads(metadata.read_text())["validation"]["is_valid"])
            result_path = write_json(results[-1], Path(directory) / "last.json",
                                     validation=validate_analysis(results[-1], longitudinal_axis="z"))
            stored = json.loads(result_path.read_text())
            self.assertEqual(stored["covariances"]["phase_space"]["coordinates"], ["x", "px", "y", "py", "z", "pz"])
            np.testing.assert_allclose(stored["covariances"]["phase_space"]["values"],
                                       results[-1].covariances["phase_space"].values)
            self.assertEqual(stored["source"]["attributes"]["file_attributes"]["pxUnit"], "#beta#gamma")
            self.assertEqual(stored["quantities"]["rms_x"]["unit"], "m")
            with path.open(newline="") as handle:
                self.assertEqual(sum(1 for _ in csv.DictReader(handle)), table.row_count)


if __name__ == "__main__":
    unittest.main()
