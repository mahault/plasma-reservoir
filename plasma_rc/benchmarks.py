"""Extra benchmarks for the method-validation study (docs/study_2026-11-04.md).

- NARMA-n: the NARMA-10 recursion (Atiya & Parlos 2000) with order n. Inferred generalization; the published
  "NARMA2" second-order system has a different form.
- Delayed XOR / parity of binary inputs: needs nonlinearity and memory together; perfect balanced XOR cannot be represented by a linear decision boundary on the raw bits.
  Above-chance classification alone is not evidence of nonlinear reservoir processing.
- Numerical rank of a state matrix: kernel quality and generalization rank (Legenstein & Maass 2007,
  Neural Networks 20, 323).
- Divergence exponent: slope of log twin-trajectory distance under identical input and noise (a conditional
  Lyapunov exponent estimate; consistency literature: Uchida et al. 2004, PRL 93, 244102).
"""
import numpy as np

from plasma_rc import analysis as A
from plasma_rc.analysis import ALPHAS, _predict

NARMA_ORDERS = (2, 5, 10)
XOR_DELAYS = ((0, 1), (1, 2), (1, 2, 3))


def held(X, u, sp, seed, max_delay, orders=NARMA_ORDERS):
    """Battery for a held random-input recording: NARMA-n (state X[k] predicts y[k+1]) and positive-delay
    capacities. Returns narma {n: test NMSE}, mc [C(1..max_delay)], ipc2 (sum of degree-2), quadratic, threshold."""
    caps = A.capacities(X, u, sp, max_delay, seed)
    return {"narma": {n: A.score(X[:-1], narma_target(u, n)[1:], sp)[0] for n in orders},
            "mc": [caps["linear"][d] for d in range(1, max_delay + 1)],
            "ipc2": sum(caps["quadratic"].values()),
            "quadratic": {f"{i},{j}": c for (i, j), c in caps["quadratic"].items()},
            "threshold": caps["threshold"]}


def baselines(u, sp, orders=NARMA_ORDERS):
    """N-B task baselines on the true input: input only, linear and quadratic 10-step history."""
    feats = {"input only": A.history(u, 1), "linear history (10)": A.history(u, 10),
             "quadratic history (10)": A.history(u, 10, quadratic=True)}
    return {k: {n: A.score(X[:-1], narma_target(u, n)[1:], sp)[0] for n in orders} for k, X in feats.items()}


def binary(X, b, sp, delays=XOR_DELAYS):
    """Battery for a binary-input recording: accuracy on XOR/parity of b[k-d] (linear ceiling 0.75 for 2 bits)."""
    return {f"xor{d}": accuracy(X, parity(b, d), sp) for d in delays}


def rank(kernel, gen):
    """Kernel and generalization rank of final states (rows = input sequences), centered and scaled on the
    kernel set: a DC offset is not a computational dimension (Legenstein & Maass 2007)."""
    kernel, gen = np.asarray(kernel, float), np.asarray(gen, float)
    mu, scale = kernel.mean(0), kernel.std(0)
    scale[scale == 0] = 1
    return {"kernel_rank": numerical_rank((kernel - mu) / scale),
            "generalization_rank": numerical_rank((gen - mu) / scale), "dims": int(kernel.shape[1])}


def narma_target(u, order):
    y = np.zeros(len(u))
    for t in range(order, len(u)):
        y[t] = (0.3 * y[t - 1] + 0.05 * y[t - 1] * y[t - order:t].sum()
                + 1.5 * u[t - 1] * u[t - order] + 0.1)
    return y


def parity(b, delays):
    """XOR over b[k - d] for d in delays (zeros before the start)."""
    out = np.zeros(len(b), dtype=int)
    for d in delays:
        out ^= np.concatenate([np.zeros(d), b[:len(b) - d]]).astype(int)
    return out.astype(float)


def accuracy(X, z, sp):
    """Ridge readout thresholded at 0.5; alpha chosen on validation accuracy, scored once on test."""
    tr, va, te = sp
    acc = lambda fit, ev, a: float(np.mean((_predict(X, z, fit, ev, a) > 0.5) == (z[ev[0]:ev[1]] > 0.5)))  # noqa
    alpha = max(ALPHAS, key=lambda a: acc(tr, va, a))
    return acc((tr[0], va[1]), te, alpha)


def numerical_rank(S, rel=1e-2):
    """Number of singular values above rel x the largest."""
    s = np.linalg.svd(np.asarray(S, float), compute_uv=False)
    return int(np.sum(s > rel * s[0])) if s.size and s[0] > 0 else 0


def divergence_exponent(t, dist, floor_ratio=1e-6):
    """Least-squares slope of ln(distance) vs time while the distance is above floor_ratio x its start [1/s]."""
    t, dist = np.asarray(t, float), np.asarray(dist, float)
    keep = dist > floor_ratio * dist[0]
    return float(np.polyfit(t[keep], np.log(dist[keep]), 1)[0])
