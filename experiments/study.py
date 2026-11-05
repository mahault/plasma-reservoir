"""Method-validation study (docs/study_2026-11-04.md): simulated lamps, controls and baselines under every
benchmark, plus time-scale sweeps. SIM-01: these results test the circuit and the analysis, not a real lamp.
    python -m experiments.study results/study_20261104 [--workers 20]
"""
import argparse
import json
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from plasma_rc import analysis as A
from plasma_rc import benchmarks as B
from plasma_rc.circuit import Config
from plasma_rc.sim import afterglow_delay, iid_delay, simulate
from plasma_rc.states import FINE, sim_states
from plasma_rc.stimuli import binary_input, held_input, rank_levels
from plasma_rc.surrogate import surrogate_states

CONFIG = Path(__file__).resolve().parents[1] / "configs/sim_illustrative.json"
R1, R2 = (100, 145), (155, 255)            # level bands inside one regime each (illustrative circuit)
EDGE = (70, 120)                            # straddles the strike threshold (level ≈ 95): R0 below, R1 above
LAMP_OFF = {"V_b": 1e6}                     # lamp removed: never strikes
RESISTOR = {"V_b": 1e-3, "V_m": 0.0, "I_x": 0.0}  # always conducting linear r_on: linear control
CONDITIONS = {   # name: (level band, lamp model, config overrides)
    "R2 lamp": (R2, "iid", {}),
    "R1 lamp": (R1, "iid", {}),
    "R1 afterglow (hyp.)": (R1, "afterglow", {}),
    "R1 lamp + 1 nF": (R1, "iid", {"C_s": 1e-9}),
    "Linear resistor": (R2, "none", RESISTOR),
    "Open circuit": (R2, "none", LAMP_OFF),
    "R0/R1 edge lamp": (EDGE, "iid", {}),
}
BASE = {"T": 20e-6, "M": 4, "steps": 1000}


def make(overrides):
    return Config(CONFIG).with_values(**overrides)


def lamp(kind, cfg):
    if kind == "none":
        return iid_delay(0.0, 0.0)
    if kind == "afterglow":
        return afterglow_delay(1e-6, 10e-6, 100e-6, 8.0)   # hypothetical: memory spans ~5 steps of 20 µs
    return iid_delay(cfg.get("lamp", "t_f"), cfg.get("lamp", "t_s"))


def states(cfg, levels, kind, seed, p, **kw):
    """Sub-window means of v and v_S (READ-01, plasma_rc.states)."""
    tr = simulate(cfg, levels / 255, p["T"], p["M"] * FINE, lamp(kind, cfg), seed, **kw)
    return sim_states(tr, p["M"]), tr


def flash_counts(tr, n, p):
    """Ablation (nonlinear summary feature): strikes per sub-window."""
    edges = np.arange(n * p["M"] + 1) * p["T"] / p["M"]
    return np.histogram(tr.flashes, edges)[0].reshape(n, p["M"]).astype(float)


def task_main(name, seed, p, extra=None, full=True):
    band, kind, ov = CONDITIONS[name]
    cfg = make({**ov, **(extra or {})})
    levels, u = held_input(p["steps"], seed, lo=band[0], hi=band[1])
    X, tr = states(cfg, levels, kind, seed, p, rtol=p.get("rtol", 1e-8))
    sp = A.splits(len(u))
    out = {"flashes_per_step": tr.flashes.size / len(u), **B.held(X, u, sp, seed, 8 if full else 4)}
    if full:
        prefix, _ = held_input(200, seed + 1000, lo=band[0], hi=band[1])
        X2, _ = states(cfg, np.concatenate([prefix, levels]), kind, seed + 1000, p)
        w = sp[0][0]
        out["consistency"] = A.consistency(X[w:], X2[len(prefix) + w:])
        t_lamp = (0.0, 0.0) if kind == "none" else (None, None)   # surrogate: memoryless version of the lamp
        sur = surrogate_states(cfg, levels / 255, p["T"], p["M"], seed + 2000, 6, *t_lamp)
        out["attribution"] = A.attribution(X, sur, u, sp, taps=5)
        F = flash_counts(tr, len(u), p)
        if F.any():
            f = B.held(F, u, sp, seed, 4, orders=(10,))
            out["ablation_flash_counts"] = {"narma10": f["narma"][10], "mc": f["mc"], "ipc2": f["ipc2"]}
    return out


def task_binary(name, seed, p):
    band, kind, ov = CONDITIONS[name]
    levels, b = binary_input(p["steps"], seed, *band)
    X, _ = states(make(ov), levels, kind, seed, p)
    return B.binary(X, b, A.splits(len(b)))


def task_rank(name, seed, p, n_seq=40, length=20, keep=3):
    band, kind, ov = CONDITIONS[name]
    cfg = make(ov)
    kern, gen = rank_levels(n_seq, length, *band, seed)
    final = lambda lv, s: states(cfg, lv, kind, s, p)[0][-keep:].ravel()  # noqa: E731
    return B.rank([final(lv, seed * 100 + i) for i, lv in enumerate(kern)],
                  [final(lv, seed * 100 + i) for i, lv in enumerate(gen)])


def task_lyap(name, seed, p):
    band, kind, ov = CONDITIONS[name]
    cfg = make(ov)
    levels, _ = held_input(200, seed, lo=band[0], hi=band[1])
    a = simulate(cfg, levels / 255, p["T"], p["M"], lamp(kind, cfg), seed, v0=0.0)
    b = simulate(cfg, levels / 255, p["T"], p["M"], lamp(kind, cfg), seed, v0=1.0)
    d = np.abs(a.v - b.v).max(1)               # per-step max distance; same input, same delay seed
    below = d < 1e-6
    conv = next((k for k in range(len(d)) if below[k:].all()), None)
    post = slice(2, conv if conv else len(d))  # skip the start-up transient (strike-time differences)
    t = a.t[:, -1]
    fit = B.divergence_exponent(t[post], d[post]) if d[post].size >= 5 and (d[post] > 0).all() else None
    return {"converged_step": conv, "exponent_per_s": fit, "dist_v": d.tolist(),
            "flash_count_diff": int(abs(a.flashes.size - b.flashes.size))}


def task_baseline(seed, p):
    _, u = held_input(p["steps"], seed, lo=0, hi=255)
    return B.baselines(u, A.splits(len(u)))


def jobs():
    seeds = range(5)
    for name in CONDITIONS:
        for s in seeds:
            yield ("main", name, s), (task_main, (name, s, BASE))
            yield ("binary", name, s), (task_binary, (name, s, BASE))
            yield ("rank", name, s), (task_rank, (name, s, BASE))
            yield ("lyap", name, s), (task_lyap, (name, s, BASE))
    for s in seeds:
        yield ("baseline", "", s), (task_baseline, (s, BASE))
        short = {**BASE, "steps": 600}
        for T in (5e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6):
            for name in ("R2 lamp", "R1 lamp", "R1 afterglow (hyp.)"):
                yield ("sweep_T", f"{name}|{T}", s), (task_main, (name, s, {**short, "T": T}, None, False))
        for tau in (0.0, 1e-6, 5e-6, 20e-6):
            yield ("sweep_tau", f"R2 lamp|{tau}", s), (task_main, ("R2 lamp", s, short, {"tau_drv": tau}, False))
        for cs in (10e-12, 100e-12, 1e-9, 10e-9):
            yield ("sweep_C", f"R1 lamp|{cs}", s), (task_main, ("R1 lamp", s, short, {"C_s": cs}, False))
        for ts in (0.0, 1e-6, 5e-6):
            yield ("sweep_ts", f"R1 lamp|{ts}", s), (task_main, ("R1 lamp", s, short, {"t_s": ts}, False))
        for m in (1, 2, 4, 8):
            yield ("sweep_M", f"R1 afterglow (hyp.)|{m}", s), (task_main, ("R1 afterglow (hyp.)", s,
                                                                         {**short, "M": m}, None, False))
    for rtol in (1e-8, 1e-10):
        yield ("tolerance", f"R1 lamp|{rtol}", 0), (task_main, ("R1 lamp", 0, {**BASE, "rtol": rtol}, None, False))


def _call(item):
    key, (fn, args) = item
    try:
        return key, fn(*args)
    except Exception as exc:  # recorded, never silently dropped
        return key, {"error": repr(exc)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out", type=Path)
    p.add_argument("--workers", type=int, default=20)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    with ProcessPoolExecutor(args.workers) as pool:
        results = [{"kind": k[0], "name": k[1], "seed": k[2], "result": r} for k, r in pool.map(_call, jobs())]
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (args.out / "results.json").write_text(json.dumps(
        {"git_head": head, "config": str(CONFIG), "base": BASE, "conditions": {k: [list(v[0]), v[1], v[2]]
         for k, v in CONDITIONS.items()}, "label": "simulation (SIM-01): not lamp evidence", "results": results},
        indent=1, default=float))
    print(f"{len(results)} tasks, {sum('error' in r['result'] for r in results)} errors")


if __name__ == "__main__":
    main()
