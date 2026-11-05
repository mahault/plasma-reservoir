import numpy as np
import pytest

from plasma_rc import analysis as A
from plasma_rc import benchmarks as B


def test_narma_hand_values():
    y = B.narma_target(np.full(12, 0.25), 10)
    assert y[:10].sum() == 0 and y[10] == pytest.approx(1.5 * 0.25 * 0.25 + 0.1)
    y2 = B.narma_target(np.full(5, 0.25), 2)
    assert y2[2] == pytest.approx(0.3 * y2[1] + 0.05 * y2[1] * (y2[1] + y2[0]) + 1.5 * 0.25 * 0.25 + 0.1)


def test_xor_needs_nonlinear_memory():
    b = np.random.default_rng(1).integers(0, 2, 3000).astype(float)
    lag = lambda d: np.concatenate([np.zeros(d), b[:-d]])  # noqa: E731
    z = B.parity(b, (1, 2))
    sp = A.splits(len(b))
    linear = np.column_stack([lag(1), lag(2)])
    assert B.accuracy(np.column_stack([linear, lag(1) * lag(2)]), z, sp) > 0.99
    assert B.accuracy(linear, z, sp) < 0.8          # XOR is not linearly separable
    assert B.accuracy(b[:, None], z, sp) < 0.6      # no memory: chance


def test_numerical_rank_and_exponent():
    rng = np.random.default_rng(2)
    S = rng.normal(size=(40, 3)) @ rng.normal(size=(3, 8))
    assert B.numerical_rank(S) == 3
    t = np.linspace(0, 1e-4, 200)
    assert B.divergence_exponent(t, 1e-3 * np.exp(-t / 2e-5)) == pytest.approx(-1 / 2e-5, rel=1e-6)


def test_linear_states_never_pass_the_xor_ceiling():
    # a linear chain holding b[k] and b[k-1] (the resistor control's best case) stays at or below 0.75
    b = np.random.default_rng(3).integers(0, 2, 3000)
    X = np.column_stack([b, np.concatenate([[0], b[:-1]])]).astype(float)
    assert B.binary(X, b, A.splits(len(b)))["xor(0, 1)"] <= 0.76


def test_held_battery_on_a_delay_line_and_rank_centering():
    u = np.random.default_rng(4).uniform(0, 0.5, 2000)
    s = A.scaled(u)
    X = np.column_stack([s, np.concatenate([[0], s[:-1]])])
    out = B.held(X, u, A.splits(len(u)), seed=0, max_delay=3)
    assert out["mc"][0] > 0.95 and out["mc"][2] == 0 and set(out["narma"]) == {2, 5, 10}
    rng = np.random.default_rng(5)
    kern = 100 + rng.normal(size=(40, 3)) @ rng.normal(size=(3, 8))   # offset must not count as a dimension
    assert B.rank(kern, kern[:1].repeat(40, 0))["kernel_rank"] == 3
