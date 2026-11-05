"""Analyze physical recordings with the shared analysis (research doc §6–7).
    python -m experiments.analyze e0 REC.npz --step-ticks 50      # per-channel step residual ε (ATTR-01)
    python -m experiments.analyze e1 REC.npz --lit-current 2e-5   # V_b bracket, lit-branch fit, I_x bound
    python -m experiments.analyze e2 REC.npz                      # strike delay vs rest, real vs sham, settling
    python -m experiments.analyze e4 REC.npz [--repeat REC2.npz]  # battery for the recording's --stimulus:
        held/prefix: capacities, NARMA-2/5/10 vs N-B, attribution vs N-A, READ-02 strike timing;
        binary: delayed XOR/parity; rank: kernel vs generalization rank; --repeat: consistency of the suffix
Values printed here are measurement candidates: the operator copies them into the config tagged "measured".
"""
import argparse
import json

import numpy as np

from plasma_rc import analysis as A
from plasma_rc import benchmarks as B
from plasma_rc.hw.recording import CHANNELS, load, segment_states
from plasma_rc.states import strike_latency
from plasma_rc.surrogate import surrogate_states


def _starts(seg):
    return np.concatenate([[0], np.cumsum(seg[:, 1])])


def e0(cap, cfg, seg, meta, args):
    """ε_j = |y(t0 + T) - y(∞)| / |y(∞) - y(t0)| per channel and step (raw ADC codes; gain-free)."""
    s, out = _starts(seg), {}
    for name, pin in CHANNELS.items():
        if pin not in cap.channels:
            continue
        ticks, codes = cap.channel(pin)
        tail = lambda i: codes[(ticks >= s[i + 1] - (s[i + 1] - s[i]) // 10) & (ticks < s[i + 1])].mean()  # noqa
        eps = []
        for i in range(1, len(seg)):
            y_inf, y0 = tail(i), tail(i - 1)
            near = codes[(ticks >= s[i] + args.step_ticks - len(cap.channels)) & (ticks < s[i] + args.step_ticks)]
            if near.size and abs(y_inf - y0) > 0:
                eps.append(float(abs(near.mean() - y_inf) / abs(y_inf - y0)))
        out[name] = {"epsilon_per_step": eps, "epsilon_max": max(eps) if eps else None}
    return out


def e1(cap, cfg, seg, meta, args):
    x, names = segment_states(cap, seg, cfg, samples=1)
    v, v_s = x[:, 0, names.index("v")], x[:, 0, names.index("v_s")]
    i_l = v_s / cfg.get("circuit", "R_S")
    s, t = _starts(seg) / cap.tick_hz, cap.flash_times_s()
    flashes = np.array([((t >= s[i]) & (t < s[i + 1])).sum() for i in range(len(seg))])
    lit = i_l > args.lit_current
    up = np.arange(len(seg)) <= int(np.argmax(seg[:, 0]))
    events = np.flatnonzero(up & ((flashes > 0) | lit))
    first = int(events[0]) if events.size else None
    fit = np.polyfit(i_l[lit], (v - v_s)[lit], 1) if lit.sum() >= 3 else None  # lamp voltage v_L = v - v_S
    down_lit = lit & ~up
    return {"V_b_bracket_v": None,  # post-strike segment means do not bracket pre-strike voltage
            "first_discharge_segment": first,
            "breakdown_status": "no_discharge_detected" if first is None else "requires_pre_strike_waveform",
            "lit_fit": None if fit is None else {"r_on_ohm": float(fit[0]), "V_m_v": float(fit[1]),
                                                 "points": int(lit.sum())},
            "I_x_upper_bound_a": float(i_l[down_lit].min()) if down_lit.any() else None,
            "flashes_per_segment": flashes.tolist()}


def e2(cap, cfg, seg, meta, args):
    trials = meta["trials"]
    onsets = np.array([t["test_onset_tick"] for t in trials]) / cap.tick_hz
    window = seg[trials[0]["test_segment"], 1] / cap.tick_hz
    d = A.strike_delays(cap.flash_times_s(), onsets, window)
    x, names = segment_states(cap, seg, cfg, samples=8)
    pre_v = [x[t["test_segment"] - 1, -1, names.index("v")] for t in trials]
    return {"delays_s": d.tolist(), "summary": A.memory_effect(
        d, [t["rest_ticks"] for t in trials], [t["sham"] for t in trials], pre_v)}


def _states(cap, cfg, seg, samples, wanted):
    x, names = segment_states(cap, seg, cfg, samples)
    return np.column_stack([x[:, :, names.index(n)] for n in wanted if n in names])


def check_repeat(cap, suffix, cap2, suffix2):
    """A repeated command must have identical physical timing and recorded channel identity."""
    if cap.tick_hz != cap2.tick_hz or cap.channels != cap2.channels:
        raise ValueError("repeat recording has different timing or channels")
    if not np.array_equal(suffix, suffix2):
        raise ValueError("repeat recording has a different suffix waveform")


def e4(cap, cfg, seg, meta, args):
    stim = meta.get("stimulus", "held")
    X = _states(cap, cfg, seg, args.samples, ("v", "v_s", "light"))  # drive monitor is diagnostic only
    if stim == "binary":
        b = np.asarray(meta["bits"])
        return {"binary": B.binary(X, b, A.splits(len(b)))}
    if stim == "rank":
        r = meta["rank"]
        final = [X[s + r["length"] - r["keep"]:s + r["length"]].ravel() for s in r["starts"]]
        pick = lambda g: [f for f, grp in zip(final, r["groups"]) if grp == g]  # noqa: E731
        return {"rank": B.rank(pick("kernel"), pick("gen"))}
    p0 = meta.get("prefix_steps", 0)
    u, X = np.asarray(meta["u"]), X[p0:]
    sp = A.splits(len(u))
    result = {"held": B.held(X, u, sp, args.seed, args.max_delay), "baselines": B.baselines(u, sp)}
    # READ-02: strike timing, a separate feature set (never mixed with the window means)
    edges_s = np.concatenate([[0], np.cumsum(seg[:, 1])]) / cap.tick_hz
    result["read02_strike_timing"] = B.held(strike_latency(cap.flash_times_s(), edges_s)[p0:], u, sp, args.seed,
                                            args.max_delay)
    # N-A: mean over delay realizations, read out like the lamp. ponytail: E0 sensor poles not yet in it (before E5)
    sur = surrogate_states(cfg, seg[:, 0] / 255, seg[:, 1] / cap.tick_hz, args.samples, args.seed)[p0:]
    result["attribution"] = A.attribution(_states(cap, cfg, seg, args.samples, ("v", "v_s"))[p0:], sur, u, sp,
                                          args.max_delay)
    if args.repeat:  # same suffix after the same (held) or a different (prefix) past
        cap2, cfg2, seg2, meta2 = load(args.repeat)
        p2 = meta2.get("prefix_steps", 0)
        check_repeat(cap, seg[p0:], cap2, seg2[p2:])
        X2 = _states(cap2, cfg2, seg2, args.samples, ("v", "v_s", "light"))[p2:]
        w = sp[0][0]
        result["consistency"] = A.consistency(X[w:], X2[w:])
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stage", choices=("e0", "e1", "e2", "e4"))
    p.add_argument("recording")
    p.add_argument("--step-ticks", type=int, default=50)
    p.add_argument("--lit-current", type=float, help="A; lit threshold above the measured dark noise (E1)")
    p.add_argument("--samples", type=int, default=4)
    p.add_argument("--max-delay", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--repeat")
    args = p.parse_args()
    if args.stage == "e1" and args.lit_current is None:
        p.error("e1 needs --lit-current from the measured dark noise")
    cap, cfg, seg, meta = load(args.recording)
    if meta["stage"] != args.stage:
        raise SystemExit(f"recording is stage {meta['stage']}, not {args.stage}")
    print(json.dumps({"recording": args.recording, "bulb_id": meta["args"]["bulb_id"],
                      "result": {"e0": e0, "e1": e1, "e2": e2, "e4": e4}[args.stage](cap, cfg, seg, meta, args)},
                     indent=2, default=float))


if __name__ == "__main__":
    main()
