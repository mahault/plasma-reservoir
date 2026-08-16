from __future__ import annotations

import numpy as np

from plasma_rc.characterization.dimensionality import effective_dimensionality
from plasma_rc.characterization.memory_capacity import memory_capacity
from plasma_rc.characterization.separation import separation_matrix


def test_memory_capacity_returns_expected_shapes():
    rng = np.random.RandomState(0)
    signal = rng.randn(120)
    states = rng.randn(120, 8)
    mc, per = memory_capacity(states, signal, max_delay=12)
    assert isinstance(mc, float)
    assert per.shape == (12,)


def test_effective_dimensionality_valid_range():
    rng = np.random.RandomState(0)
    states = rng.randn(80, 6)
    n, cum = effective_dimensionality(states, threshold=0.9)
    assert 1 <= n <= states.shape[1]
    assert cum.ndim == 1


def test_separation_matrix_square():
    rng = np.random.RandomState(0)
    data = {
        "a": rng.randn(3, 20, 4),
        "b": rng.randn(3, 20, 4) + 0.3,
    }
    sep, labels = separation_matrix(data)
    assert sep.shape == (2, 2)
    assert labels == ["a", "b"]
