"""Analytic population-moment fixtures and optional local FODO comparisons."""

from pathlib import Path
import unittest

import numpy as np

from postprocess import analyze_snapshot
from postprocess.models import FieldMetadata, ParticleSnapshot, SourceMetadata
from postprocess.readers import list_snapshots, read_snapshot, read_stat


def snapshot():
    # Orthogonal, zero-mean, unit-variance populations; no random sampling error.
    u = np.array([-1.0, -1.0, 1.0, 1.0])
    v = np.array([-1.0, 1.0, -1.0, 1.0])
    columns = {
        "x": 10 + 2 * u, "px": 1 + 3 * u + 4 * v,
        "y": -4 + 3 * v, "py": -2 + u - 2 * v,
        "z": u + v, "pz": np.full(4, 2.0), "q": np.full(4, -1e-12),
    }
    fields = {name: FieldMetadata("p/(mc)" if name.startswith("p") else "m")
              for name in ("x", "px", "y", "py", "z", "pz")}
    return ParticleSnapshot(7, "Step#7", columns, SourceMetadata(Path("synthetic.h5")), fields)


class AnalysisTests(unittest.TestCase):
    def test_full_coupled_covariance_from_orthogonal_population(self):
        # Six zero-mean orthogonal columns with exact population variance 1.
        u, v, w = np.array(np.meshgrid([-1., 1.], [-1., 1.], [-1., 1.])).reshape(3, -1)
        basis = np.column_stack((u, v, w, u*v, u*w, v*w))
        transform = np.diag([.002, .0003, .003, .0004, .005, .01])
        transform[0, 2], transform[3, 1], transform[4, 0] = .001, .0002, .002
        means = np.array([.01, .001, -.02, -.001, .03, 2.])
        population = basis @ transform.T + means
        axes = ("x", "px", "y", "py", "z", "pz")
        data = snapshot()
        data.columns = {name: population[:, i] for i, name in enumerate(axes)}
        result = analyze_snapshot(data, longitudinal_axis="z")
        expected = transform @ transform.T
        np.testing.assert_allclose(result.covariances["phase_space"].values, expected, rtol=1e-12, atol=1e-18)
        for i, name in enumerate(axes):
            self.assertAlmostEqual(result.quantities[f"centroid_{name}"].value, means[i])
        for plane, start in (("x", 0), ("y", 2)):
            block = expected[start:start+2, start:start+2]
            np.testing.assert_allclose(result.quantities[f"emit_n{plane}"].value,
                                       np.sqrt(np.linalg.det(block)), rtol=1e-12)

    def test_linear_drift_preserves_emittance_and_transports_twiss(self):
        data = snapshot()
        before = analyze_snapshot(data, longitudinal_axis="z")
        length = .75
        for plane in ("x", "y"):
            data.columns[plane] += length * data.columns["p" + plane] / data.columns["pz"]
        after = analyze_snapshot(data, longitudinal_axis="z")
        for plane in ("x", "y"):
            a, b, g = (before.quantities[f"{name}_{plane}"].value for name in ("alpha", "beta", "gamma"))
            for name, expected in (("alpha", a-length*g), ("beta", b-2*length*a+length**2*g), ("gamma", g)):
                self.assertAlmostEqual(after.quantities[f"{name}_{plane}"].value, expected)
            for key in (f"emit_n{plane}", f"emit_{plane}"):
                self.assertAlmostEqual(after.quantities[key].value, before.quantities[key].value)

    def test_known_moments_emittances_twiss_and_covariance_order(self):
        result = analyze_snapshot(snapshot(), longitudinal_axis="z")
        self.assertEqual(result.status, "success")
        expected = {
            "num_particles": 4, "centroid_x": 10, "rms_x": 2,
            "centroid_px": 1, "rms_px": 5, "centroid_y": -4, "rms_y": 3,
            "emit_nx": 8, "emit_x": 4, "alpha_x": -0.75,
            "beta_x": 1, "gamma_x": 1.5625, "rms_x_prime": 2.5,
            "emit_ny": 3, "emit_y": 1.5, "alpha_y": 2,
            "beta_y": 6, "gamma_y": 5 / 6,
        }
        for name, value in expected.items():
            with self.subTest(name=name):
                self.assertAlmostEqual(result.quantities[name].value, value)
        covariance = result.covariances["phase_space"]
        self.assertEqual(covariance.coordinates, ("x", "px", "y", "py", "z", "pz"))
        self.assertEqual(covariance.units, ("m", "p/(mc)", "m", "p/(mc)", "m", "p/(mc)"))
        np.testing.assert_allclose(covariance.values[:2, :2], [[4, 6], [6, 25]])
        self.assertEqual(result.quantities["beta_x"].unit, "m")
        self.assertEqual(result.quantities["gamma_x"].unit, "1/m")
        for plane in ("x", "y"):
            q = result.quantities
            self.assertAlmostEqual(q[f"beta_{plane}"].value * q[f"gamma_{plane}"].value
                                   - q[f"alpha_{plane}"].value**2, 1.0)

    def test_geometric_optics_require_explicit_axis_confirmation(self):
        result = analyze_snapshot(snapshot())
        self.assertEqual(result.status, "success")
        self.assertIn("emit_nx", result.quantities)
        self.assertNotIn("emit_x", result.quantities)
        self.assertNotIn("alpha_x", result.quantities)
        with self.assertRaises(ValueError):
            analyze_snapshot(snapshot(), longitudinal_axis="x")

    def test_translation_invariance_and_no_input_mutation(self):
        data = snapshot()
        reference = analyze_snapshot(data, longitudinal_axis="z")
        data.columns["x"] += 1e12
        data.columns["px"] += 1e9
        before = {name: values.copy() for name, values in data.columns.items()}
        result = analyze_snapshot(data, longitudinal_axis="z")
        for name in ("rms_x", "rms_px", "emit_nx", "emit_x", "alpha_x", "beta_x", "gamma_x"):
            self.assertAlmostEqual(result.quantities[name].value, reference.quantities[name].value)
        for name in before:
            np.testing.assert_array_equal(data.columns[name], before[name])
        self.assertEqual(data.fields["x"].unit, "m")

    def test_varying_longitudinal_momentum_uses_particle_slopes(self):
        data = snapshot()
        data.columns["pz"] = np.array([1.0, 2.0, 3.0, 4.0])
        result = analyze_snapshot(data, longitudinal_axis="z")
        covariance = np.cov(data.columns["x"], data.columns["px"] / data.columns["pz"], ddof=0)
        expected = np.sqrt(np.linalg.det(covariance))
        self.assertAlmostEqual(result.quantities["emit_x"].value, expected)
        self.assertNotAlmostEqual(expected, result.quantities["emit_nx"].value / np.mean(data.columns["pz"]))

    def test_centred_rms_is_not_raw_rms(self):
        result = analyze_snapshot(snapshot())
        self.assertEqual(result.quantities["rms_x"].value, 2)
        self.assertNotEqual(result.quantities["rms_x"].value, np.sqrt(104))

    def test_unit_conversion_and_normalization_metadata(self):
        data = snapshot()
        for name in ("x", "y", "z"):
            data.columns[name] *= 1000
            data.fields[name].unit = "mm"
        for name in ("px", "py", "pz"):
            data.fields[name].unit = "#beta#gamma"
        result = analyze_snapshot(data, longitudinal_axis="z")
        self.assertAlmostEqual(result.quantities["emit_nx"].value, 8)
        self.assertAlmostEqual(result.quantities["rms_y"].value, 3)
        self.assertEqual(result.quantities["rms_x"].unit, "m")
        self.assertEqual(data.fields["x"].unit, "mm")

    def test_unknown_units_preserve_raw_moments_and_block_emittance(self):
        data = snapshot()
        data.fields["x"].unit = None
        data.fields["py"].unit = "1"
        result = analyze_snapshot(data, longitudinal_axis="z")
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.quantities["rms_x"].value, 2)
        self.assertIsNone(result.quantities["rms_x"].unit)
        self.assertNotIn("emit_nx", result.quantities)
        self.assertNotIn("emit_ny", result.quantities)
        data.momentum_convention = "p/(mc)"
        self.assertIn("emit_ny", analyze_snapshot(data).quantities)
        data.momentum_convention = "slopes"
        self.assertNotIn("emit_ny", analyze_snapshot(data).quantities)

    def test_unequal_charge_warning_without_changing_weighting(self):
        data = snapshot()
        data.columns["q"] *= np.array([1.0, 2.0, 3.0, 4.0])
        result = analyze_snapshot(data)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.quantities["centroid_x"].value, 10)
        self.assertTrue(any(issue.code == "unequal_charges" and issue.severity == "warning"
                            for issue in result.issues))
        del data.columns["q"]
        self.assertIn("weights_unverified", [issue.code for issue in analyze_snapshot(data).issues])

    def test_mixed_species_skip_optics(self):
        data = snapshot()
        data.columns["sp"] = np.array([1, 2, 1, 2])
        result = analyze_snapshot(data, longitudinal_axis="z")
        self.assertEqual(result.status, "partial")
        self.assertIn("rms_x", result.quantities)
        self.assertNotIn("emit_nx", result.quantities)
        self.assertIn("mixed_species", [issue.code for issue in result.issues])

    def test_missing_and_nonfinite_data_give_partial_results(self):
        data = snapshot()
        data.columns["x"][0] = np.nan
        del data.columns["z"]
        result = analyze_snapshot(data, longitudinal_axis="z")
        self.assertEqual(result.status, "partial")
        self.assertNotIn("rms_x", result.quantities)
        self.assertNotIn("emit_nx", result.quantities)
        self.assertNotIn("phase_space", result.covariances)
        self.assertIn("emit_ny", result.quantities)
        self.assertIn("beta_y", result.quantities)
        codes = [issue.code for issue in result.issues]
        self.assertIn("nonfinite_data", codes)
        self.assertIn("missing_field", codes)
        self.assertTrue(all(issue.source == data.source.path and issue.step == 7 for issue in result.issues))

    def test_empty_and_all_invalid_data_fail(self):
        for value in (np.array([]), np.array([np.nan])):
            data = snapshot()
            data.columns = {name: value for name in ("x", "px", "y", "py", "z", "pz")}
            result = analyze_snapshot(data, longitudinal_axis="z")
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.quantities, {})

    def test_mutated_inconsistent_dimensions_are_reported(self):
        data = snapshot()
        data.columns["y"] = np.ones(3)
        data.columns["py"] = np.ones((4, 1))
        result = analyze_snapshot(data)
        self.assertEqual(result.status, "partial")
        self.assertNotIn("rms_y", result.quantities)
        self.assertNotIn("rms_py", result.quantities)

    def test_zero_emittance_is_valid_but_twiss_is_undefined(self):
        for single_particle in (False, True):
            data = snapshot()
            data.columns["px"] = 3 * data.columns["x"]
            if single_particle:
                data.columns = {name: value[:1] for name, value in data.columns.items()}
            result = analyze_snapshot(data, longitudinal_axis="z")
            self.assertEqual(result.quantities["emit_nx"].value, 0)
            self.assertEqual(result.quantities["emit_x"].value, 0)
            self.assertNotIn("alpha_x", result.quantities)
            self.assertNotIn("beta_x", result.quantities)
            self.assertEqual(result.status, "partial")
            self.assertIn("undefined_twiss", [issue.code for issue in result.issues])

    def test_nearly_correlated_emittance_avoids_determinant_cancellation(self):
        data = snapshot()
        u = np.array([-1., -1., 1., 1.])
        v = np.array([-1., 1., -1., 1.])
        data.columns["x"], data.columns["px"] = u, u + 1e-10 * v
        result = analyze_snapshot(data, longitudinal_axis="z")
        self.assertEqual(result.status, "success")
        np.testing.assert_allclose(result.quantities["emit_nx"].value, 1e-10, rtol=2e-6)

    def test_zero_backward_and_nonfinite_pz_do_not_produce_geometric_optics(self):
        for bad in (0.0, -1.0, np.inf):
            data = snapshot()
            data.columns["pz"][0] = bad
            result = analyze_snapshot(data, longitudinal_axis="z")
            self.assertEqual(result.status, "partial")
            self.assertIn("emit_nx", result.quantities)
            self.assertNotIn("emit_x", result.quantities)

    def test_numerical_overflow_is_an_issue_not_infinite_output(self):
        data = snapshot()
        data.columns["x"] = np.array([1e308, -1e308, 1e308, -1e308])
        result = analyze_snapshot(data, longitudinal_axis="z")
        self.assertEqual(result.status, "partial")
        self.assertNotIn("rms_x", result.quantities)
        self.assertIn("calculation_failed", [issue.code for issue in result.issues])
        self.assertTrue(all(np.all(np.isfinite(q.value)) for q in result.quantities.values()))


class FodoAnalysisTests(unittest.TestCase):
    def test_recomputed_moments_match_stored_fodo_diagnostics(self):
        root = Path(__file__).resolve().parents[2] / "output/opalx-simulator/fodo-no-spacecharge"
        h5_path, stat_path = root / "FODO-no-spacecharge.h5", root / "FODO-no-spacecharge.stat"
        if not h5_path.exists() or not stat_path.exists():
            self.skipTest("Local FODO outputs are unavailable")
        table = read_stat(stat_path)
        for step in list_snapshots(h5_path):
            data = read_snapshot(h5_path, step)
            # This fixture is a straight FODO lattice; no bend-frame reconstruction.
            result = analyze_snapshot(data, longitudinal_axis="z")
            self.assertEqual(result.status, "success")
            row = int(np.argmin(np.abs(table.columns["t"] * 1e-9 - data.time)))
            self.assertAlmostEqual(table.columns["t"][row] * 1e-9, data.time, places=18)
            for index, plane in enumerate(("x", "y")):
                with self.subTest(step=step, plane=plane):
                    q = result.quantities
                    np.testing.assert_allclose(q[f"rms_{plane}"].value,
                                               data.source.attributes["RMSX"][index], rtol=1e-12)
                    np.testing.assert_allclose(q[f"emit_n{plane}"].value,
                                               data.source.attributes["#varepsilon"][index], rtol=1e-12)
                    np.testing.assert_allclose(q[f"emit_n{plane}"].value,
                                               table.columns[f"emit_{plane}"][row], rtol=1e-12)
                    np.testing.assert_allclose(q[f"rms_{plane}"].value,
                                               table.columns[f"rms_{plane}"][row], rtol=1e-12)
                    np.testing.assert_allclose(q[f"centroid_{plane}"].value,
                                               table.columns[f"mean_{plane}"][row], rtol=1e-10, atol=1e-18)
                    self.assertAlmostEqual(q[f"beta_{plane}"].value * q[f"gamma_{plane}"].value
                                           - q[f"alpha_{plane}"].value**2, 1.0, places=12)
                    # OPALX's reported geometric emittance uses a different estimator.
                    self.assertGreater(q[f"emit_{plane}"].value, 0)


if __name__ == "__main__":
    unittest.main()
