"""Known same-step mapping, memoryless baseline and missing flash regressions."""

import numpy as np
import pytest
from plasma_rc.characterization.ipc import ipc
from plasma_rc.characterization.dynamics import flash_reliability
from plasma_rc.reservoir.digital_twin import PlasmaDigitalTwin


def test_memoryless_readout_is_instantaneous_not_memory():
    u = np.random.default_rng(9).uniform(-1, 1, 3000)
    result = ipc(u[:, None], u, 10, 1, np.random.default_rng(1))
    assert result["mc"] < 0.05
    assert result["instantaneous_linear"] == pytest.approx(1.0, abs=0.02)
    assert result["total"] == pytest.approx(1.0, abs=0.05)


def test_missing_flash_cannot_match_twice():
    result = flash_reliability([np.array([0.10, 0.11]), np.array([0.105])], 0.01)
    assert result["matched_fraction"] == 0.5


def test_gp_current_window_predicts_current_state():
    u = np.random.default_rng(3).normal(size=70)
    y = np.column_stack([u, 2 * u, -u])
    twin = PlasmaDigitalTwin(noise_scale=0.0)
    twin.fit(u, y)
    for value in u[:5]:
        state = twin.step(value).as_array()
    np.testing.assert_allclose(state, y[4], atol=0.05)
