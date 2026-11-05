"""Event-driven circuit simulation against closed-form solutions of the §4.2 node equation."""
import copy
import math

import numpy as np
import pytest

from plasma_rc.circuit import Config
from plasma_rc.sim import afterglow_delay, iid_delay, rest_dependent_delay, simulate
from plasma_rc.states import FINE, sim_states
from plasma_rc.surrogate import surrogate_states
from tests.test_circuit import RAW


def cfg(**changes):
    raw = copy.deepcopy(RAW)
    raw["circuit"]["tau_drv"] = {"value": 0.0, "unit": "s", "source": "assumed"}
    return Config(raw).with_values(**changes)


ZERO = iid_delay(0.0, 0.0)


def test_rc_charge_with_lamp_off():
    c = cfg(V_b=1e4)                       # never strikes
    tr = simulate(c, np.array([0.6]), 5e-6, 50, ZERO, seed=0)
    v_th, r_th = c.thevenin(c.drive(0.6))
    expected = v_th * (1 - np.exp(-tr.t[0] / (r_th * 10e-12)))
    np.testing.assert_allclose(tr.v[0], expected, rtol=1e-5, atol=1e-6)
    assert tr.flashes.size == 0


def test_relaxation_period_matches_closed_form():
    c = cfg(I_x=1.5e-3)                    # R1: cannot hold at V_D = 200 V (i_op 0.91 mA)
    tr = simulate(c, np.ones(4), 20e-6, 10, ZERO, seed=0)
    v_th, r_th = c.thevenin(200.0)
    v_b, v_x = 80.0, c.extinction_voltage()  # node voltages: 80 V, 50 + 5 kΩ·1.5 mA = 57.5 V
    t_c = r_th * 10e-12 * math.log((v_th - v_x) / (v_th - v_b))
    g = 1 / 100e3 + 1 / 100e3 + 1 / 5e3    # node conductance while lit [S]
    v_eq = (200 / 100e3 + 50 / 5e3) / g     # lit node equilibrium, 54.5 V
    t_on = 10e-12 / g * math.log((v_b - v_eq) / (v_x - v_eq))
    assert c.regime(200.0) == "R1"
    np.testing.assert_allclose(np.diff(tr.flashes)[1:], t_c + t_on, rtol=1e-3)


def test_lit_current_reaches_operating_point():
    c = cfg()
    tr = simulate(c, np.ones(2), 50e-6, 5, ZERO, seed=0)
    assert tr.v_s[-1, -1] / 1e3 == pytest.approx(c.operating_current(200.0), rel=1e-4)


def test_driver_pole_is_first_order():
    c = cfg(V_b=1e4, tau_drv=1e-6)
    tr = simulate(c, np.array([0.0, 1.0]), 10e-6, 20, ZERO, seed=0)
    t = tr.t[1] - 10e-6
    np.testing.assert_allclose(tr.v_d[1], 200 - 100 * np.exp(-t / 1e-6), rtol=1e-5)


def test_tighter_tolerance_does_not_change_result():
    c = cfg(I_x=1.5e-3)
    x = np.random.default_rng(1).uniform(0.6, 1.0, 20)
    a = simulate(c, x, 20e-6, 8, iid_delay(1e-6, 2e-6), seed=3)
    b = simulate(c, x, 20e-6, 8, iid_delay(1e-6, 2e-6), seed=3, rtol=1e-10)
    np.testing.assert_allclose(a.flashes, b.flashes, atol=1e-9)


def test_surrogate_mean_of_deterministic_lamp_is_one_realization():
    raw = copy.deepcopy(RAW)                          # RAW has no t_f / t_s: add a deterministic lamp
    raw["circuit"]["tau_drv"] = {"value": 0.0, "unit": "s", "source": "assumed"}
    raw["lamp"].update({"t_f": {"value": 1e-6, "unit": "s", "source": "assumed"},
                        "t_s": {"value": 0.0, "unit": "s", "source": "assumed"}})
    c = Config(raw).with_values(I_x=1.5e-3)
    x = np.random.default_rng(2).uniform(0.6, 1.0, 10)
    one = sim_states(simulate(c, x, 20e-6, 4 * FINE, iid_delay(1e-6, 0.0), seed=5), 4)
    np.testing.assert_allclose(surrogate_states(c, x, 20e-6, 4, seed=5, k=3), one)


def test_delay_models():
    rng = np.random.default_rng(0)
    iid = iid_delay(1e-6, 2e-6)
    assert np.mean([iid(0.0, rng) for _ in range(4000)]) == pytest.approx(3e-6, rel=0.05)
    mem = rest_dependent_delay(1e-6, 4e-6, 10e-6)   # hypothetical memory lamp, tests only
    assert mem(1e-3, rng) > mem(1e-7, rng)
    glow = afterglow_delay(1e-6, 4e-6, 10e-6)        # accumulates over flashes, decays over rests
    first, burst = glow(1.0, rng), [glow(1e-7, rng) for _ in range(3)]
    assert first == pytest.approx(5e-6) and burst[0] > burst[1] > burst[2]
    assert glow(1.0, rng) == pytest.approx(5e-6)     # long rest: memory faded
