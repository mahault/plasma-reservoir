"""IPC (Dambre et al. 2012) against systems with known capacities."""

import numpy as np
import pytest

from plasma_rc.characterization.ipc import ipc, legendre_basis

rng = np.random.default_rng(0)
U = rng.uniform(-1, 1, 6000)


def _delay_line(u, taps):
    return np.stack([np.roll(u, j) for j in range(taps)], axis=1)


def test_basis_is_orthonormal_under_uniform_input():
    specs, z = legendre_basis(U, max_delay=3, max_degree=2)
    gram = z.T @ z / len(z)
    np.testing.assert_allclose(gram, np.eye(len(specs)), atol=0.06)


def test_delay_line_has_memory_equal_to_taps_and_no_nonlinearity():
    res = ipc(_delay_line(U, 5), U, max_delay=10, max_degree=2, rng=np.random.default_rng(1))
    assert res["mc"] == pytest.approx(4.0, abs=0.1)
    assert res["nonlinear"] == pytest.approx(0.0, abs=0.05)


def test_square_of_input_gives_degree_two_capacity():
    res = ipc(np.stack([U, U**2], axis=1), U, max_delay=4, max_degree=2, rng=np.random.default_rng(2))
    assert res["per_degree"][2] == pytest.approx(1.0, abs=0.05)
    assert res["total"] <= 2.0 + 0.05  # bounded by the number of readouts


def test_too_short_raises():
    with pytest.raises(ValueError, match="steps"):
        ipc(_delay_line(U[:60], 3), U[:60], max_delay=20, max_degree=3, rng=np.random.default_rng(0))


def test_constant_and_duplicate_readouts_add_no_capacity():
    x = _delay_line(U, 2)
    padded = np.column_stack([x, x[:, 0], np.zeros(len(U)), np.ones(len(U))])
    a = ipc(x, U, max_delay=6, max_degree=2, rng=np.random.default_rng(4))
    b = ipc(padded, U, max_delay=6, max_degree=2, rng=np.random.default_rng(4))
    assert b["total"] == pytest.approx(a["total"], abs=1e-9)
