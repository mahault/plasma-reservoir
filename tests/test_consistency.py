from __future__ import annotations

import numpy as np
import pytest

from plasma_rc.characterization.consistency import pairwise_consistency


def test_pairwise_consistency_two_identical_traces_is_one():
    trace = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    traces = np.stack([trace, trace])
    assert pairwise_consistency(traces) == pytest.approx(1.0)


def test_pairwise_consistency_three_trials_averages_pairs():
    # a = [1,2,3]; b = 2*a (affine positive slope -> corr(a,b) = +1);
    # c = 4-a (affine negative slope -> corr(a,c) = corr(b,c) = -1).
    # These are well-known algebraic facts about Pearson correlation under
    # affine transforms, computed independently of pairwise_consistency's
    # own implementation. Expected mean of the three pairs: (1 - 1 - 1)/3.
    a = np.array([1.0, 2.0, 3.0])
    b = 2 * a
    c = 4 - a
    traces = np.stack([a, b, c])
    assert pairwise_consistency(traces) == pytest.approx(-1.0 / 3.0)


def test_pairwise_consistency_independent_noise_is_near_zero():
    # For large N, independent Gaussian samples have sample correlation
    # concentrated near 0 (a standard statistical fact, not derived from
    # pairwise_consistency's own implementation).
    rng = np.random.default_rng(0)
    traces = rng.standard_normal((5, 20000))
    assert abs(pairwise_consistency(traces)) < 0.05
