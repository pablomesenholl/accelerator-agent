"""Offline DBA COF acceptance; consumes existing outputs, never runs OPALX."""

import argparse
from pathlib import Path
import re

import numpy as np

from postprocess import read_closed_orbit, to_summary, validate_closed_orbit, write_json


def check_case(case: Path, reference: Path) -> dict:
    """Use the benchmark's logged reference momentum and transverse slope map."""
    case, reference = Path(case), Path(reference)
    data = read_closed_orbit(case / "closed-orbit.json")
    report = validate_closed_orbit(data, require_stable=True,
                                   position_atol=1e-7, momentum_atol=1e-7)
    matches = re.findall(r"\bp0_mc=([^\s]+)", (case / "run.log").read_text())
    if len(matches) != 1:
        raise ValueError("Expected exactly one logged p0_mc reference momentum")
    p0 = float(matches[0])
    if not np.isfinite(p0) or p0 <= 0:
        raise ValueError("Logged p0_mc must be finite and positive")
    analytic = np.loadtxt(reference)
    if analytic.shape not in ((4, 4), (6, 6)) or not np.all(np.isfinite(analytic)):
        raise ValueError("Expected finite 4x4 or 6x6 analytic slope map")
    transform = np.diag([1., p0, 1., p0])
    measured = np.linalg.solve(transform, data.matrix @ transform)
    difference = measured - analytic[:4, :4]
    error = float(np.max(np.abs(difference)))
    return {"status": "PASS" if report.is_valid and error < 1e-6 else "FAIL",
            "case": str(case.resolve()), "reference": str(reference.resolve()),
            "p0_mc": p0, "max_matrix_error": error,
            "map_tolerance": 1e-6, "position_scale_m": 1.,
            "slope_map": measured, "difference": difference,
            "closed_orbit": to_summary(data, validation=report)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path, help="Directory containing closed-orbit.json and run.log")
    parser.add_argument("--reference", required=True, type=Path, help="Analytic ring-slope-map.txt")
    parser.add_argument("--output", type=Path, help="New JSON report path")
    args = parser.parse_args()
    try:
        result = check_case(args.case, args.reference)
        if args.output:
            write_json(result, args.output)
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"{result['status']}: maximum map error {result['max_matrix_error']:.6g}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
