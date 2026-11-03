"""Fit explicit neon-switch parameter candidates to measured electrical traces."""

import argparse
from pathlib import Path

from plasma_rc.neon.calibration import run_parameter_sweep


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="CSV with synchronized time_s, drive_v, voltage_v[, current_a]")
    parser.add_argument("grid", type=Path, help="JSON file containing explicit parameter candidate lists")
    parser.add_argument("output", type=Path, help="new directory for candidate traces and ranked summary")
    parser.add_argument("--validation", type=Path, help="independent held-out electrical trace CSV")
    args = parser.parse_args()
    result = run_parameter_sweep(args.reference, args.grid, args.output, validation_path=args.validation)
    print(f"Best calibration score: {result['best']['calibration_score']:.6g}")
    if result["best"]["validation_score"] is not None:
        print(f"Best candidate validation score: {result['best']['validation_score']:.6g}")
    print("Physical accuracy is not established by this grid fit.")


if __name__ == "__main__":
    main()
