"""Synthetic reader fixtures; optional FODO checks require only local outputs."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import h5py
import numpy as np

from postprocess.readers import list_snapshots, read_snapshot, read_stat, read_timing


STAT = '''SDDS1
! comments are not data
&description text="Header, with &end inside quotes", contents="test" &end
&parameter name=revision, type=string &end
&parameter name=processors, type=long &end
&parameter name=species, type=string, fixed_value="PROTON" &end
&column name=t, type=double, units=ns, description="Time, elapsed" &end
&column
 name=id, type=long64, units=1
&end
&column name=extra, type=float &end
&data mode=ascii, no_row_counts=1 &end
OPALX 0.9 git rev. #test
2
1.0 9007199254740993 0.5
! another comment
2.0 9007199254740994 nan
'''


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write_stat(self, text=STAT):
        path = self.root / "beam.stat"
        path.write_text(text)
        return path

    def write_h5(self):
        path = self.root / "beam.h5"
        with h5py.File(path, "w") as handle:
            handle.attrs["OPAL_version"] = np.bytes_("OPALX test")
            handle.attrs["xUnit"] = np.bytes_("m")
            handle.attrs["TIMEUnit"] = np.bytes_("ns")
            handle.attrs["SPOSUnit"] = np.bytes_("cm")
            handle.attrs["raw_array"] = [1.0, 2.0]
            handle.create_group("other_metadata")
            for step in (10, 2, 0):
                group = handle.create_group(f"Step#{step}")
                group.attrs["TIME"] = [2.0]
                group.attrs["SPOS"] = [25.0]
                group.attrs["GlobalTrackStep"] = [step * 100]
                group.create_dataset("id", data=np.array([2**53 + 1, 2**53 + 2], dtype="int64"))
                group.create_dataset("x", data=[1.0, 2.0])
                dataset = group.create_dataset("px", data=[0.1, 0.2])
                dataset.attrs["units"] = "p/(mc)"
                dataset.attrs["description"] = "Normalized momentum"
        return path

    def test_stat_types_units_parameters_and_unknown_columns(self):
        path = self.write_stat()
        table = read_stat(path)
        self.assertEqual(table.row_count, 2)
        self.assertEqual(table.columns["id"].dtype, np.dtype("int64"))
        self.assertEqual(int(table.columns["id"][0]), 9007199254740993)
        self.assertEqual(table.columns["extra"].dtype, np.dtype("float32"))
        self.assertTrue(np.isnan(table.columns["extra"][1]))
        self.assertEqual(table.fields["t"].unit, "ns")
        self.assertEqual(table.fields["t"].description, "Time, elapsed")
        self.assertIsNone(table.fields["extra"].unit)
        self.assertEqual(table.source.attributes["species"], "PROTON")
        self.assertEqual(table.source.attributes["processors"], 2)
        self.assertEqual(table.source.opalx_version, "OPALX 0.9 git rev. #test")
        self.assertIn("sdds_header", table.source.attributes)
        self.assertEqual(table.source.path, path.resolve())

    def test_stat_empty_and_single_row_tables(self):
        empty = STAT[:STAT.index("1.0 9007")]
        self.assertEqual(read_stat(self.write_stat(empty)).row_count, 0)
        table = read_stat(self.write_stat(empty + "1 9007199254740993 3\n"))
        self.assertEqual(table.columns["t"].shape, (1,))

    def test_stat_rejects_bad_rows_without_skipping(self):
        for bad in ("1 2", "1 not_an_integer 3", "1 9223372036854775808 3", "1 2 3 4"):
            with self.subTest(row=bad):
                text = STAT.replace("1.0 9007199254740993 0.5", bad)
                with self.assertRaisesRegex(ValueError, r"beam.stat: .*line"):
                    read_stat(self.write_stat(text))

    def test_stat_rejects_unsupported_layouts_and_broken_headers(self):
        variants = [
            STAT.replace("mode=ascii", "mode=binary"),
            STAT.replace("no_row_counts=1", "no_row_counts=0"),
            STAT.replace("no_row_counts=1", "no_row_counts=1, column_major_order=1"),
            STAT.replace("type=long64", "type=string"),
            STAT.replace("name=extra", "name=id"),
            STAT.replace("&column name=extra", "&array name=extra"),
            "SDDS1\n&column name=x, type=double\n",
            "SDDS1\n&column name=x, type=double &end\n",
            "garbage\n",
            STAT[:STAT.index("OPALX 0.9")],
        ]
        for text in variants:
            with self.subTest(text=text[-80:]), self.assertRaises(ValueError):
                read_stat(self.write_stat(text))

    def test_h5_inventory_does_not_read_datasets(self):
        path = self.write_h5()
        with patch.object(h5py.Dataset, "__getitem__", side_effect=AssertionError("dataset read")):
            self.assertEqual(list_snapshots(path), [0, 2, 10])

    def test_h5_loads_only_requested_dump_preserves_metadata_and_closes(self):
        path = self.write_h5()
        original = h5py.Dataset.__getitem__
        loaded = []

        def record(dataset, key):
            loaded.append(dataset.name)
            return original(dataset, key)

        with patch.object(h5py.Dataset, "__getitem__", record):
            snapshot = read_snapshot(path, 10)
        self.assertEqual(set(loaded), {"/Step#10/id", "/Step#10/x", "/Step#10/px"})
        self.assertEqual(snapshot.particle_count, 2)
        self.assertEqual(int(snapshot.columns["id"][0]), 2**53 + 1)
        self.assertEqual(snapshot.s, 0.25)
        self.assertEqual(snapshot.time, 2e-9)
        self.assertEqual(snapshot.source.attributes["TIME"][0], 2.0)
        self.assertEqual(snapshot.source.attributes["GlobalTrackStep"][0], 1000)
        self.assertEqual(snapshot.source.opalx_version, "OPALX test")
        np.testing.assert_array_equal(snapshot.source.attributes["file_attributes"]["raw_array"], [1, 2])
        self.assertEqual(snapshot.source.attributes["dataset_attributes"]["px"]["units"], "p/(mc)")
        self.assertEqual(snapshot.fields["x"].unit, "m")
        self.assertEqual(snapshot.fields["px"].description, "Normalized momentum")
        self.assertIsNone(snapshot.coordinate_frame)
        self.assertIsNone(snapshot.momentum_convention)
        # Reopening for writing succeeds: the returned model holds no live handles.
        with h5py.File(path, "r+") as handle:
            handle["Step#10/x"][0] = 99
        self.assertEqual(snapshot.columns["x"][0], 1.0)

    def test_h5_unknown_units_and_missing_coordinates_are_not_guessed(self):
        path = self.write_h5()
        with h5py.File(path, "r+") as handle:
            handle.attrs["TIMEUnit"] = "unknown"
            del handle["Step#0"].attrs["SPOS"]
            handle["Step#0/x"].attrs["units"] = "mm"
        snapshot = read_snapshot(path, 0)
        self.assertIsNone(snapshot.s)
        self.assertIsNone(snapshot.time)
        self.assertEqual(snapshot.fields["x"].unit, "mm")
        self.assertEqual(snapshot.columns["x"][0], 1.0)

    def test_h5_bad_selection(self):
        path = self.write_h5()
        for step in (1, -1, True, 0.5, "0"):
            with self.subTest(step=step), self.assertRaises(ValueError):
                read_snapshot(path, step)

    def test_h5_rejects_bad_groups_and_links(self):
        for name, kind in (("Step#bad", "group"), ("Step#00", "group"),
                           ("Step#3", "dataset"), ("Step#3", "link")):
            path = self.write_h5()
            with h5py.File(path, "r+") as handle:
                if kind == "group":
                    handle.create_group(name)
                elif kind == "dataset":
                    handle.create_dataset(name, data=[1])
                else:
                    handle[name] = h5py.SoftLink("/Step#0")
            with self.subTest(name=name, kind=kind), self.assertRaises(ValueError):
                list_snapshots(path)
        with h5py.File(self.root / "empty.h5", "w"):
            pass
        with self.assertRaises(ValueError):
            list_snapshots(self.root / "empty.h5")

    def test_h5_rejects_malformed_particle_layouts(self):
        for variant in ("length", "rank", "text", "group", "link", "coordinate"):
            path = self.write_h5()
            with h5py.File(path, "r+") as handle:
                group = handle["Step#0"]
                if variant == "length":
                    group.create_dataset("bad", data=[1])
                elif variant == "rank":
                    group.create_dataset("bad", data=[[1, 2]])
                elif variant == "text":
                    group.create_dataset("bad", data=[b"a", b"b"])
                elif variant == "group":
                    group.create_group("nested")
                elif variant == "link":
                    group["alias"] = h5py.SoftLink("/Step#0/x")
                else:
                    group.attrs["TIME"] = [1, 2]
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, "step 0"):
                read_snapshot(path, 0)

    def test_h5_empty_and_nonfinite_arrays_are_retained(self):
        path = self.root / "minimal.h5"
        with h5py.File(path, "w") as handle:
            handle.create_group("Step#0").create_dataset("x", data=[])
            handle.create_group("Step#1").create_dataset("x", data=[np.nan])
        self.assertEqual(read_snapshot(path, 0).particle_count, 0)
        self.assertTrue(np.isnan(read_snapshot(path, 1).columns["x"][0]))

    def test_timing_preserves_sections_and_line_endings(self):
        path = self.root / "timing.dat"
        raw = b"ranks Wall tot\r\nmainTimer... 1 10.63\r\n\r\nranks Wall max Wall min Wall avg\r\nmainTimer... 1 10.63 10.63 10.63\r\n"
        path.write_bytes(raw)
        timing = read_timing(path)
        self.assertEqual(timing.text.encode("utf-8"), raw)
        self.assertEqual(timing.source.path, path.resolve())
        path.write_text("")
        self.assertEqual(read_timing(path).text, "")

    def test_missing_files_raise(self):
        for reader in (read_stat, list_snapshots, read_timing):
            with self.subTest(reader=reader), self.assertRaises((FileNotFoundError, OSError)):
                reader(self.root / "missing")
        with self.assertRaises(OSError):
            read_snapshot(self.root / "missing", 0)


class FodoReaderTests(unittest.TestCase):
    def test_local_reference_outputs(self):
        root = Path(__file__).resolve().parents[2] / "output/opalx-simulator/fodo-no-spacecharge"
        if not all((root / name).exists() for name in
                   ("FODO-no-spacecharge.stat", "FODO-no-spacecharge.h5", "timing.dat")):
            self.skipTest("Local FODO outputs are not available")
        table = read_stat(root / "FODO-no-spacecharge.stat")
        self.assertEqual(len(table.columns), 47)
        self.assertEqual(table.row_count, 1087)
        self.assertEqual(table.fields["t"].unit, "ns")
        self.assertEqual(table.source.attributes["species"], "PROTON")
        path = root / "FODO-no-spacecharge.h5"
        self.assertEqual(list_snapshots(path), list(range(11)))
        first, last = read_snapshot(path, 0), read_snapshot(path, 10)
        self.assertEqual(first.particle_count, 10000)
        self.assertEqual(last.particle_count, 10000)
        self.assertEqual(first.fields["px"].unit, "#beta#gamma")
        self.assertAlmostEqual(first.s, 0.18395383, places=7)
        self.assertAlmostEqual(last.time, 1.087e-8, places=14)
        # Compare stored outputs only, without asserting unresolved moment semantics.
        self.assertAlmostEqual(table.columns["t"][-1] * 1e-9, last.time, places=18)
        self.assertAlmostEqual(table.columns["s"][-1], last.s, places=6)
        self.assertIn("mainTimer", read_timing(root / "timing.dat").text)


if __name__ == "__main__":
    unittest.main()
