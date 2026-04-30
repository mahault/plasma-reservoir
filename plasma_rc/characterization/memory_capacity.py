"""Memory capacity measurement for reservoir computing.

MC = sum_{k=1}^{K} R^2(y_k, u_{t-k})

where y_k is the linear readout trained to reconstruct the input
delayed by k steps.  Theoretical max = number of independent
reservoir dimensions.

TODO (Luca / Samuel):
    - Run on real plasma data once sufficient trials collected
    - Compare MC across input types (audio, sine, noise)
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import Ridge


def memory_capacity(
    reservoir_states: np.ndarray,
    input_signal: np.ndarray,
    max_delay: int = 50,
    alpha: float = 1e-6,
) -> tuple[float, np.ndarray]:
    """Compute memory capacity of a reservoir.

    Parameters
    ----------
    reservoir_states : (T, D) reservoir state matrix
    input_signal : (T,) input signal that was fed to the reservoir
    max_delay : maximum delay k to test
    alpha : Ridge regularization

    Returns
    -------
    mc : total memory capacity (scalar)
    mc_per_delay : (max_delay,) R^2 at each delay
    """
    T = len(input_signal)
    mc_per_delay = np.zeros(max_delay)

    for k in range(1, max_delay + 1):
        target = input_signal[: T - k]
        states = reservoir_states[k:]
        n = min(len(target), len(states))
        target, states = target[:n], states[:n]

        model = Ridge(alpha=alpha)
        model.fit(states, target)
        pred = model.predict(states)

        ss_res = np.sum((pred - target) ** 2)
        ss_tot = np.sum((target - target.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        mc_per_delay[k - 1] = max(r2, 0.0)

    return float(mc_per_delay.sum()), mc_per_delay
