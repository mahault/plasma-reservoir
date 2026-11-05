"""Hardware acquisition for stages E0, E1, E2, E4 (research doc §7) on the Teensy 4.1 (firmware/ne2h).

Software checks are not interlocks. Before any lamp stage the operator must have verified the HV driver
current limit, resistor ratings, clamps, probe ratings and the discharge path (research doc §4.5).
    python -m experiments.acquire PORT CONFIG OUT.npz e0 --levels 0 255 0 --hold 2000 --bulb-id dummy-R1 ...
    python -m experiments.acquire PORT CONFIG OUT.npz e1 --lo 0 --hi 255 --hold 2000 --bulb-id B01 ...
    python -m experiments.acquire PORT CONFIG OUT.npz e2 --base 0 --cond 255 --test 200 --sham 80 --bulb-id B01 ...
    python -m experiments.acquire PORT CONFIG OUT.npz e4 --lo LO --hi HI --steps 600 --step-ticks 50 --bulb-id B01 ...
        [--stimulus held|binary|rank|prefix]   # battery stimuli (docs/hardware_runbook.md §7)
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from plasma_rc.circuit import Config
from plasma_rc.hw.link import open_board
from plasma_rc.hw.recording import save
from plasma_rc.stimuli import binary_input, held_input, pulse_pairs, ramp, rank_levels, steps


def waveform(args):
    """Segments plus the stage record needed to analyze them (trials or exact input)."""
    if args.stage == "e0":
        return steps(np.array(args.levels), args.hold), {}
    if args.stage == "e1":
        return ramp(args.lo, args.hi, args.hold), {}
    if args.stage == "e2":
        seg, trials = pulse_pairs(args.rests, args.cond, args.test, args.base, args.sham, args.pulse_ticks,
                                  args.settle_ticks, args.repeats, args.seed)
        return seg, {"trials": trials}
    return e4_waveform(args)


def e4_waveform(args):
    """E4 battery stimuli. held: random levels (MC/IPC, NARMA); binary: bits at the band edges (XOR);
    rank: kernel and generalization sequences, each after a settle at --base (R0); prefix: a random prefix
    (--prefix-seed) before the held sequence, for the different-prefix repeat test."""
    rec = {"stimulus": args.stimulus, "lo": args.lo, "hi": args.hi}
    if args.stimulus == "binary":
        levels, b = binary_input(args.steps, args.seed, args.lo, args.hi)
        return steps(levels, args.step_ticks), {**rec, "bits": b.tolist()}
    if args.stimulus == "rank":
        if args.seq_len < 3:
            raise ValueError("rank sequences need at least 3 steps for the readout")
        kern, gen = rank_levels(args.n_seq, args.seq_len, args.lo, args.hi, args.seed)
        seg, starts = [], []
        for lv in (*kern, *gen):
            seg.append((args.base, args.settle_ticks))
            starts.append(len(seg))
            seg += [(int(x), args.step_ticks) for x in lv]
        groups = ["kernel"] * len(kern) + ["gen"] * len(gen)
        return np.asarray(seg, np.int64), {**rec, "rank": {"starts": starts, "length": args.seq_len, "keep": 3,
                                                          "groups": groups}}
    levels, u = held_input(args.steps, args.seed, lo=args.lo, hi=args.hi)
    prefix = held_input(args.prefix_steps, args.prefix_seed, lo=args.lo, hi=args.hi)[0] \
        if args.stimulus == "prefix" else np.array([], int)
    return steps(np.concatenate([prefix, levels]), args.step_ticks), {**rec, "u": u.tolist(),
                                                                       "prefix_steps": len(prefix)}


def check_safety(cfg, stage):
    """E0 runs on dummy loads; lamp stages need the derived continuous-current bound to hold."""
    s = cfg.safety()
    if stage != "e0" and s["continuous_bound_ok"] is not True:
        raise SystemExit(f"refused: continuous-current bound not satisfied or unknown ({s}); fill the config")
    if stage in ("e2", "e4"):
        for name in ("V_b", "V_m", "r_on", "I_x"):
            cfg.get("lamp", name)  # E1 must have measured these first
    return s


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("port")
    p.add_argument("config", type=Path)
    p.add_argument("out", type=Path, help="new .npz recording")
    p.add_argument("stage", choices=("e0", "e1", "e2", "e4"))
    p.add_argument("--bulb-id", required=True, help="lamp ID, or the dummy load ID for E0")
    p.add_argument("--session", required=True)
    p.add_argument("--temperature-c", type=float, required=True)
    p.add_argument("--warmup-s", type=float, required=True)
    p.add_argument("--illumination", required=True, help="e.g. 'dark box, LED off'")
    p.add_argument("--confirm-safety", action="store_true", help="operator verified the §4.5 checklist")
    p.add_argument("--ocr1a", type=int, default=5999, help="tick = ocr1a + 1 CPU cycles")
    p.add_argument("--channels", default="0123")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--levels", type=int, nargs="+", default=[0, 255, 0])
    p.add_argument("--hold", type=int, default=2000)
    p.add_argument("--lo", type=int, default=0)
    p.add_argument("--hi", type=int, default=255)
    p.add_argument("--base", type=int, default=0)
    p.add_argument("--cond", type=int, default=255)
    p.add_argument("--test", type=int, default=200)
    p.add_argument("--sham", type=int, default=80)
    p.add_argument("--rests", type=int, nargs="+", default=[2, 20, 200, 2000])
    p.add_argument("--pulse-ticks", type=int, default=100)
    p.add_argument("--settle-ticks", type=int, default=5000)
    p.add_argument("--repeats", type=int, default=8)
    p.add_argument("--steps", type=int, default=600)
    p.add_argument("--step-ticks", type=int, default=50)
    p.add_argument("--stimulus", choices=("held", "binary", "rank", "prefix"), default="held")
    p.add_argument("--prefix-steps", type=int, default=200)
    p.add_argument("--prefix-seed", type=int, default=1000)
    p.add_argument("--n-seq", type=int, default=40)
    p.add_argument("--seq-len", type=int, default=20)
    args = p.parse_args()
    if not args.confirm_safety:
        raise SystemExit("refused: pass --confirm-safety after checking the §4.5 list")
    if args.out.exists():
        raise SystemExit(f"refused: {args.out} exists")
    cfg = Config(args.config)
    safety = check_safety(cfg, args.stage)
    seg, record = waveform(args)
    board = open_board(args.port)
    try:
        board.configure(args.ocr1a, args.channels)
        board.upload(seg)
        board.start("WAVE")
        time.sleep(seg[:, 1].sum() * (args.ocr1a + 1) / board.clock_hz + 0.5)
        capture = board.stop()
    finally:
        board.close()
    meta = {"stage": args.stage, "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
            "safety_bounds": safety, "started_unix": time.time(), **record}
    save(args.out, capture, cfg.raw, seg, meta)
    print(json.dumps({"saved": str(args.out), "samples": int(capture.ticks.size),
                      "flashes": int(capture.flash_tick.size)}))


if __name__ == "__main__":
    main()
