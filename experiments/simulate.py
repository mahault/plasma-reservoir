"""Simulation pipeline (SIM-01): circuit regimes, safety bounds and E2 pulse pairs.
E4 random-input benchmarks run through the method-validation study (experiments/study.py).

Outputs check the circuit and the analysis; they are never evidence of intrinsic lamp memory.
    python -m experiments.simulate CONFIG OUT regimes
    python -m experiments.simulate CONFIG OUT e2 --base 0 --cond 255 --test 200 --sham 100 [--hypothetical-memory TAU]
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from plasma_rc import analysis as A
from plasma_rc.circuit import Config
from plasma_rc.sim import iid_delay, rest_dependent_delay, simulate
from plasma_rc.stimuli import pulse_pairs


def lamp_delay(cfg, memory_tau):
    t_f, t_s = cfg.get("lamp", "t_f"), cfg.get("lamp", "t_s")
    return rest_dependent_delay(t_f, t_s, memory_tau) if memory_tau else iid_delay(t_f, t_s)


def regimes(cfg, args):
    grid = [{"level": lv, "v_d": cfg.drive(lv / 255), "regime": cfg.regime(cfg.drive(lv / 255))}
            for lv in range(0, 256, 5)]
    return {"grid": grid, "safety": cfg.safety()}


def e2(cfg, args):
    seg, trials = pulse_pairs(args.rests, args.cond, args.test, args.base, args.sham, args.pulse_ticks,
                              args.settle_ticks, args.repeats, args.seed)
    tr = simulate(cfg, seg[:, 0] / 255, seg[:, 1] * args.tick, 8, lamp_delay(cfg, args.hypothetical_memory),
                  args.seed)
    onsets = np.array([t["test_onset_tick"] for t in trials]) * args.tick
    d = A.strike_delays(tr.flashes, onsets, args.pulse_ticks * args.tick)
    pre_v = [tr.v[t["test_segment"] - 1, -1] for t in trials]  # last sample of the rest segment
    return {"trials": trials, "delays_s": d.tolist(),
            "summary": A.memory_effect(d, [t["rest_ticks"] for t in trials], [t["sham"] for t in trials], pre_v)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("config", type=Path)
    p.add_argument("out", type=Path, help="new directory")
    p.add_argument("stage", choices=("regimes", "e2"))
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--tick", type=float, default=1e-6, help="seconds per tick")
    p.add_argument("--hypothetical-memory", type=float, default=0.0,
                   help="TEST ONLY: rest-dependent delay with this time constant [s]")
    p.add_argument("--base", type=int, default=0)
    p.add_argument("--cond", type=int, default=255)
    p.add_argument("--test", type=int, default=200)
    p.add_argument("--sham", type=int, default=100)
    p.add_argument("--rests", type=int, nargs="+", default=[2, 20, 200, 2000])
    p.add_argument("--pulse-ticks", type=int, default=100)
    p.add_argument("--settle-ticks", type=int, default=5000)
    p.add_argument("--repeats", type=int, default=8)
    args = p.parse_args()
    cfg = Config(args.config)
    result = {"regimes": regimes, "e2": e2}[args.stage](cfg, args)
    args.out.mkdir(parents=True, exist_ok=False)
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (args.out / "result.json").write_text(json.dumps(
        {"stage": args.stage, "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
         "git_head": head, "config": cfg.raw, "label": "simulation: circuit/analysis check, not lamp evidence",
         "result": result}, indent=2, default=float))
    print(json.dumps(result if args.stage != "e2" else result["summary"], indent=2, default=float)[:3000])


if __name__ == "__main__":
    main()
