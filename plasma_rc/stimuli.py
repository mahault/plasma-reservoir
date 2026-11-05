"""Stimuli as DAC level segments: an (n, 2) int array of [level, ticks], played exactly by the firmware.

The host generates and logs every level, so the applied (quantized) sequence is known exactly
(research doc §7, E1/E2/E4). Normalized drive x = level / (n_levels - 1); NARMA input u = x / 2.
"""
import numpy as np


def held_input(n_steps, seed, n_levels=256, lo=0, hi=None):
    """Uniform random held levels in [lo, hi] (one regime, REGIME-01) and the exact NARMA input
    u = 0.5·(level - lo)/(hi - lo) in [0, 0.5]."""
    hi = n_levels - 1 if hi is None else hi
    levels = np.random.default_rng(seed).integers(lo, hi + 1, n_steps)
    return levels, 0.5 * (levels - lo) / (hi - lo)


def binary_input(n_steps, seed, lo, hi, margin=5):
    """Random bits b[k] as levels just inside the band edges: lo + margin (0) or hi - margin (1)."""
    b = np.random.default_rng(seed).integers(0, 2, n_steps)
    return np.where(b, hi - margin, lo + margin), b


def rank_levels(n_seq, length, lo, hi, seed, jitter=3):
    """Kernel set: n_seq random sequences; generalization set: n_seq copies of one base sequence with
    ±jitter-level noise (Legenstein & Maass 2007). Returns (kernel, gen), each (n_seq, length)."""
    rng = np.random.default_rng(seed)
    base = rng.integers(lo, hi + 1, length)
    kernel = np.array([rng.integers(lo, hi + 1, length) for _ in range(n_seq)])
    gen = np.array([np.clip(base + rng.integers(-jitter, jitter + 1, length), lo, hi) for _ in range(n_seq)])
    return kernel, gen


def steps(levels, ticks_per_step):
    return np.column_stack([levels, np.full(len(levels), ticks_per_step)]).astype(np.int64)


def ramp(lo, hi, ticks_per_level):
    """Slow up-down staircase for static characterization (E1: V_b on the way up, V_x on the way down)."""
    up = np.arange(lo, hi + 1)
    return steps(np.concatenate([up, up[-2::-1]]), ticks_per_level)


def pulse_pairs(rest_ticks, cond, test, base, sham, pulse_ticks, settle_ticks, repeats, seed):
    """E2 'different past, same present': settle, conditioning pulse (or sub-breakdown sham), rest,
    identical test pulse. Trials are shuffled; returns segments and one record per trial."""
    order = [(r, s) for r in rest_ticks for s in (False, True) for _ in range(repeats)]
    order = [order[i] for i in np.random.default_rng(seed).permutation(len(order))]
    seg, trials, tick = [], [], 0
    for rest, is_sham in order:
        for level, ticks in ((base, settle_ticks), (sham if is_sham else cond, pulse_ticks), (base, rest)):
            seg.append((level, ticks))
            tick += ticks
        trials.append({"rest_ticks": int(rest), "sham": is_sham, "test_segment": len(seg),
                       "test_onset_tick": tick})
        seg.append((test, pulse_ticks))
        tick += pulse_ticks
    seg.append((base, settle_ticks))
    return np.asarray(seg, dtype=np.int64), trials
