"""NARMA-10 benchmark for reservoir computing.

TODO (Samuel / Luca):
    - Run through physical plasma + digital twin
    - Compare NMSE across readout types (linear, Bayesian, BayesNet)
"""
from __future__ import annotations

import numpy as np


def narma10(n_steps: int, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Generate NARMA-10 input/target pair.

    Returns
    -------
    u : (n_steps,) uniform random input in [0, 0.5]
    y : (n_steps,) NARMA-10 target signal
    """
    rng = np.random.RandomState(seed)
    u = rng.uniform(0, 0.5, n_steps)
    y = np.zeros(n_steps)
    for t in range(10, n_steps):
        y[t] = (
            0.3 * y[t - 1]
            + 0.05 * y[t - 1] * np.sum(y[t - 10 : t])
            + 1.5 * u[t - 1] * u[t - 10]
            + 0.1
        )
    return u, y
