"""Run an exploratory NE-2H-labeled NARMA-10 parameter search."""

import argparse
from pathlib import Path

from plasma_rc.neon.ne2h_study import run_ne2h_study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new directory for traces, figures, summary, and report")
    parser.add_argument("--steps", type=int, default=450)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--max-step", type=float, default=20e-6, help="maximum ngspice timestep in seconds")
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be positive")
    result = run_ne2h_study(args.output, seeds=tuple(range(args.seeds)), n_steps=args.steps,
                            max_step_s=args.max_step)
    print(f"Validation-best parameter set: candidate {result['selection']['best_candidate_index']}")
    print(f"Held-out NARMA-10 NMSE: {result['best']['mean']:.4f} ± {result['best']['std']:.4f}")
    print(f"Report: {args.output / 'report.md'}")
    print("Exploratory simulation only; this is not physical calibration.")


if __name__ == "__main__":
    main()
