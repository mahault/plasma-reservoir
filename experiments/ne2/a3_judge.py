"""A3 (objectives task 11): S1-S3 verdicts from A1 and A2.

Per regime: average repeats per bulb, then mean +/- std over bulbs. A criterion passes when
the bulb's mean - std lies above the comparison's mean + std (our operationalisation of
"above ..., mean +/- std over bulbs", objectives doc; Inferred). S1: nonlinear IPC above the
shuffled floor and the resistor control. S2: MC above both controls. S3: consistency is reported;
its pass threshold waits for the chosen consistency reference (objectives doc open question).
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from experiments.ne2.common import RESULTS, parser


def per_bulb(rows: list[dict], regime: str, control: str, key: str) -> np.ndarray:
    by = defaultdict(list)
    for r in rows:
        if r["regime"] == regime and r["control"] == control:
            by[r["bulb_id"]].append(float(r[key]))
    return np.array([np.mean(v) for v in by.values()])


def above(a: np.ndarray, b: np.ndarray) -> bool | None:
    if len(a) == 0 or len(b) == 0:
        return None
    return bool(a.mean() - a.std() > b.mean() + b.std())


def fmt(a: np.ndarray) -> str:
    return "n/a" if len(a) == 0 else f"{a.mean():.3f} ± {a.std():.3f} (n={len(a)})"


def main(argv=None) -> int:
    p = parser(__doc__)
    p.add_argument("--a1", default=str(RESULTS / "a1_ipc.csv"))
    p.add_argument("--a2", default=str(RESULTS / "a2_dynamics.csv"))
    p.add_argument("--out", default=str(RESULTS / "a3_judge.md"))
    args = p.parse_args(argv)
    ipc_rows = list(csv.DictReader(open(args.a1)))
    dyn = list(csv.DictReader(open(args.a2))) if Path(args.a2).exists() else []
    lines = [
        "| regime | criterion | bulb | comparison | verdict |",
        "|---|---|---|---|---|",
    ]
    verdict = {True: "PASS", False: "FAIL", None: "missing data"}
    for regime in sorted({r["regime"] for r in ipc_rows}):
        nl = per_bulb(ipc_rows, regime, "none", "nonlinear")
        for name, ref in (
            (
                "shuffled floor",
                per_bulb(ipc_rows, regime, "none", "nonlinear_shuffled"),
            ),
            ("resistor control", per_bulb(ipc_rows, regime, "resistor", "nonlinear")),
        ):
            lines.append(
                f"| {regime} | S1 nonlinear IPC > {name} | {fmt(nl)} | {fmt(ref)} | {verdict[above(nl, ref)]} |"
            )
        mc = per_bulb(ipc_rows, regime, "none", "mc")
        for ctrl in ("resistor", "audio-only"):
            ref = per_bulb(ipc_rows, regime, ctrl, "mc")
            lines.append(
                f"| {regime} | S2 MC > {ctrl} control | {fmt(mc)} | {fmt(ref)} | {verdict[above(mc, ref)]} |"
            )
        c = np.array([float(r["consistency_C"]) for r in dyn if r["regime"] == regime])
        lines.append(
            f"| {regime} | S3 consistency C | {fmt(c)} | threshold pending | reported only |"
        )
    text = (
        "\n".join(lines)
        + "\n\nH1 needs S1-S3 across bulbs in at least one regime; otherwise report the negative result.\n"
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
