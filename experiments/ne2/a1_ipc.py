"""A1 (objectives tasks 9-10): memory capacity, nonlinear IPC and total IPC of every E4 trial.

Readout features per step (technical.md §5): mean light, i_b and node voltage, flash count and
last inter-flash interval; the audio-only control uses the A0 input tap instead. Capacities follow
Dambre et al. 2012 with the shuffled-input cutoff and Richardson correction (D-35); the same
analysis on shuffled u gives the noise floor reported next to each value (task 9).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from experiments.ne2.common import RESULTS, parser



from plasma_rc.trials.storage import trials
from plasma_rc.analysis.ipc import analyse


def main(argv=None) -> int:
    p = parser(__doc__)
    p.add_argument("sessions", nargs="+", help="session folders written by E4")
    p.add_argument(
        "--max-delay", type=int, default=20, help="past steps in the target basis"
    )
    p.add_argument(
        "--max-degree", type=int, default=3, help="highest total Legendre degree"
    )
    p.add_argument("--out", default=str(RESULTS / "a1_ipc.csv"))
    p.add_argument(
        "--allow-legacy",
        action="store_true",
        help="allow historical records with unknown drop status",
    )
    args = p.parse_args(argv)
    out = [
        analyse(r, args.max_delay, args.max_degree, args.allow_legacy)
        for r in trials(args.sessions, "ipc")
    ]
    if not out:
        raise SystemExit("no E4 (kind=ipc) trials in these sessions")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    for r in out:
        print(
            f"{r['name']}: MC {r['mc']:.3f}  nonlinear {r['nonlinear']:.3f} (shuffled {r['nonlinear_shuffled']:.3f})"
            f"  total {r['total']:.3f}  rank {r['rank']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
