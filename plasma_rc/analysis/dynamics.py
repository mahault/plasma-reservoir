"""Repeated-input consistency and finite-time contraction diagnostics."""

from itertools import combinations
import numpy as np
from plasma_rc.trials.storage import load_trial
from plasma_rc.characterization.consistency import pairwise_consistency
from plasma_rc.characterization.dynamics import flash_reliability, lambda_c
from plasma_rc.characterization.features import step_features

N_ANALOG = 3  # step_features columns 0..2: light, i_b, v


def common_segment(
    row: dict, allow_legacy=False
) -> tuple[np.ndarray, np.ndarray, float]:
    """(steps x features) over the common drive, flash times from its start [s], step length [s]."""
    cap = load_trial(row["raw_file"])
    cap.require_integrity(allow_legacy)
    tps, n, n_p = int(row["ticks_per_step"]), int(row["n_steps"]), int(row["n_prefix"])
    x = step_features(cap, tps, n_p + n)[n_p:]
    t0 = n_p * tps / cap.tick_hz
    t = cap.flash_times_s() - t0
    return x, t[(t >= 0) & (t < n * tps / cap.tick_hz)], tps / cap.tick_hz


def analyse(
    reps: list[dict], silence: list[dict], window_s: float | None, allow_legacy=False
) -> dict:
    if len(reps) < 2 or len(silence) < 2:
        raise ValueError("need at least two replicas and two silence repeats")
    signatures = []
    conditions = []
    drives = []
    for r in [*reps, *silence]:
        c = load_trial(r["raw_file"])
        conditions.append(
            (
                c.source,
                *(
                    r.get(k, "")
                    for k in ("bulb_id", "regime", "control", "jumpers", "V_s_measured")
                ),
            )
        )
        if r in reps:
            with np.load(r["raw_file"]) as data:
                if "levels" not in data:
                    raise ValueError("missing common drive in replica record")
                start, n = int(r["n_prefix"]), int(r["n_steps"])
                common = data["levels"][start : start + n]
                if len(common) != n:
                    raise ValueError("incomplete common drive")
                drives.append(common.copy())
        signatures.append(
            (
                int(r["ticks_per_step"]),
                int(r["n_steps"]),
                c.clock_hz,
                c.ocr1a,
                c.channels,
                c.adc_bits,
                c.v_ref,
            )
        )
    if any(c != conditions[0] for c in conditions):
        raise ValueError("incompatible conditions or provenance across replicas")
    if any(not np.array_equal(d, drives[0]) for d in drives[1:]):
        raise ValueError("replicas must share the same recorded common drive")
    if any(s != signatures[0] for s in signatures):
        raise ValueError("incompatible timing or calibration across replicas")
    segs = [common_segment(r, allow_legacy) for r in reps]
    sil = [common_segment(r, allow_legacy)[0] for r in silence]
    x = np.stack([s[0] for s in segs])
    mu, sd = x.reshape(-1, x.shape[2]).mean(0), x.reshape(-1, x.shape[2]).std(0)
    sd = np.where(sd > 0, sd, 1.0)
    xs, ss = (x - mu) / sd, (np.stack(sil) - mu) / sd
    live = x.reshape(-1, x.shape[2]).std(0) > 0
    c = float(
        np.mean([pairwise_consistency(xs[:, :, k]) for k in np.flatnonzero(live)])
    )
    xa, sa = xs[:, :, :N_ANALOG], ss[:, :, :N_ANALOG]
    floor = float(
        np.median(
            [
                np.linalg.norm(sa[i] - sa[j], axis=1).mean()
                for i, j in combinations(range(len(sa)), 2)
            ]
        )
    )
    step_s = segs[0][2]
    lam = lambda_c(xa, step_s, floor)
    rel = flash_reliability(
        [s[1] for s in segs], step_s / 2 if window_s is None else window_s
    )
    r0 = reps[0]
    return {
        "bulb_id": r0["bulb_id"],
        "regime": r0["regime"],
        "replicas": len(reps),
        "consistency_C": c,
        "silence_floor": floor,
        "lambda_c_per_s": lam["lambda"],
        "lambda_points": lam["n_points"],
        "lambda_note": "finite-time diagnostic; " + lam["reason"],
        "flash_matched_fraction": rel["matched_fraction"],
        "flash_median_sigma_s": rel["median_sigma_s"],
        "n_flashes_ref": rel["n_ref"],
    }
