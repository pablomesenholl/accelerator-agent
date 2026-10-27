"""Local acceptance check for straight FODO outputs; never launches OPALX.

Use the project .venv interpreter. --confirm-z-longitudinal asserts
compatible straight-lattice position/momentum axes. A reference profile pins
existing files and narrowly identifies the known legacy centroid metadata bug.
No reference means all reported mismatches fail, including centroid mismatches.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import sys

import h5py
import numpy as np
import pandas as pd

from postprocess import (
    analyze_snapshot, compare_diagnostics, discover_run, list_snapshots,
    read_snapshot, read_stat, read_timing, results_to_dataframe, select_file,
    to_dataframe, to_summary, validate_analysis, validate_run_files,
    validate_snapshot, validate_statistics, validate_timing,
    write_json, write_statistics_csv,
)


def _hash(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _valid(report, stage):
    _require(report.is_valid, f"{stage}: " + "; ".join(
        f"{issue.code} ({issue.field_name}): {issue.message}"
        for issue in report.issues if issue.severity == "error"))


def _known_centroid(snapshot, issue, reference):
    revision = reference.get("known_centroid_bug_revision") if reference else None
    if (not revision or revision not in (snapshot.source.opalx_version or "")
        or issue.code != "reported_mismatch"
        or issue.source != snapshot.source.path
        or issue.field_name not in {"centroid[0]", "centroid[1]", "centroid[2]"}):
        return False
    raw = snapshot.source.attributes.get("centroid")
    expected = np.array([snapshot.columns[name].sum() for name in ("x", "px", "y")])
    return raw is not None and np.asarray(raw).shape == (3,) and bool(
        np.allclose(raw, expected, rtol=1e-10, atol=1e-14))


def _plots(table, series, output):
    # Direct Agg canvas: no GUI, interactive backend or display server required.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    for name, columns, label in (
        ("envelope.png", ("rms_x", "rms_y"), "RMS beam size [m]"),
        ("normalized_emittance.png", ("emit_nx", "emit_ny"), "Normalized emittance [m]"),
    ):
        figure = Figure(figsize=(7, 4), tight_layout=True)
        FigureCanvasAgg(figure)
        axis = figure.subplots()
        for column in columns:
            reported = column.replace("emit_n", "emit_")
            axis.plot(table.columns["s"], table.columns[reported], label=f"stat: {reported}")
            axis.plot(series["s"], series[column], "o", label=f"particles: {column}")
        axis.set(xlabel="Path length [m]", ylabel=label)
        axis.legend()
        figure.savefig(output / name)
        _require((output / name).stat().st_size > 1000, f"Plot is empty: {name}")


def check_fodo(run, output, *, confirm_z_longitudinal=False, reference=None, plots=True):
    """Write an acceptance bundle to a new directory; return its report dict.

    Intended for straight FODO data in shared position/momentum axes. Input files
    are hashed before/after. Checks and exceptions yield a failed report rather
    than a false success. Output/precondition failures raise before any report.
    Existing destinations and output nested under input are refused.
    """
    _require(confirm_z_longitudinal, "Confirm compatible axes with longitudinal z before checking FODO optics")
    run, output = Path(run).resolve(strict=True), Path(output).resolve()
    _require(run.is_dir(), "Run input must be a directory")
    _require(not output.is_relative_to(run), "Acceptance output must be outside the source run")
    output.mkdir(parents=True, exist_ok=False)
    stages = {name: "not_run" for name in
              ("discovery", "reading", "input_validation", "analysis", "comparisons", "exports", "plots")}
    report = {"schema_version": 1, "kind": "fodo_acceptance", "status": "failed",
              "input": str(run), "output": str(output), "simulation_executed": False,
              "assumptions": ["Straight FODO; caller confirms common axes with longitudinal z",
                              "Equal macroparticle population; no particles filtered"],
              "stages": stages, "snapshots": [], "known_issues": [], "errors": [],
              "reference_verified": False, "source_unchanged": None}
    manifest = {"schema_version": 1, "kind": "fodo_input_manifest", "files": {},
                "software": {"python": platform.python_version(), "numpy": np.__version__,
                             "pandas": pd.__version__, "h5py": h5py.__version__}}
    originals = {}
    active_stage = "discovery"
    try:
        files = discover_run(run)
        file_report = validate_run_files(files)
        report["file_validation"] = to_summary(file_report)
        _valid(file_report, "Output files")
        stat_path = files.root / select_file(files, "statistics")
        h5_path = files.root / select_file(files, "snapshots")
        timing = select_file(files, "timings")
        paths = [stat_path, h5_path] + ([files.root / timing] if timing is not None else [])
        originals = {path: _hash(path) for path in paths}
        manifest["files"] = {str(path.relative_to(run)): {"sha256": digest, "bytes": path.stat().st_size}
                             for path, digest in originals.items()}
        profile = None
        if reference is not None:
            reference = Path(reference).resolve(strict=True)
            profile = json.loads(reference.read_text(encoding="utf-8"))
            for path in (stat_path, h5_path):
                relative = str(path.relative_to(run))
                _require(profile["files"].get(relative) == originals[path], f"Reference hash mismatch: {relative}")
            report["reference_verified"] = True
            manifest["reference"] = {"path": str(reference), "sha256": _hash(reference)}
        stages[active_stage] = "passed"

        active_stage = "reading"
        table = read_stat(stat_path)
        steps = list_snapshots(h5_path)
        report["statistics_rows"], report["statistics_columns"] = table.row_count, len(table.columns)
        report["snapshot_steps"] = steps
        if profile:
            for key, value in (("statistics_rows", table.row_count),
                               ("statistics_columns", len(table.columns)), ("snapshot_steps", steps)):
                _require(profile[key] == value, f"Reference {key} differs")
        if timing is not None:
            data = read_timing(files.root / timing)
            timing_report = validate_timing(data)
            report["timing_validation"] = to_summary(timing_report)
            write_json(data, output / "timing.json", validation=timing_report)
        stages[active_stage] = "passed"

        active_stage = "input_validation"
        stat_report = validate_statistics(table)
        report["statistics_validation"] = to_summary(stat_report)
        _valid(stat_report, "Statistics")
        # This acceptance profile compares/plots known SI statistics, not arbitrary
        # unit-labelled tables. Reject unsupported conventions instead of guessing.
        for name in ("s", "rms_x", "rms_y", "emit_x", "emit_y", "mean_x", "mean_y", "mean_s"):
            _require(name in table.columns and name in table.fields and table.fields[name].unit == "m",
                     f"FODO acceptance requires {name} in metres")
        results, calculation_reports = [], []
        for step in steps:
            active_stage = "input_validation"
            for name in ("input_validation", "analysis", "comparisons"):
                if stages[name] == "not_run":
                    stages[name] = "incomplete"
            snapshot = read_snapshot(h5_path, step)
            input_report = validate_snapshot(snapshot, longitudinal_axis="z")
            item = {"step": step, "particle_count": snapshot.particle_count,
                    "input_validation": to_summary(input_report)}
            report["snapshots"].append(item)
            _valid(input_report, f"Snapshot {step}")
            _require(snapshot.s is not None and snapshot.time is not None, "Snapshot time/path must be available")
            if profile:
                _require(snapshot.particle_count == profile["particles_per_snapshot"], "Reference particle count differs")

            active_stage = "analysis"
            result = analyze_snapshot(snapshot, longitudinal_axis="z")
            calculation = validate_analysis(result, longitudinal_axis="z")
            item["calculation_validation"] = to_summary(calculation)
            _valid(calculation, f"Calculation {step}")
            _require(result.status == "success", "Calculation did not complete")
            results.append(result)
            calculation_reports.append(calculation)

            active_stage = "comparisons"
            comparison = compare_diagnostics(snapshot, result, table, frame_confirmed=True,
                                             rtol=1e-10, atol=1e-14)
            item["comparison"] = to_summary(comparison)
            unexpected = []
            for issue in comparison.issues:
                if issue.severity != "error":
                    continue
                if _known_centroid(snapshot, issue, profile):
                    report["known_issues"].append(to_summary({"step": step, "issue": issue})["data"])
                else:
                    unexpected.append(f"{issue.code}: {issue.field_name}: {issue.message}")
            _require(not unexpected, f"Snapshot {step} unexpected comparison errors: {unexpected}")
            # Prevent a skipped/unmatched comparison from counting as acceptance.
            _require(any("unique statistics time match:" in check for check in comparison.checks), "No unique time match")
            _require("statistics path coordinate agreement" in comparison.checks, "Path matching did not run")
            for name in ("mean_x", "mean_y", "mean_s", "rms_x", "rms_y", "emit_x", "emit_y", "numParticles"):
                _require(any(f":{name}[" in check for check in comparison.checks), f"Comparison did not run: {name}")
            write_json(result, output / "snapshots" / f"step_{step}.json", validation=calculation)
        stages["input_validation"] = stages["analysis"] = "passed"
        stages["comparisons"] = "passed_with_known_issue" if report["known_issues"] else "passed"

        active_stage = "exports"
        series = results_to_dataframe(results, validation_reports=calculation_reports)
        _require(len(series) == len(steps), "Analysis-series row count differs")
        changes = {}
        for plane in ("x", "y"):
            values = series[f"emit_n{plane}"].to_numpy()
            _require(values[0] > 0, "Reference initial emittance must be positive")
            changes[plane] = float(np.max(np.abs(values / values[0] - 1)))
            if profile:
                _require(np.isclose(changes[plane], profile["expected_max_relative_normalized_emittance_change"][plane],
                                    rtol=1e-8, atol=1e-12), "FODO emittance variation differs from measured reference")
        report["max_relative_normalized_emittance_change"] = changes
        if profile:
            energy = table.columns["energy"]
            _require(energy[0] > 0, "Reference energy must be positive")
            energy_change = float(np.max(np.abs(energy / energy[0] - 1)))
            report["max_relative_energy_change"] = energy_change
            _require(energy_change <= profile["max_relative_energy_change"], "FODO energy drift exceeds reference bound")
        csv_path, sidecar = write_statistics_csv(table, output / "statistics.csv", validation=stat_report)
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for name, values in table.columns.items():
            restored = np.array([row[name] for row in rows], dtype=values.dtype)
            _require(np.array_equal(restored, values, equal_nan=True), f"CSV round trip differs: {name}")
        metadata = json.loads(sidecar.read_text())
        _require(metadata["validation"]["is_valid"], "CSV validation metadata lost")
        series.to_csv(output / "series.csv", index=False)
        write_json(series.attrs, output / "series.metadata.json")
        for result in results:
            loaded = json.loads((output / "snapshots" / f"step_{result.step}.json").read_text())
            _require(loaded == to_summary(result, validation=calculation_reports[steps.index(result.step)]), "JSON round trip differs")
        frame = to_dataframe(table, columns=["s", "rms_x", "rms_y"])
        _require(np.array_equal(frame["s"].to_numpy(), table.columns["s"]), "Plot table changes coordinates")
        stages[active_stage] = "passed"
        if plots:
            active_stage = "plots"
            _plots(table, series, output)
            stages[active_stage] = "passed"
        else:
            stages["plots"] = "skipped_by_request"
        report["status"] = "passed_with_known_issue" if report["known_issues"] else "passed"
    except (OSError, ValueError, TypeError, KeyError) as error:
        stages[active_stage] = "failed"
        report["errors"].append({"stage": active_stage, "type": type(error).__name__, "message": str(error)})
    finally:
        if originals:
            report["source_unchanged"] = all(path.is_file() and _hash(path) == digest for path, digest in originals.items())
            if not report["source_unchanged"]:
                report["status"] = "failed"
                report["errors"].append({"stage": "source_integrity", "message": "Input hashes changed during acceptance"})
        write_json(manifest, output / "manifest.json")
        report["artifacts"] = sorted(str(path.relative_to(output)) for path in output.rglob("*") if path.is_file())
        report["artifacts"].append("report.json")
        write_json(report, output / "report.json")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New directory outside the input run")
    parser.add_argument("--reference", type=Path, help="Optional checksum-pinned FODO profile")
    parser.add_argument("--confirm-z-longitudinal", required=True, action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = check_fodo(args.input, args.output, confirm_z_longitudinal=args.confirm_z_longitudinal,
                            reference=args.reference, plots=not args.no_plots)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(f"{report['status']}: {args.output / 'report.json'}")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
