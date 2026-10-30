"""S6: NARMA-10 on the simulated bulb (roadmap step 2), from the saved S2 E4 trials (Teensy 4.1).

The held-step drive u in [-1, 1] is mapped onto NARMA's input range, u_n = (u + 1) / 4 in [0, 0.5], and
the target is narma10_target(u_n) (Atiya & Parlos 2000). The state after step k predicts y(k + 1).
Readout: ridge, penalty chosen by CV on the training steps only (sklearn RidgeCV); steps 100-999 train,
1000-1499 test; NMSE on the test steps. Feature sets: the A1 five features and the 4-virtual-node set
of each S2 bulb model, and input-only references: u(k) alone; a 10-tap linear delay line u(k..k-9);
the delay line plus all its pairwise products (holds the target's u(t) u(t-9) term: an upper
reference). 5 seeds (the S2 trials). Run s2_sim_reservoir.py first.
"""

from __future__ import annotations

import json
from itertools import combinations_with_replacement

import numpy as np
from plasma_rc.trials.storage import trials
from experiments.ne2.common import RESULTS
from plasma_rc.simulation.config import CONDITIONS
from plasma_rc.analysis.features import virtual_node_features
from sklearn.linear_model import RidgeCV

from plasma_rc.trials.storage import load_trial
from plasma_rc.stimuli import levels_to_u
from plasma_rc.benchmarks.narma import narma10_target
from plasma_rc.characterization.features import step_features
from plasma_rc.evaluation.metrics import nmse

WASHOUT, SPLIT, TAPS = 100, 1000, 10


def delay_line(u: np.ndarray, taps: int = TAPS) -> np.ndarray:
    return np.column_stack(
        [np.concatenate([np.zeros(d), u[: len(u) - d]]) for d in range(taps)]
    )


def with_products(x: np.ndarray) -> np.ndarray:
    pairs = combinations_with_replacement(range(x.shape[1]), 2)
    return np.column_stack([x] + [x[:, i] * x[:, j] for i, j in pairs])


def score(x: np.ndarray, y: np.ndarray) -> float:
    """Test NMSE of a ridge readout of state x(k) for target y(k + 1)."""
    x, y = x[:-1], y[1:]
    tr, te = slice(WASHOUT, SPLIT), slice(SPLIT, None)
    mu, sd = x[tr].mean(0), x[tr].std(0)
    z = (x - mu) / np.where(sd > 0, sd, 1.0)
    model = RidgeCV(alphas=np.logspace(-6, 3, 19)).fit(z[tr], y[tr])
    return nmse(y[te], model.predict(z[te]))


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--allow-legacy", action="store_true")
    args = parser.parse_args()
    rows = {}
    for r in trials([str(args.session)], "ipc"):
        cap = load_trial(r["raw_file"])
        cap.require_integrity(args.allow_legacy)
        tps, n_steps = int(r["ticks_per_step"]), int(r["n_steps"])
        if n_steps <= SPLIT + 1:
            raise ValueError("NARMA requires a nonempty test segment after step 1000")
        u_n = (levels_to_u(np.load(r["raw_file"])["levels"]) + 1) / 4
        y = narma10_target(u_n)
        name = r["bulb_id"].removeprefix("sim-")
        rows.setdefault(f"{name}: 5 features", []).append(
            score(step_features(cap, tps, n_steps), y)
        )
        rows.setdefault(f"{name}: 4 virtual nodes", []).append(
            score(virtual_node_features(cap, tps, n_steps), y)
        )
        if name == "linear":  # the input references depend only on u, once per seed
            rows.setdefault("input u(k) only", []).append(score(u_n[:, None], y))
            rows.setdefault("10-tap delay line", []).append(score(delay_line(u_n), y))
            rows.setdefault("10-tap delay line + products", []).append(
                score(with_products(delay_line(u_n)), y)
            )
    if not rows:
        raise ValueError("no IPC trials found")
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = {
        "setup": {
            "conditions": list(CONDITIONS),
            "washout": WASHOUT,
            "train_end": SPLIT,
            "n_steps": "per-trial recorded",
            "taps": TAPS,
            "session": str(args.session),
        },
        "nmse": {
            k: {
                "mean": float(np.mean(v)),
                "std": float(np.std(v)),
                "median": float(np.median(v)),
                "per_seed": [float(x) for x in v],
            }
            for k, v in rows.items()
        },
    }
    (RESULTS / "sim_narma.json").write_text(json.dumps(out, indent=1))
    for k, v in out["nmse"].items():
        print(
            f"{k:40s} NMSE {v['mean']:.3f} ± {v['std']:.3f}, median {v['median']:.3f}"
        )


if __name__ == "__main__":
    main()
