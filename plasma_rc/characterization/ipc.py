"""Information processing capacity (Dambre, Verstraeten, Schrauwen, Massar, Sci. Rep. 2:514, 2012).

Targets are products of normalised Legendre polynomials of past inputs u(k-d), u ~ U[-1, 1]
(Dambre 2012). Capacity of a linear readout (with intercept) of the states:
    C[z] = 1 - min_w <(z - y)^2> / <z^2>.
Finite data bias every capacity upward by ~1/N (Dambre 2012 set small capacities to zero;
Ramachandran & Massar 2026, arXiv:2605.19152 [preprint], derive the 1/N term). We set to zero
every capacity not above the largest capacity reached by the same basis on shuffled input
(no relation to the states), and Richardson-correct the rest: C = 2 C_N - C_{N/2} (D-35).
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from numpy.polynomial import legendre

MIN_STEPS_PER_READOUT = 20  # engineering guard against capacities fitted on too few steps


def _p(n: int, x: np.ndarray) -> np.ndarray:
    """Legendre P_n scaled to unit mean square under U[-1, 1]: sqrt(2n + 1) P_n."""
    return np.sqrt(2 * n + 1) * legendre.legval(x, [0] * n + [1])


def _specs(max_delay: int, max_degree: int):
    """All {delay: degree} products with distinct delays and total degree 1..max_degree."""
    for n_factors in range(1, max_degree + 1):
        for delays in combinations(range(max_delay), n_factors):
            yield from _degree_splits(delays, max_degree)


def _degree_splits(delays, budget):
    if len(delays) == 1:
        for d in range(1, budget + 1):
            yield ((delays[0], d),)
        return
    for d in range(1, budget - len(delays) + 2):
        for rest in _degree_splits(delays[1:], budget - d):
            yield ((delays[0], d),) + rest


def legendre_basis(u: np.ndarray, max_delay: int, max_degree: int) -> tuple[list, np.ndarray]:
    """Target specs and matrix Z (rows k = max_delay-1 .. T-1, one column per target)."""
    lagged = {d: u[max_delay - 1 - d: len(u) - d] for d in range(max_delay)}
    specs = list(_specs(max_delay, max_degree))
    z = np.stack([np.prod([_p(n, lagged[d]) for d, n in s], axis=0) for s in specs], axis=1)
    return specs, z


def _capacities(x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """In-sample capacity of every column of z; constant or collinear readouts add nothing
    (orthonormal basis of the readout span from a rank-revealing SVD)."""
    u, s, _ = np.linalg.svd(np.column_stack([x, np.ones(len(x))]), full_matrices=False)
    q = u[:, s > s[0] * 1e-10]
    return np.sum((q.T @ z) ** 2, axis=0) / np.sum(z**2, axis=0)


def ipc(states: np.ndarray, u: np.ndarray, max_delay: int, max_degree: int, rng: np.random.Generator) -> dict:
    """MC (degree 1), nonlinear IPC (degree >= 2) and total, bias-corrected (see module doc)."""
    if len(states) != len(u):
        raise ValueError("states and u must have one row per step")
    x = states[max_delay - 1:]
    if len(x) < MIN_STEPS_PER_READOUT * (states.shape[1] + 1):
        raise ValueError(f"{len(x)} usable steps is too few for {states.shape[1]} readouts")
    specs, z = legendre_basis(u, max_delay, max_degree)
    degree = np.array([sum(n for _, n in s) for s in specs])
    c_n = _capacities(x, z)
    half = len(x) // 2
    c_half = _capacities(x[:half], z[:half])
    _, z_shuf = legendre_basis(rng.permutation(u), max_delay, max_degree)
    c_shuf = _capacities(x, z_shuf)
    cutoff = {d: c_shuf[degree == d].max() for d in np.unique(degree)}
    keep = c_n > np.array([cutoff[d] for d in degree])
    est = np.where(keep, np.clip(2 * c_n - c_half, 0.0, 1.0), 0.0)
    per_degree = {int(d): float(est[degree == d].sum()) for d in np.unique(degree)}
    return {
        "mc": float(est[(degree == 1) & np.array([s[0][0] > 0 for s in specs])].sum()),
        "instantaneous_linear": float(est[(degree == 1) & np.array([s[0][0] == 0 for s in specs])].sum()),
        "delay_convention": "total includes delay zero; mc strictly positive delays",
        "nonlinear": float(est[degree >= 2].sum()),
        "total": float(est.sum()),
        "per_degree": per_degree,
        "n_steps": len(x),
    }
