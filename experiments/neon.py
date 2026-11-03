"""Run the neon and LED experiment suite."""

import argparse
from pathlib import Path

from plasma_rc.neon.figures import generate_figures
from plasma_rc.neon.optical import analyze_optical
from plasma_rc.neon.report import analyze_study
from plasma_rc.neon.study import run_pulse_study, run_study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new output directory")
    parser.add_argument("--steps", type=int, default=900)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--max-step", type=float, default=5e-6, help="maximum ngspice step, seconds")
    parser.add_argument("--ballast", type=float, default=1e6, help="neon ballast resistance, ohms")
    parser.add_argument("--capacitance", type=float, default=1e-9, help="assumed node capacitance, farads")
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be positive")
    args.output.mkdir(parents=True, exist_ok=False)
    study = args.output / "study"
    optical = args.output / "optical"
    run_study(study, list(range(args.seeds)), n_steps=args.steps, max_step_s=args.max_step,
              ballast_ohm=args.ballast, capacitance_f=args.capacitance)
    analyze_study(study)
    analyze_optical(study, optical)
    run_pulse_study(args.output / "pulse", [0.5e6, 2e6], capacitance_f=args.capacitance)
    generate_figures(study, optical, args.output / "figures", args.output / "pulse")


if __name__ == "__main__":
    main()
