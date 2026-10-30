"""A2: consistency C, flash reliability and λ_c from E6 replicas (D-34).

Per bulb x regime: step features over the common segment (after each replica's own prefix),
z-scored with one scaler for replicas and silence runs. C is the mean pairwise correlation per
feature (Uchida 2008). λ_c uses only the continuous state (mean light, i_b, v per step): the
slope of the mean log-distance between replicas while above twice the silence-run distance
(untested hypothesis, A13). Flash-derived features are excluded from λ_c because they are
piecewise constant; flash timing is judged by flash reliability (Mainen & Sejnowski 1995).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from plasma_rc.trials.storage import trials
from experiments.ne2.common import RESULTS, parser


from plasma_rc.analysis.dynamics import analyse


def main(argv=None) -> int:
    p = parser(__doc__)
    p.add_argument("sessions", nargs="+", help="session folders written by E6")
    p.add_argument(
        "--window-s",
        type=float,
        default=None,
        help="flash match window (default: half a step)",
    )
    p.add_argument("--out", default=str(RESULTS / "a2_dynamics.csv"))
    p.add_argument("--allow-legacy", action="store_true")
    args = p.parse_args(argv)
    reps, sil = trials(args.sessions, "replica"), trials(args.sessions, "silence")
    groups = sorted({(r["bulb_id"], r["regime"]) for r in reps})
    out = [
        analyse(
            [r for r in reps if (r["bulb_id"], r["regime"]) == g],
            [r for r in sil if (r["bulb_id"], r["regime"]) == g],
            args.window_s,
            args.allow_legacy,
        )
        for g in groups
    ]
    if not out:
        raise SystemExit("no E6 (kind=replica) trials in these sessions")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    for r in out:
        print(
            f"{r['bulb_id']} {r['regime']}: C {r['consistency_C']:.3f}  lambda_c {r['lambda_c_per_s']:.3g} /s "
            f"{r['lambda_note']}  flashes matched {r['flash_matched_fraction']:.2f}, sigma {r['flash_median_sigma_s']:.3g} s"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
