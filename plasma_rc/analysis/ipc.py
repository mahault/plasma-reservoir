"""IPC analysis of a validated recorded trial; current input is not memory."""

import numpy as np
from plasma_rc.trials.storage import load_trial
from plasma_rc.stimuli import levels_to_u
from plasma_rc.characterization.features import step_features
from plasma_rc.characterization.ipc import ipc


def analyse(row: dict, max_delay: int, max_degree: int, allow_legacy=False) -> dict:
    cap = load_trial(row["raw_file"])
    cap.require_integrity(allow_legacy)
    with np.load(row["raw_file"]) as d:
        u = levels_to_u(d["levels"])
    analog = ("0",) if row["control"] == "audio-only" else ("1", "2", "3")
    x = step_features(cap, int(row["ticks_per_step"]), len(u), analog)
    x = (x - x.mean(0)) / np.where(x.std(0) > 0, x.std(0), 1.0)
    res = ipc(x, u, max_delay, max_degree, np.random.default_rng(0))
    floor = ipc(
        x,
        np.random.default_rng(1).permutation(u),
        max_delay,
        max_degree,
        np.random.default_rng(0),
    )
    keys = ("name", "bulb_id", "regime", "control", "repeat")
    return {
        **{k: row[k] for k in keys},
        "mc": res["mc"],
        "instantaneous_linear": res["instantaneous_linear"],
        "nonlinear": res["nonlinear"],
        "total": res["total"],
        "nonlinear_shuffled": floor["nonlinear"],
        "mc_shuffled": floor["mc"],
        "n_steps": res["n_steps"],
        "rank": int(np.linalg.matrix_rank(x)),
    }
