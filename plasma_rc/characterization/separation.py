"""Separation property analysis.

Measures whether distinct inputs produce distinguishable reservoir states.

TODO (Majesti / Samuel):
    - Collect multi-class data (different words, different volumes)
    - Compute pairwise distance matrices
    - Lyapunov (λ_c) estimation lives in dynamics.py (D-34)
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
