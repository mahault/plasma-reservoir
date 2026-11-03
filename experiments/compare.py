"""Compare analyzed neon and LED trials with matching input."""

import argparse
import json
from pathlib import Path
from plasma_rc.neon.experiment import compare_trials, save_analysis


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("analyses", type=Path, nargs="+")
    args = parser.parse_args(argv)
    trials = [json.loads(path.read_text()) for path in args.analyses]
    save_analysis(args.output, {"pairs": compare_trials(trials),
                               "note": "Matched input and split only; inspect sensor and drive comparability; repeated pairs are not independent."})


if __name__ == "__main__":
    main()
