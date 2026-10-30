"""technical.md §4 conditions, checked against hand-derived numbers."""

import pytest

from plasma_rc import circuit_checks as cc


def test_rs_min():
    assert cc.rs_min(235.0, 50.0, 0.3e-3) == pytest.approx(616_666.67, rel=1e-6)


def test_thevenin_and_back():
    v, r = cc.thevenin(100.0, 1e6, 10e6)
    assert v == pytest.approx(1000 / 11) and r == pytest.approx(1e7 / 11)
    assert cc.supply_for(v, 1e6, 10e6) == pytest.approx(100.0)


def test_near_breakdown_window_limited_by_latching():
    # silent: V_e < V' < V_b; no latch: V' < V_e + I_min R'  -> (50, min(76, 60))
    assert cc.near_breakdown_window(76.0, 50.0, 1e-4, 1e5) == pytest.approx((50.0, 60.0))


def test_always_on_window():
    # strike: V' > V_b; I_min < (V' - V_m)/R' < I_max -> (max(76, 68), 88)
    assert cc.always_on_window(76.0, 58.0, 1e-4, 3e-4, 1e5) == pytest.approx((76.0, 88.0))


def test_empty_window_is_none():
    assert cc.near_breakdown_window(76.0, 80.0, 1e-4, 1e5) is None


def test_input_path():
    assert cc.mid_gain(1e6, 1e6) == pytest.approx(0.5)
    assert cc.droop(0.01, 1e6, 1e-6) == pytest.approx(0.01)
    assert cc.corner_hz(1e3, 1e-6) == pytest.approx(159.15494, rel=1e-6)


def test_always_on_includes_conducting_resistance():
    # With affine intercept 48 V and total series resistance 200 kohm:
    # (max(76,48+20),48+60) = (76,108).
    assert cc.always_on_window(76.,48.,1e-4,3e-4,1e5,r_on=1e5) == pytest.approx((76.,108.))
