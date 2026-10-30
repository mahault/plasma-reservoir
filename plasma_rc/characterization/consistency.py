"""Consistency (twin-trial) analysis: a Lyapunov-sign proxy from repeated trials.

Implements the pairwise-correlation consistency measure C from Uchida, Yoshimura,
Davis, Yoshimori, Roy, "Consistency in the driven butterfly," Phys. Rev. E 78,
036203 (2008), Eq. 1 (arXiv:nlin/0703004). See research/lyapunov_consistency_experimental_design.md
for the full derivation and literature context.
"""

from __future__ import annotations

import numpy as np


def pairwise_consistency(traces: np.ndarray) -> float:
    """Mean pairwise Pearson correlation across repeated-trial traces.

    Parameters
    ----------
    traces : (n_trials, T) — same stimulus, multiple repeat recordings

    Returns
    -------
    C : mean of the n_trials*(n_trials-1)/2 pairwise correlation coefficients.
        C -> 1 means all repeats converge to the same trajectory (consistent,
        negative conditional Lyapunov exponent); C near 0 means repeats are
        uncorrelated.
    """
    n_trials = traces.shape[0]
    correlations = []
    for i in range(n_trials):
        for j in range(i + 1, n_trials):
            correlations.append(np.corrcoef(traces[i], traces[j])[0, 1])
    return float(np.mean(correlations))
