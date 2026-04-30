"""Mackey-Glass chaotic time series benchmark.

TODO (Samuel / Luca):
    - Run through physical plasma + digital twin
    - Evaluate one-step and multi-step prediction NMSE
"""
from __future__ import annotations

import numpy as np


def mackey_glass(
    n_steps: int, tau: int = 17, beta: float = 0.2, gamma: float = 0.1, n: int = 10, dt: float = 0.1
) -> np.ndarray:
    """Generate Mackey-Glass time series.

    dx/dt = beta * x(t-tau) / (1 + x(t-tau)^n) - gamma * x(t)

    Returns
    -------
    x : (n_steps,) Mackey-Glass signal
    """
    x = np.zeros(n_steps)
    x[0] = 1.2
    for t in range(max(tau, 1), n_steps - 1):
        x_tau = x[t - tau]
        x[t + 1] = x[t] + dt * (beta * x_tau / (1.0 + x_tau ** n) - gamma * x[t])
    return x
