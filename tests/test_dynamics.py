"""Replica dynamics: λ_c from divergence (untested hypothesis, D-34) and flash reliability."""

import numpy as np
import pytest

from plasma_rc.characterization.dynamics import flash_reliability, lambda_c


def test_lambda_c_recovers_known_contraction_rate():
    t = np.arange(200) * 0.1
    rng = np.random.default_rng(0)
    drive = np.sin(t)
    reps = np.stack([drive + a * np.exp(-0.5 * t) + 1e-6 * rng.standard_normal(t.size)
                     for a in (1.0, -0.7, 0.4)])
    res = lambda_c(reps[:, :, None], dt=0.1, floor=1e-4)
    assert res["lambda"] == pytest.approx(-0.5, abs=0.05)


def test_lambda_below_floor_nan():
    reps = np.zeros((3, 50, 1))
    res = lambda_c(reps, dt=1.0, floor=1.0)
    assert np.isnan(res["lambda"]) and "floor" in res["reason"]


def test_flash_reliability_measures_jitter():
    rng = np.random.default_rng(3)
    ref = np.arange(1, 41) * 0.05
    reps = [ref + 1e-4 * rng.standard_normal(ref.size) for _ in range(8)]
    res = flash_reliability(reps, window_s=0.01)
    assert res["matched_fraction"] == 1.0
    assert res["median_sigma_s"] == pytest.approx(1e-4, rel=0.4)


def test_flash_reliability_unmatched_flashes_lower_fraction():
    ref = np.array([0.1, 0.2, 0.3])
    res = flash_reliability([ref, np.array([0.1, 0.3])], window_s=0.01)
    assert res["matched_fraction"] == pytest.approx(2 / 3)
