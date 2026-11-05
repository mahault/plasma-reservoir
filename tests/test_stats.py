import numpy as np
import pytest

from plasma_rc.stats import cluster_bootstrap, holm


def test_holm_adjustment_hand_example():
    # sorted p 0.01, 0.03, 0.04 -> 0.03, 0.06, max(0.06, 0.04) = 0.06; returned in input order
    np.testing.assert_allclose(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])


def test_cluster_bootstrap_resamples_bulbs_not_trials():
    # bulb A: 10 trials at +1, bulb B: 1 trial at -1. Trial-level mean 0.82; bulb-level mean 0.
    diffs = np.array([1.0] * 10 + [-1.0])
    bulbs = np.array(["A"] * 10 + ["B"])
    res = cluster_bootstrap(diffs, bulbs, n_boot=4000, seed=0)
    assert res["mean"] == pytest.approx(0.0)
    assert res["lo"] == pytest.approx(-1.0) and res["hi"] == pytest.approx(1.0)
    assert res["n_clusters"] == 2
