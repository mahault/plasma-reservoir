"""S2: seeded simulated E4/E6 sessions; profiles and analysis live in shared modules.

Illustrative device parameters; results do not demonstrate physical NE-2 computation.
"""

import argparse
from dataclasses import asdict
import json
import time
import numpy as np
from experiments.ne2.common import RESULTS
from plasma_rc.analysis.ipc import analyse as a1_analyse
from plasma_rc.analysis.dynamics import analyse as a2_analyse
from plasma_rc.analysis.features import virtual_node_features
from plasma_rc.trials.metadata import RunMeta
from plasma_rc.trials.storage import load_trial, write_trial, trials
from plasma_rc.stimuli import levels_to_u, replica_levels, xorshift32_levels
from plasma_rc.simulation.config import (
    PROFILES,
    TEENSY41,
    CONDITIONS,
    SEED0,
    circuit,
    SimulationSetup,
)
from plasma_rc.characterization.features import step_features
from plasma_rc.characterization.ipc import ipc

N_STEPS, SEEDS = 1500, 5
N_PREFIX, N_COMMON, REPEATS = 100, 300, 5
LIGHT = {
    "delay_Y_bg=100": dict(Y_res=0.0, Y_bg=100.0),
    "delay_Y_bg=1000": dict(Y_res=0.0, Y_bg=1000.0),
}
SWEEPS = {
    "Y_bg": [1.0, 100.0, 1000.0],
    "tau_res": [0.03, 3.0],
    "margin": [0.25, 1.0],
    "C_c": [0.1e-6],
    "I_min": [20e-6, 100e-6],
}


def meta(name, repeat):
    return RunMeta(
        f"sim-{name}",
        "near-breakdown",
        "none",
        float("nan"),
        0.0,
        None,
        "simulated",
        repeat,
    )


def capacity(cap, levels, tps, n, virtual=False):
    x = virtual_node_features(cap, tps, n) if virtual else step_features(cap, tps, n)
    x = (x - x.mean(0)) / np.where(x.std(0) > 0, x.std(0), 1.0)
    return ipc(x, levels_to_u(levels), 20, 3, np.random.default_rng(0))


def e4(session, name, p, seeds=SEEDS, profile=TEENSY41, oversample=None):
    out = []
    for seed in range(seeds):
        levels = xorshift32_levels(SEED0 + seed, N_STEPS)
        setup = SimulationSetup(p, profile, seed, oversample)
        cap = setup.run(levels)
        write_trial(
            session,
            f"ipc_{name}_s{seed}",
            cap,
            meta(name, seed),
            dict(
                kind="ipc",
                ticks_per_step=profile.tps,
                n_steps=N_STEPS,
                n_prefix=0,
                levels=levels,
                setup=setup.metadata(),
            ),
        )
        x = step_features(cap, profile.tps, N_STEPS)[:, 2:3]
        v = ipc(
            (x - x.mean()) / (x.std() or 1.0),
            levels_to_u(levels),
            20,
            3,
            np.random.default_rng(0),
        )
        res = capacity(cap, levels, profile.tps, N_STEPS)
        out.append(
            dict(
                flashes_per_step=len(cap.flash_tick) / N_STEPS,
                mc_v_only=v["mc"],
                nonlinear_v_only=v["nonlinear"],
                per_degree=res["per_degree"],
            )
        )
    rows = [r for r in trials([session], "ipc") if r["bulb_id"] == f"sim-{name}"]
    return [{**o, **a1_analyse(r, 20, 3)} for o, r in zip(out, rows)]


def e6(session, name, p, profile=TEENSY41):
    for r in range(REPEATS):
        lv = replica_levels(SEED0 + 1 + r, N_PREFIX, SEED0, N_COMMON)
        extra = dict(ticks_per_step=profile.tps, n_steps=N_COMMON, n_prefix=N_PREFIX)
        for kind, levels, seed in [
            ("replica", lv, 100 + r),
            ("silence", np.full(len(lv), 128, np.uint8), 200 + r),
        ]:
            setup = SimulationSetup(p, profile, seed)
            write_trial(
                session,
                f"{kind}_{name}_r{r}",
                setup.run(levels),
                meta(name, r),
                {**extra, "kind": kind, "levels": levels, "setup": setup.metadata()},
            )
    groups = [
        [r for r in trials([session], kind) if r["bulb_id"] == f"sim-{name}"]
        for kind in ("replica", "silence")
    ]
    return a2_analyse(*groups, None)


def virtual_nodes(session, name):
    rows = []
    for r in trials([session], "ipc"):
        if r["bulb_id"] != f"sim-{name}":
            continue
        with np.load(r["raw_file"]) as d:
            levels = d["levels"]
        rows.append(
            capacity(
                load_trial(r["raw_file"]),
                levels,
                int(r["ticks_per_step"]),
                len(levels),
                True,
            )
        )
    return {
        k: [float(np.mean([r[k] for r in rows])), float(np.std([r[k] for r in rows]))]
        for k in ("instantaneous_linear", "mc", "nonlinear", "total")
    }


def summary(rows):
    keys = (
        "instantaneous_linear",
        "mc",
        "nonlinear",
        "total",
        "nonlinear_shuffled",
        "mc_v_only",
        "nonlinear_v_only",
        "flashes_per_step",
    )
    out = {
        k: [float(np.mean([r[k] for r in rows])), float(np.std([r[k] for r in rows]))]
        for k in keys
    }
    out["per_degree"] = {
        d: float(np.mean([r["per_degree"].get(d, 0.0) for r in rows]))
        for d in (1, 2, 3)
    }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--board", choices=PROFILES, default="teensy41")
    ap.add_argument(
        "--out",
        type=str,
        default=None,
        help="new output directory; existing trials are never overwritten",
    )
    args = ap.parse_args()
    profile = PROFILES[args.board]
    from pathlib import Path

    root = (
        Path(args.out)
        if args.out
        else RESULTS / f"sim_sessions_{profile.board}_{time.time_ns()}"
    )
    if root.exists():
        raise FileExistsError(f"choose a new output directory: {root}")
    out = {
        "setup": {
            "acquisition": asdict(profile),
            "n_steps": N_STEPS,
            "seeds": SEEDS,
            "base": asdict(circuit(profile=profile)),
        },
        "conditions": {},
        "sweeps": {},
    }
    for name, over in CONDITIONS.items():
        p = circuit(profile=profile, **over)
        out["conditions"][name] = {
            "e4": summary(e4(root / "e4", name, p, profile=profile)),
            "e6": e6(root / "e6", name, p, profile),
            "e4_virtual_nodes": virtual_nodes(root / "e4", name),
        }
    for key, values in SWEEPS.items():
        for val in values:
            name = f"{key}={val:g}"
            out["sweeps"][name] = summary(
                e4(
                    root / "sweeps",
                    name,
                    circuit(profile=profile, **{key: val}),
                    profile=profile,
                )
            )
    for name, over in LIGHT.items():
        out["sweeps"][name] = summary(
            e4(root / "sweeps", name, circuit(profile=profile, **over), profile=profile)
        )
    out["dt_check"] = {
        tag: summary(
            e4(
                root / "dt",
                tag,
                circuit(profile=profile),
                seeds=2,
                profile=profile,
                oversample=mult * profile.oversample,
            )
        )
        for tag, mult in [("dt-base", 1), ("dt-half", 2)]
    }
    (root / "summary.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"Wrote {root}; pass its e4 directory to S6 with --session")


if __name__ == "__main__":
    main()
