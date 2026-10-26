"""Offline data contract checks; no OPALX execution or Magnus requests."""

from pathlib import Path
import unittest

import numpy as np

from postprocess.models import (
    AnalysisResult, CovarianceMatrix, FieldMetadata, ParticleSnapshot,
    Quantity, RunFiles, SourceMetadata, StatisticsTable, ValidationIssue,
)


class DataContractTests(unittest.TestCase):
    def setUp(self):
        self.source = SourceMetadata(Path("beam.h5"))

    def test_particle_ids_keep_integer_precision_and_arrays_are_shared(self):
        ids = np.array([2**53 + 1, 2**53 + 2], dtype=np.int64)
        snapshot = ParticleSnapshot(
            step=10, group_name="Step#10", source=self.source,
            columns={"id": ids, "x": np.array([0.1, 0.2])},
            fields={"x": FieldMetadata("m")}, s=2.0, time=1e-8,
        )
        self.assertIs(snapshot.columns["id"], ids)
        self.assertEqual(int(snapshot.columns["id"][0]), 2**53 + 1)
        self.assertEqual(snapshot.particle_count, 2)
        self.assertIsNone(snapshot.coordinate_frame)
        self.assertIsNone(snapshot.momentum_convention)

    def test_statistics_preserve_units_and_source_metadata(self):
        source = SourceMetadata(
            Path("beam.stat"), opalx_version="OPALX 0.9",
            attributes={"species": "PROTON", "processors": 1},
        )
        table = StatisticsTable(
            columns={"t": np.array([1.0, 2.0])}, source=source,
            fields={"t": FieldMetadata("ns", "Time")},
        )
        np.testing.assert_array_equal(table.columns["t"], [1.0, 2.0])
        self.assertEqual(table.fields["t"].unit, "ns")
        self.assertEqual(table.row_count, 2)
        self.assertEqual(table.source.attributes["species"], "PROTON")
        self.assertIsNone(FieldMetadata().unit)

    def test_table_and_snapshot_reject_inconsistent_columns(self):
        invalid = [
            ({"x": [1.0]}, TypeError),
            ({"x": np.ones((2, 1))}, ValueError),
            ({"x": np.ones(2), "px": np.ones(3)}, ValueError),
            ({"x": np.array(["bad"])}, TypeError),
            ({"x": np.array([1j])}, TypeError),
        ]
        for columns, exception in invalid:
            for constructor in (
                lambda: StatisticsTable(columns, self.source),
                lambda: ParticleSnapshot(0, "Step#0", columns, self.source),
            ):
                with self.subTest(columns=columns, constructor=constructor):
                    with self.assertRaises(exception):
                        constructor()

    def test_empty_and_nonfinite_data_remain_available_for_validation(self):
        self.assertEqual(StatisticsTable({}, self.source).row_count, 0)
        snapshot = ParticleSnapshot(0, "Step#0", {"x": np.array([])}, self.source)
        self.assertEqual(snapshot.particle_count, 0)
        table = StatisticsTable({"x": np.array([np.nan])}, self.source)
        self.assertTrue(np.isnan(table.columns["x"][0]))

    def test_covariance_requires_matching_axes_and_units(self):
        covariance = CovarianceMatrix(np.eye(2), ("x", "px"), ("m", "p/(mc)"))
        self.assertEqual(covariance.coordinates, ("x", "px"))
        for values, axes, units, exception in [
            (np.eye(3), ("x", "px"), ("m", "1"), ValueError),
            (np.eye(2), ("x", "px"), ("m",), ValueError),
            (np.eye(2), ("x", "x"), ("m", "m"), ValueError),
            ([[1]], ("x",), ("m",), TypeError),
            (np.array([["bad"]]), ("x",), ("m",), TypeError),
        ]:
            with self.subTest(axes=axes, units=units):
                with self.assertRaises(exception):
                    CovarianceMatrix(values, axes, units)

    def test_failed_calculation_is_distinct_from_zero_quantity(self):
        issue = ValidationIssue(
            "singular_covariance", "Twiss is undefined for zero emittance",
            "error", source=self.source.path, step=0, field_name="twiss_x",
        )
        result = AnalysisResult(
            self.source, "partial", step=0,
            quantities={"emit_x": Quantity(0.0, "m rad", "sqrt(det(cov(x, x_prime)))")},
            issues=[issue], assumptions=["Equal macroparticle weighting"],
        )
        self.assertEqual(result.quantities["emit_x"].value, 0.0)
        self.assertNotIn("twiss_x", result.quantities)
        self.assertEqual(result.issues[0].code, "singular_covariance")
        self.assertEqual(AnalysisResult(self.source, "failed", issues=[issue]).quantities, {})

    def test_mutable_defaults_are_independent(self):
        first, second = RunFiles(Path("run")), RunFiles(Path("other"))
        first.unhandled.append(Path("orbit.json"))
        self.assertEqual(second.unhandled, [])
        self.source.attributes["raw"] = np.array([1.0])
        self.assertEqual(SourceMetadata(Path("other.h5")).attributes, {})
        first_result = AnalysisResult(self.source, "success")
        second_result = AnalysisResult(self.source, "success")
        first_result.assumptions.append("Equal weighting")
        self.assertEqual(second_result.assumptions, [])


if __name__ == "__main__":
    unittest.main()
