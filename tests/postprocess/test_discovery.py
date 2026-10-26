"""Discovery checks use temporary directories and never launch simulations."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from postprocess.readers import AmbiguousOutputError, discover_run, select_file


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def create(self, *names):
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def test_classifies_fodo_layout_without_reading_contents(self):
        self.create(
            "beam.in", "beam.stat", "beam.h5", "timing.dat",
            "data/beam_DesignPath.dat", "data/elements.sdds", "orbit.json",
            "plots/validation_report.txt", "analysis/derived.stat",
            "analysis/derived.h5", "analysis/copied.in",
        )
        files = discover_run(self.root)
        self.assertEqual(files.root, self.root.resolve())
        self.assertEqual(files.statistics, [Path("beam.stat")])
        self.assertEqual(files.snapshots, [Path("beam.h5")])
        self.assertEqual(files.timings, [Path("timing.dat")])
        self.assertEqual(files.inputs, [Path("beam.in")])
        self.assertEqual(files.unhandled, [
            Path("data/beam_DesignPath.dat"), Path("data/elements.sdds"), Path("orbit.json"),
        ])
        self.assertEqual(files.derived, [
            Path("analysis/copied.in"), Path("analysis/derived.h5"),
            Path("analysis/derived.stat"), Path("plots/validation_report.txt"),
        ])

    def test_empty_and_partial_outputs(self):
        files = discover_run(self.root)
        for kind in ("statistics", "snapshots", "timings"):
            self.assertIsNone(select_file(files, kind))
        self.create("beam.stat")
        files = discover_run(self.root)
        self.assertEqual(select_file(files, "statistics"), Path("beam.stat"))
        self.assertIsNone(select_file(files, "snapshots"))

    def test_ambiguous_outputs_require_selection_and_are_sorted(self):
        self.create("z.stat", "nested/a.stat", "z.h5", "nested/a.h5",
                    "timing.dat", "nested/timing.dat")
        files = discover_run(self.root)
        self.assertEqual(files.statistics, [Path("nested/a.stat"), Path("z.stat")])
        for kind, choice in (("statistics", "nested/a.stat"),
                             ("snapshots", "nested/a.h5"), ("timings", "nested/timing.dat")):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(AmbiguousOutputError, "select a path"):
                    select_file(files, kind)
                self.assertEqual(select_file(files, kind, choice), Path(choice))
                self.assertEqual(select_file(files, kind, self.root / choice), Path(choice))

    def test_selection_rejects_wrong_kind_missing_and_outside_paths(self):
        self.create("beam.stat", "beam.h5", "plots/copied.stat")
        files = discover_run(self.root)
        for path in ("beam.h5", "missing.stat", "plots/copied.stat", "../outside.stat"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                select_file(files, "statistics", path)
        with self.assertRaises(ValueError):
            select_file(files, "unknown")

    def test_nested_candidates_case_and_configurable_derived_directories(self):
        self.create("nested/BEAM.STAT", "nested/BEAM.HDF5", "nested/TIMING.DAT",
                    "custom/copied.h5", "nested/plots/envelope.stat")
        files = discover_run(self.root, derived_directories=("custom", "plots"))
        self.assertEqual(files.snapshots, [Path("nested/BEAM.HDF5")])
        self.assertEqual(files.statistics, [Path("nested/BEAM.STAT")])
        self.assertEqual(files.timings, [Path("nested/TIMING.DAT")])
        self.assertEqual(len(files.derived), 2)
        self.assertEqual(len(discover_run(self.root, derived_directories=()).statistics), 2)

    def test_symlinks_are_unhandled_and_directories_not_traversed(self):
        self.create("real/beam.stat")
        (self.root / "alias.stat").symlink_to(self.root / "real/beam.stat")
        (self.root / "alias_directory").symlink_to(self.root / "real", target_is_directory=True)
        (self.root / "broken.h5").symlink_to(self.root / "absent.h5")
        files = discover_run(self.root)
        self.assertEqual(files.statistics, [Path("real/beam.stat")])
        self.assertEqual(files.unhandled, [Path("alias.stat"), Path("alias_directory"), Path("broken.h5")])
        with self.assertRaises(ValueError):
            select_file(files, "statistics", "alias_directory/beam.stat")

    def test_invalid_root_and_traversal_errors(self):
        with self.assertRaises(FileNotFoundError):
            discover_run(self.root / "absent")
        self.create("beam.stat")
        with self.assertRaises(NotADirectoryError):
            discover_run(self.root / "beam.stat")

        def failed_walk(path, *, on_error):
            on_error(PermissionError("Cannot inspect subdirectory"))
            return iter(())

        with patch.object(Path, "walk", failed_walk):
            with self.assertRaises(PermissionError):
                discover_run(self.root)


if __name__ == "__main__":
    unittest.main()
