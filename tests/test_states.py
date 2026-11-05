"""State readout (plasma_rc.states) against closed forms, and the simulation adapter's resolution."""
from pathlib import Path

import numpy as np

from plasma_rc.circuit import Config
from plasma_rc.sim import iid_delay, simulate
from plasma_rc.states import FINE, sim_states, strike_latency, window_means
from tests.test_sim import ZERO, cfg


def test_window_means_of_rc_charge_match_the_integral():
    c = cfg(V_b=1e4)                                   # lamp never strikes: plain RC, tau = R_th C_s = 0.5 µs
    tr = simulate(c, np.array([0.6]), 5e-6, 4 * FINE, ZERO, seed=0)
    v_th, r_th = c.thevenin(c.drive(0.6))
    tau, a = r_th * 10e-12, np.arange(4) * 1.25e-6
    exact = v_th * (1 - tau / 1.25e-6 * (np.exp(-a / tau) - np.exp(-(a + 1.25e-6) / tau)))
    np.testing.assert_allclose(sim_states(tr, 4)[0, :4], exact, atol=2e-3 * v_th)   # midpoint rule, h = 78 ns


def test_window_means_bins_by_segment_edges():
    t = np.array([0, 1, 2, 3, 4, 5, 6, 7])
    x = window_means(t, t * 10.0, [0, 4, 8], 2)       # segments [0,4), [4,8); two sub-windows each
    np.testing.assert_array_equal(x, [[5, 25], [45, 65]])
    assert np.isnan(window_means([0.5], [1.0], [0, 1, 2], 1)[1, 0])   # empty sub-window


def test_fine_resolution_bound_in_relaxation_of_the_study_circuit():
    # Midpoint samples miss ~0.1 µs strike discharges. For the study's illustrative circuit in R1, FINE = 16
    # stays within 3 % of the state range of a 4x finer readout (measured 2.3 %). Faster circuits err more
    # (22 % for the tests' RAW circuit): exact window integrals are the proper fix (proposed, not done).
    c = Config(Path(__file__).resolve().parents[1] / "configs/sim_illustrative.json")
    x = np.random.default_rng(0).integers(100, 146, 60) / 255
    s16, s64 = (sim_states(simulate(c, x, 20e-6, 4 * f, iid_delay(1e-6, 0.0), seed=3), 4)[:, :4] for f in (16, 64))
    assert np.abs(s16 - s64).max() < 0.03 * np.ptp(s64)


def test_strike_latency_is_censored_at_the_step_length():
    lat = strike_latency([0.5, 0.7, 2.25], [0, 1, 2, 3])
    np.testing.assert_allclose(lat, [[0.5, 1], [1.0, 0], [0.25, 1]])
    np.testing.assert_allclose(strike_latency([], [0, 2]), [[2.0, 0]])
