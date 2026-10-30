"""COF reader, validation, discovery/export and offline DBA acceptance checks."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from postprocess import (
    discover_run, read_closed_orbit, select_file, to_summary,
    validate_closed_orbit, validate_run_files, write_json,
)
from postprocess.readers import AmbiguousOutputError

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / 'fixtures/dba'
SPEC = importlib.util.spec_from_file_location('dba_acceptance', HERE / 'check_dba.py')
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


class CofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = json.loads((FIXTURE / 'nominal/closed-orbit.json').read_text())

    def read(self, raw=None):
        path = self.root / 'closed-orbit.json'
        path.write_text(json.dumps(self.raw if raw is None else raw))
        return read_closed_orbit(path)

    def test_reader_preserves_reported_values_extensions_and_metadata(self):
        self.raw['future_extension'] = {'arbitrary': [1, 'two']}
        data = self.read()
        np.testing.assert_array_equal(data.matrix, self.raw['matrix'])
        np.testing.assert_array_equal(data.eigenvalues, self.raw['eigenvalues'])
        self.assertEqual(data.source.attributes, self.raw)
        self.assertEqual(data.coordinate_order, ('x', 'px', 'y', 'py'))
        self.assertEqual(data.units, ('m', 'p/(mc)', 'm', 'p/(mc)'))
        self.assertIsNone(data.source.opalx_version)
        self.assertTrue(validate_closed_orbit(data).is_valid)
        # Materialized arrays do not alias the original metadata lists.
        data.matrix[0, 0] = 99
        self.assertEqual(data.source.attributes['matrix'], self.raw['matrix'])

    def test_reader_rejects_unrelated_or_malformed_structures_with_context(self):
        bad = [[], {}, {'status': 'PASS'}]
        for name, value in [('matrix', [[1]]), ('coordinates', ['x']*4),
                            ('residual', [True]*4), ('converged', 1),
                            ('stability', None), ('eigenvalues', [1]*4)]:
            raw = deepcopy(self.raw)
            raw[name] = value
            bad.append(raw)
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'closed-orbit.json'):
                self.read(raw)
        for text in ('{"matrix":', '{"converged":true,"converged":false}'):
            path = self.root / 'broken.json'
            path.write_text(text)
            with self.assertRaisesRegex(ValueError, 'broken.json'):
                read_closed_orbit(path)

    def test_optional_eigenvalues_and_custom_filename(self):
        del self.raw['eigenvalues']
        data = self.read()
        self.assertIsNone(data.eigenvalues)
        self.assertTrue(validate_closed_orbit(data).is_valid)
        custom = self.root / 'custom.json'
        custom.write_text(json.dumps(self.raw))
        self.assertTrue(read_closed_orbit(custom).converged)

    def test_validation_separates_integrity_stability_and_strict_closure(self):
        data = self.read()
        data.stability = 'UNSTABLE'
        self.assertTrue(validate_closed_orbit(data).is_valid)
        self.assertFalse(validate_closed_orbit(data, require_stable=True).is_valid)
        data.residual[:] = [1e-7, 0, 0, 2e-7]
        self.assertTrue(validate_closed_orbit(data).is_valid)
        report = validate_closed_orbit(data, position_atol=1e-7)
        self.assertEqual([i.code for i in report.issues], ['closure_tolerance'])
        self.assertTrue(validate_closed_orbit(data, position_atol=2e-7).is_valid)
        self.assertFalse(validate_closed_orbit(data, momentum_atol=2e-7).is_valid)
        data.converged = False
        self.assertIn('not_converged', [i.code for i in validate_closed_orbit(data).issues])
        for bound in (0, -1, np.inf, np.nan, True):
            with self.assertRaises(ValueError):
                validate_closed_orbit(data, position_atol=bound)

    def test_nonfinite_mutated_arrays_and_bad_metadata_remain_diagnostic(self):
        self.raw['matrix'][0][0] = float('nan')
        self.raw['mass_eV'] = -1
        self.raw['position_m'] = [0, 1]
        self.raw['section_rotation_wxyz'] = [0]*4
        self.raw['fractional_modes'] = [{'tune': 2, 'complement': None}]
        data = self.read()
        report = validate_closed_orbit(data)
        self.assertFalse(report.is_valid)
        self.assertEqual(json.dumps(self.raw), json.dumps(data.source.attributes))
        self.assertTrue(all(i.source == data.source.path for i in report.issues))
        self.assertTrue({'matrix', 'mass_eV', 'position_m', 'section_rotation_wxyz'} <=
                        {i.field_name for i in report.issues})
        summary = to_summary(data, validation=report)
        self.assertIsNone(summary['matrix'][0][0])
        self.assertTrue(summary['serialization_issues'])
        with self.assertRaises(ValueError):
            to_summary(data, nonfinite='raise')
        data.residual = np.zeros((2, 2))
        self.assertFalse(validate_closed_orbit(data, position_atol=1e-7).is_valid)

    def test_discovery_selection_requirements_and_exports(self):
        data = self.read()
        (self.root / 'comparison.json').write_text('{}')
        derived = self.root / 'analysis/closed-orbit.json'
        derived.parent.mkdir()
        derived.write_text('{}')
        files = discover_run(self.root)
        self.assertEqual(files.closed_orbits, [Path('closed-orbit.json')])
        self.assertEqual(files.unhandled, [Path('comparison.json')])
        self.assertEqual(files.derived, [Path('analysis/closed-orbit.json')])
        self.assertEqual(select_file(files, 'closed_orbits'), Path('closed-orbit.json'))
        self.assertTrue(validate_run_files(files, required=('closed_orbits',)).is_valid)
        self.assertFalse(validate_run_files(files).is_valid)
        report = validate_closed_orbit(data)
        path = write_json(data, self.root / 'export.json', validation=report)
        summary = json.loads(path.read_text())
        self.assertEqual(summary['kind'], 'closed_orbit')
        self.assertEqual(summary['source']['attributes'], self.raw)
        self.assertEqual(summary['matrix'], self.raw['matrix'])
        self.assertTrue(summary['validation']['is_valid'])
        (self.root / 'nested').mkdir()
        (self.root / 'nested/CLOSED-ORBIT.JSON').write_text('{}')
        files = discover_run(self.root)
        with self.assertRaises(AmbiguousOutputError):
            select_file(files, 'closed_orbits')
        self.assertEqual(select_file(files, 'closed_orbits', 'nested/CLOSED-ORBIT.JSON'),
                         Path('nested/CLOSED-ORBIT.JSON'))
        self.assertIsNone(select_file(discover_run(derived.parent), 'statistics'))

    def test_fixture_integrity_and_both_historical_cases_pass(self):
        provenance = json.loads((FIXTURE / 'provenance.json').read_text())
        for name, record in provenance['files'].items():
            self.assertEqual(hashlib.sha256((FIXTURE/name).read_bytes()).hexdigest(), record['sha256'])
        for case in ('nominal', 'displaced'):
            local = self.root/case
            local.mkdir()
            for source, target in (('closed-orbit.json', 'closed-orbit.json'), ('run.log.txt', 'run.log')):
                (local/target).write_bytes((FIXTURE/case/source).read_bytes())
            result = acceptance.check_case(local, FIXTURE/'ring-slope-map.txt')
            self.assertEqual(result['status'], 'PASS')
            self.assertLess(result['max_matrix_error'], 1e-8)

    def test_acceptance_rejects_wrong_map_closure_and_missing_reference_momentum(self):
        log = self.root/'run.log'
        log.write_text('p0_mc=490.23677663749817 ')
        for field, value in [('matrix', np.eye(4).tolist()), ('residual', [0, 1e-7, 0, 0]),
                             ('converged', False), ('stability', 'UNSTABLE')]:
            raw = deepcopy(self.raw)
            raw[field] = value
            self.read(raw)
            self.assertEqual(acceptance.check_case(self.root, FIXTURE/'ring-slope-map.txt')['status'], 'FAIL')
        for text in ('', 'p0_mc=nan ', 'p0_mc=-1 ', 'p0_mc=1 p0_mc=2'):
            log.write_text(text)
            with self.assertRaises(ValueError):
                acceptance.check_case(self.root, FIXTURE/'ring-slope-map.txt')


if __name__ == '__main__':
    unittest.main()
