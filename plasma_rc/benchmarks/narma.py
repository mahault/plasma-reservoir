"""NARMA-10 benchmark for reservoir computing (Atiya & Parlos, IEEE Trans. Neural Netw. 11, 697, 2000):
    y(t+1) = 0.3 y(t) + 0.05 y(t) sum_{i=0..9} y(t-i) + 1.5 u(t-9) u(t) + 0.1,   u ~ U[0, 0.5].

TODO (Samuel / Luca):
    - Run through physical plasma + digital twin
    - Compare NMSE across readout types (linear, Bayesian, BayesNet)
"""
from __future__ import annotations

import numpy as np


def narma10_target(u: np.ndarray) -> np.ndarray:
    """NARMA-10 target for a given input u in [0, 0.5] (first 10 values 0)."""
    y = np.zeros(len(u))
    for t in range(10, len(u)):
        y[t] = 0.3 * y[t - 1] + 0.05 * y[t - 1] * np.sum(y[t - 10 : t]) + 1.5 * u[t - 1] * u[t - 10] + 0.1
    return y


def narma10(n_steps: int, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """NARMA-10 input/target pair: u (n_steps,) uniform in [0, 0.5], y (n_steps,) target."""
    u = np.random.RandomState(seed).uniform(0, 0.5, n_steps)
    return u, narma10_target(u)
