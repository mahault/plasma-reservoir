import copy

import numpy as np
import pytest

from plasma_rc import analysis as A
from plasma_rc.circuit import Config
from plasma_rc.sim import iid_delay, rest_dependent_delay, simulate
from plasma_rc.stimuli import pulse_pairs
from tests.test_circuit import RAW


def test_capacities_of_a_delay_line():
    u = np.random.default_rng(0).uniform(0, 0.5, 3000)
    s = A.scaled(u)
    lag = lambda d: np.concatenate([np.zeros(d), s[:-d]])  # noqa: E731
    sp = A.splits(len(u))
    lin = A.capacities(np.column_stack([lag(1), lag(2)]), u, sp, max_delay=4, seed=0)
    assert lin["linear"][1] > 0.95 and lin["linear"][2] > 0.95
    assert lin["linear"][3] == 0 and lin["linear"][4] == 0         # below shuffle threshold
    assert sum(lin["quadratic"].values()) == 0
    quad = A.capacities(np.column_stack([lag(1), lag(2), lag(1) * lag(2)]), u, sp, max_delay=3, seed=0)
    assert quad["quadratic"][(1, 2)] > 0.95


def test_consistency_sees_offsets_that_correlation_misses():
    a = np.sin(np.linspace(0, 20, 500))[:, None]
    assert A.consistency(a, a)["nmse_consistency"] == pytest.approx(1.0)
    shifted = A.consistency(a, a + 0.5)
    assert shifted["correlation"] == pytest.approx(1.0) and shifted["nmse_consistency"] < 0.6


def test_attribution_detects_memory_beyond_surrogate():
    rng = np.random.default_rng(1)
    u = rng.uniform(0, 0.5, 2000)
    s = A.scaled(u)
    prev = np.concatenate([[0], s[:-1]])
    surrogate = np.column_stack([s**2])
    sp = A.splits(len(u))
    # var(s²) = 1/5 - 1/9 = 0.089, var(0.8·prev) = 0.213: surrogate alone leaves NMSE ≈ 0.70
    with_memory = np.column_stack([s**2 + 0.8 * prev + 0.05 * rng.normal(size=len(u))])
    without = np.column_stack([s**2 + 0.05 * rng.normal(size=len(u))])
    assert A.attribution(with_memory, surrogate, u, sp, taps=3)["gain"] > 0.5
    assert abs(A.attribution(without, surrogate, u, sp, taps=3)["gain"]) < 0.02


def _e2(delay):
    raw = copy.deepcopy(RAW)
    raw["circuit"]["tau_drv"] = {"value": 0.0, "unit": "s", "source": "assumed"}
    cfg = Config(raw)
    # x = level/255: base 0 -> 100 V (dark), cond 255 -> 200 V (lit), test 204 -> 180 V (strikes, holds),
    # sham 128 -> 150 V (V_th 75 V < V_b: no discharge). One tick = 1 µs. Settle 2 ms exceeds the
    # hypothetical memory horizon, so sham trials start from a rested lamp.
    seg, trials = pulse_pairs([2, 20, 200, 2000], cond=255, test=204, base=0, sham=128,
                              pulse_ticks=100, settle_ticks=2000, repeats=8, seed=0)
    tr = simulate(cfg, seg[:, 0] / 255, seg[:, 1] * 1e-6, 1, delay, seed=0)
    onsets = np.array([t["test_onset_tick"] for t in trials]) * 1e-6
    d = A.strike_delays(tr.flashes, onsets, window_s=100e-6)
    return A.memory_effect(d, [t["rest_ticks"] for t in trials], [t["sham"] for t in trials])


def test_e2_ground_truth_memory_lamp_detected():
    res = _e2(rest_dependent_delay(1e-6, 20e-6, 200e-6))
    assert res["spearman_real"] > 0.8
    assert res["per_rest"][2]["sham_minus_real_s"] > 15e-6        # short rest: real strikes much sooner
    assert abs(res["per_rest"][2000]["sham_minus_real_s"]) < 2e-6  # long rest: memory faded
    assert all(r["real_strike_fraction"] == 1.0 for r in res["per_rest"].values())


def test_e2_ground_truth_iid_lamp_not_detected():
    res = _e2(iid_delay(1e-6, 10e-6))
    assert abs(res["spearman_real"]) < 0.4
