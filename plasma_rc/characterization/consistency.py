"""Consistency (twin-trial) analysis: a Lyapunov-sign proxy from repeated trials.

Implements the pairwise-correlation consistency measure C from Uchida, Yoshimura,
Davis, Yoshimori, Roy, "Consistency in the driven butterfly," Phys. Rev. E 78,
036203 (2008), Eq. 1 (arXiv:nlin/0703004). See research/lyapunov_consistency_experimental_design.md
for the full derivation and literature context.
"""

from __future__ import annotations

from pathlib import Path

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


def load_repeat_traces(
    npz_paths: list[Path], channel: str, discard_s: float, fs_hz: int
) -> np.ndarray:
    """Load one channel from each repeat-trial npz, discard the transient, align lengths.

    Parameters
    ----------
    npz_paths : repeat recordings of the identical stimulus
    channel : "brightness" or "audio_in"
    discard_s : seconds to drop from the start of each trial (settling/transient)
    fs_hz : sample rate, used to convert discard_s to a sample count

    Returns
    -------
    traces : (n_trials, T) — T is the shortest post-discard trial length
    """
    discard_n = int(discard_s * fs_hz)
    trimmed = []
    for path in npz_paths:
        with np.load(path) as data:
            trimmed.append(data[channel][discard_n:])
    min_len = min(len(t) for t in trimmed)
    return np.stack([t[:min_len] for t in trimmed])
