"""Separation property analysis.

Measures whether distinct inputs produce distinguishable reservoir states.

TODO (Majesti / Samuel):
    - Collect multi-class data (different words, different volumes)
    - Compute pairwise distance matrices
    - Estimate Lyapunov exponents for trajectory divergence
"""
from __future__ import annotations

import numpy as np


def separation_matrix(
    class_trajectories: dict[str, np.ndarray],
) -> tuple[np.ndarray, list[str]]:
    """Pairwise Euclidean distance between mean class trajectories.

    Parameters
    ----------
    class_trajectories : {label: (n_trials, T, D)} reservoir states per class

    Returns
    -------
    dist : (C, C) distance matrix
    labels : class labels in matrix order
    """
    labels = sorted(class_trajectories.keys())
    n = len(labels)
    dist = np.zeros((n, n))

    means = {}
    for label in labels:
        # mean trajectory across trials, then flatten
        means[label] = class_trajectories[label].mean(axis=0).ravel()

    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(means[labels[i]] - means[labels[j]])

    return dist, labels


def lyapunov_estimate(
    trajectories: np.ndarray, dt: float = 1.0
) -> float:
    """Estimate largest Lyapunov exponent from repeated trials of same input.

    Parameters
    ----------
    trajectories : (n_trials, T, D) — same input, multiple runs

    Returns
    -------
    lambda_max : estimated largest Lyapunov exponent
    """
    n_trials, T, D = trajectories.shape
    # pairwise divergence across trials
    divergences = []
    for i in range(n_trials):
        for j in range(i + 1, n_trials):
            d = np.linalg.norm(trajectories[i] - trajectories[j], axis=1)
            d = np.maximum(d, 1e-12)  # avoid log(0)
            divergences.append(np.log(d))

    mean_log_div = np.mean(divergences, axis=0)
    # linear fit to log(divergence) vs time
    t = np.arange(T) * dt
    coeffs = np.polyfit(t, mean_log_div, 1)
    return float(coeffs[0])  # slope = lambda_max
