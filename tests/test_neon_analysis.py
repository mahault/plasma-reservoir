"""Causality and target alignment for minimal-circuit benchmark analysis."""
import numpy as np
import pytest

from plasma_rc.neon.analysis import step_samples, narma_score, narma_predict, held_drive, input_delays, delayed_capacities, characterize_ipc, optical_features, feature_correlations, strike_delay
from plasma_rc.neon.spice import Trace


def test_step_samples_cannot_use_next_step():
    trace = Trace(np.array([0., 1., 2., 3.]), np.zeros(4),
                  np.array([0., 1., 2., 1000.]), np.zeros(4))
    features = step_samples(trace, np.array([0., 1., 2.]), windows=1)
    assert features.shape == (2, 2)
    assert features[1, 0] == pytest.approx(1.5)


def test_final_boundary_roundoff_does_not_reject_interior_samples():
    trace = Trace(np.array([0., 0.1, 0.3]), np.zeros(3), np.array([0., 1., 3.]), np.zeros(3))
    features = step_samples(trace, np.array([0., 0.1, 0.1 + 0.2]), windows=1)
    assert features[:, 0] == pytest.approx([0.5, 2.0])


def test_step_sampling_rejects_interpolation_using_next_step():
    trace = Trace(np.array([0., 1., 3.]), np.zeros(3), np.array([0., 1., 100.]), np.zeros(3))
    with pytest.raises(ValueError, match="bracket"):
        step_samples(trace, np.array([1., 2.]), windows=1)


def test_narma_score_recovers_exact_target_without_shifting():
    u = np.random.default_rng(8).uniform(0, 0.5, 200)
    from plasma_rc.neon.narma import narma10_target
    target = narma10_target(u)
    # This artificial state is only an alignment test, never a reservoir feature.
    x = np.concatenate([target[1:], [0]])[:, None]
    score = narma_score(x, u, train=(20, 100), test=(110, 190), alpha=0.0)
    assert score < 1e-20
    expected, predicted = narma_predict(x, u, train=(20, 100), test=(110, 190), alpha=0.0)
    np.testing.assert_allclose(expected, predicted, atol=1e-12)


def test_narma10_recurrence_matches_hand_calculation():
    from plasma_rc.neon.narma import narma10_target
    y = narma10_target(np.full(12, 0.5))
    assert y[10] == pytest.approx(0.475)
    assert y[11] == pytest.approx(0.62878125)


def test_held_drive_keeps_each_input_until_next_step():
    points, edges = held_drive(np.array([0., 0.5]), bias_v=70, gain_v=20,
                               step_s=0.01, start_s=0.02, rise_s=0.0001)
    assert edges == pytest.approx([0.02, 0.03, 0.04])
    assert np.interp(0.025, *np.asarray(points).T) == pytest.approx(70)
    assert np.interp(0.035, *np.asarray(points).T) == pytest.approx(80)


def test_delays_contain_only_present_and_past_values():
    result = input_delays(np.array([1., 2., 3., 4.]), 3)
    np.testing.assert_array_equal(result[2], [3., 2., 1.])
    np.testing.assert_array_equal(result[0], [1., 0., 0.])


def test_held_out_capacity_detects_present_without_inventing_memory():
    u = np.random.default_rng(4).uniform(0, 0.5, 4000)
    result = delayed_capacities(u[:, None], u, train=(10, 2000), test=(2000, 4000), max_delay=2)
    assert result["degree_1"][0] == pytest.approx(1, abs=0.001)
    assert result["degree_1"][1] < 0.03


def test_held_out_capacity_detects_cross_delay_nonlinearity():
    u = np.random.default_rng(9).uniform(0, 0.5, 4000)
    d = input_delays(4 * u - 1, 2)
    result = delayed_capacities((d[:, 0] * d[:, 1])[:, None], u, (10, 2000), (2000, 4000), 2)
    assert result["degree_2_cross"]["0,1"] == pytest.approx(1, abs=0.001)


def test_ipc_reports_significant_present_signal_and_shuffled_null():
    u = np.random.default_rng(10).uniform(0, 0.5, 1000)
    result = characterize_ipc(u[:, None], u, (10, 500), (500, 1000), 2, seed=3, n_shuffles=3)
    assert result["linear_capacity"] == pytest.approx(1, abs=0.05)
    assert result["null_max"]["degree_1"] < 0.1


def test_optical_features_report_proxy_flash_rate_and_variation():
    t = np.array([0., 0.25, 0.5, 0.75, 1., 1.25, 1.5, 1.75, 2.])
    current = np.array([0., 0., 2e-6, 2e-6, 0., 0., 0., 0., 0.])
    trace = Trace(t, np.zeros_like(t), np.zeros_like(t), current)
    x = optical_features(trace, np.array([0., 1., 2.]), samples=2, threshold_a=1e-6)
    np.testing.assert_allclose(x[:, 0], [1e-6, 0], atol=1e-15)
    np.testing.assert_allclose(x[:, 1], [1, 0], atol=1e-15)
    np.testing.assert_allclose(x[:, 2], [1e-6, 0], atol=1e-15)


def test_correlations_mark_constant_features_as_undefined():
    x = np.array([[1., 2., 3.], [2., 4., 3.], [3., 6., 3.]])
    result = feature_correlations(x)
    assert result[0][1] == pytest.approx(1)
    assert result[0][2] is None


def test_strike_delay_requires_new_ignition_after_pulse():
    t = np.array([0., 0.1, 0.2, 0.3, 0.4])
    trace = Trace(t, np.zeros(5), np.zeros(5), np.array([0., 0., 0., 2e-6, 2e-6]))
    assert strike_delay(trace, start_s=0.1, end_s=0.4) == pytest.approx(0.2)
    assert strike_delay(trace, start_s=0.3, end_s=0.4) is None
