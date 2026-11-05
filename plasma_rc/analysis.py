"""Analysis shared by simulation and hardware: raw-sample states with a linear ridge readout (READ-01).

Readout target z[k] from state X[k]; features standardized on the fitting rows only; ridge alpha chosen on
validation, refit on train + validation, scored once on test (VALID-01).
Capacities: Dambre et al. (2012), Sci. Rep. 2, 514; positive delays only, normalized Legendre targets of the
scaled input s = 4u - 1 in [-1, 1], zeroed below a shuffled-input threshold.
Task targets and the benchmark battery: plasma_rc.benchmarks.
"""
from itertools import combinations_with_replacement

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge

ALPHAS = (1e-6, 1e-4, 1e-2, 1.0)


def scaled(u):
    return 4 * np.asarray(u, float) - 1


def splits(n, washout=0.1):
    w = max(int(n * washout), 1)
    return (w, n // 2), (n // 2, int(n * 0.7)), (int(n * 0.7), n)


def nmse(z, p):
    return float(np.mean((z - p) ** 2) / np.var(z))


def _predict(X, z, fit, ev, alpha):
    mu, sd = X[fit[0]:fit[1]].mean(0), X[fit[0]:fit[1]].std(0)
    sd[sd == 0] = 1.0
    Xs = (X - mu) / sd
    model = Ridge(alpha=alpha).fit(Xs[fit[0]:fit[1]], z[fit[0]:fit[1]])
    return model.predict(Xs[ev[0]:ev[1]])


def score(X, z, sp):
    """Test NMSE with alpha selected on validation; returns (nmse, alpha)."""
    (tr, va, te) = sp
    alpha = min(ALPHAS, key=lambda a: nmse(z[va[0]:va[1]], _predict(X, z, tr, va, a)))
    return nmse(z[te[0]:te[1]], _predict(X, z, (tr[0], va[1]), te, alpha)), alpha


def _lag(s, d):
    return np.concatenate([np.zeros(d), s[:len(s) - d]])


def history(u, taps, quadratic=False):
    """N-B baselines: s[k..k-taps+1], optionally with all pairwise products (cross-lag included)."""
    lags = np.column_stack([_lag(scaled(u), d) for d in range(taps)])
    if not quadratic:
        return lags
    prods = [lags[:, i] * lags[:, j] for i, j in combinations_with_replacement(range(taps), 2)]
    return np.column_stack([lags] + prods)


def _targets(s, max_delay):
    lin = {d: _lag(s, d) for d in range(1, max_delay + 1)}
    quad = {(i, j): (1.5 * lin[i] ** 2 - 0.5) if i == j else lin[i] * lin[j]
            for i, j in combinations_with_replacement(range(1, max_delay + 1), 2)}
    return lin, quad


def capacities(X, u, sp, max_delay, seed, n_shuffle=10):
    """Positive-delay linear and degree-2 capacities, zeroed below the max capacity found for
    targets built from shuffled inputs (same X, same readout)."""
    cap = lambda z: max(0.0, 1.0 - score(X, z, sp)[0])  # noqa: E731
    rng = np.random.default_rng(seed)
    null = 0.0
    for _ in range(n_shuffle):
        lin, quad = _targets(scaled(rng.permutation(u)), max_delay)
        null = max(null, *(cap(z) for z in (*lin.values(), *quad.values())))
    lin, quad = _targets(scaled(u), max_delay)
    keep = lambda c: c if c > null else 0.0  # noqa: E731
    return {"linear": {d: keep(cap(z)) for d, z in lin.items()},
            "quadratic": {k: keep(cap(z)) for k, z in quad.items()}, "threshold": null}


def consistency(a, b):
    """Repeat agreement per feature: 1 - MSE / mean variance (sees offset and gain) and correlation."""
    a, b = np.atleast_2d(a.T).T, np.atleast_2d(b.T).T
    live = (a.var(0) > 0) & (b.var(0) > 0)   # constant features carry no repeatability information
    a, b = a[:, live], b[:, live]
    mse = ((a - b) ** 2).mean(0)
    return {"nmse_consistency": float(np.mean(1 - mse / (0.5 * (a.var(0) + b.var(0))))),
            "correlation": float(np.mean([np.corrcoef(a[:, i], b[:, i])[0, 1] for i in range(a.shape[1])]))}


def attribution(X_meas, X_sur, u, sp, taps):
    """Exploratory surrogate-discrepancy diagnostic, not a calibrated N-A rejection test: does past input explain the measured state beyond the surrogate prediction and u[k]?
    gain = mean over measured features of NMSE(base) - NMSE(base + u[k-1..k-taps])."""
    s = scaled(u)
    base = np.column_stack([X_sur, s])
    aug = np.column_stack([base] + [_lag(s, d) for d in range(1, taps + 1)])
    live = [j for j in range(X_meas.shape[1]) if X_meas[:, j].var() > 0]  # constant features: nothing to explain
    nb = [score(base, X_meas[:, j], sp)[0] for j in live]
    na = [score(aug, X_meas[:, j], sp)[0] for j in live]
    return {"base_nmse": float(np.mean(nb)), "augmented_nmse": float(np.mean(na)),
            "gain": float(np.mean(nb) - np.mean(na))}


def strike_delays(flashes, onsets, window_s):
    """First strike after each test onset within the window; NaN = no strike (censored, kept)."""
    flashes = np.asarray(flashes)
    out = np.full(len(onsets), np.nan)
    for i, t0 in enumerate(onsets):
        hit = flashes[(flashes >= t0) & (flashes < t0 + window_s)]
        if hit.size:
            out[i] = hit[0] - t0
    return out


def memory_effect(delays, rests, sham, pre_test_v=None):
    """E2 descriptive summary (delay medians/correlation conditional on successful strikes): per rest interval, median delay after real vs sham conditioning, strike fractions and,
    if given, the median node voltage just before the test pulse (settling check: unequal pre-test
    voltages mean the external state, not the gas, may explain a delay difference)."""
    d, r, s = np.asarray(delays), np.asarray(rests), np.asarray(sham, bool)
    v = np.full(len(d), np.nan) if pre_test_v is None else np.asarray(pre_test_v, float)
    real = ~s & np.isfinite(d)
    per = {}
    for rest in np.unique(r):
        dr, ds = d[(r == rest) & ~s], d[(r == rest) & s]
        per[int(rest)] = {"real_median_s": float(np.nanmedian(dr)), "sham_median_s": float(np.nanmedian(ds)),
                          "sham_minus_real_s": float(np.nanmedian(ds) - np.nanmedian(dr)),
                          "real_strike_fraction": float(np.isfinite(dr).mean()),
                          "sham_strike_fraction": float(np.isfinite(ds).mean()),
                          "real_pre_test_v": float(np.median(v[(r == rest) & ~s])),
                          "sham_pre_test_v": float(np.median(v[(r == rest) & s]))}
    return {"delay_summary_scope": "conditional_on_success_not_censoring_adjusted", "spearman_real": float(spearmanr(r[real], d[real]).statistic), "per_rest": per}
