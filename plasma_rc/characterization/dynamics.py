"""Replica dynamics: λ_c from replica divergence and flash-time reliability (D-34).

Replicas = repeats of one common drive, each after a different random prefix.
λ_c here is an **untested hypothesis** (audit A13): no peer-reviewed experimental estimator was
found; we take the slope of the mean log-distance between replicas while it stays above twice
the silence floor (cf. the conditional Lyapunov exponent of Uchida et al., PRE 78:036203, 2008).
Flash reliability follows the repeated-frozen-input idea of Mainen & Sejnowski, Science
268:1503 (1995); matching each flash of the first repeat to an unused nearest flash of the others is
our simplification (Inferred).
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

MIN_POINTS = 5


def lambda_c(traces: np.ndarray, dt: float, floor: float) -> dict:
    """traces: (replicas, T, features) over the common segment; floor: silence-replica distance."""
    if len(traces) < 2 or dt <= 0 or not np.isfinite(dt) or not np.isfinite(floor) or floor < 0:
        raise ValueError("need at least two replicas, positive dt and nonnegative finite floor")
    pairs = list(combinations(range(len(traces)), 2))
    dist = np.stack([np.linalg.norm(traces[i] - traces[j], axis=1) for i, j in pairs])
    mean_log = np.mean(np.log(np.maximum(dist, 1e-300)), axis=0)
    above = mean_log > np.log(max(2 * floor, np.finfo(float).tiny))
    n = len(above) if above.all() else int(np.argmin(above))
    if n < MIN_POINTS:
        return {"lambda": float("nan"), "n_points": n, "reason": "replicas not above 2x the silence floor"}
    t = np.arange(n) * dt
    return {"lambda": float(np.polyfit(t, mean_log[:n], 1)[0]), "n_points": n, "reason": ""}


def flash_reliability(times_per_repeat: list[np.ndarray], window_s: float) -> dict:
    """Fraction of first-repeat flashes found in every other repeat within window_s, and
    the spread (std across repeats) of each matched flash time."""
    # Greedy reference-order nearest matching; consume hits only for complete groups.
    ref, others = np.asarray(times_per_repeat[0]), [np.asarray(t) for t in times_per_repeat[1:]]
    if len(times_per_repeat) < 2 or not np.isfinite(window_s) or window_s < 0:
        raise ValueError("need at least two repeats and a finite nonnegative window")
    available = [list(o) for o in others]
    sigmas = []
    for t in ref:
        indices = [int(np.argmin(np.abs(np.asarray(o) - t))) if o else None for o in available]
        hits = [o[i] for o,i in zip(available,indices) if i is not None]
        if len(hits) == len(others) and all(abs(h - t) <= window_s for h in hits):
            sigmas.append(np.std([t, *hits], ddof=1))
            for o,i in zip(available,indices):
                del o[i]
    return {
        "n_ref": len(ref),
        "matched_fraction": len(sigmas) / len(ref) if len(ref) else float("nan"),
        "median_sigma_s": float(np.median(sigmas)) if sigmas else float("nan"),
    }
