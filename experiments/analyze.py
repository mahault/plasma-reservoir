"""Analyze a saved acquisition trial."""

import argparse
from pathlib import Path

from plasma_rc.neon.capture import load_recording
from plasma_rc.neon.experiment import analyze_recording, save_analysis
from plasma_rc.neon.figures import generate_figures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("output", type=Path, help="new analysis directory")
    args = parser.parse_args(argv)
    _, _, u, _ = load_recording(args.recording)
    n = len(u)
    if n < 60:
        parser.error("at least 60 steps are required")
    args.output.mkdir(parents=True, exist_ok=False)
    result = analyze_recording(args.recording, (max(10, n // 10), n // 2),
                               (n // 2, n * 7 // 10), (n * 7 // 10, n - 1))
    save_analysis(args.output / "analysis.json", result)
    generate_figures(result, args.output / "figures")


if __name__ == "__main__":
    main()
