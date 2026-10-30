"""Circuit A in ngspice against the technical.md §4 formulas (plasma_rc.circuit_checks).

Bulb = hysteretic switch (D-20, model hypothesis, accepted 2026-10-26): strikes at v >= V_b
(no breakdown delay), conducts on v = V_m + r_on i_b, extinguishes when i_b < I_min, i.e. at
v = V_e. Datasheet NE-2AS values (lit. review [2], Cited): V_b 76 V avg, maintaining 58 V at
0.3 mA, extinguishing >= 50 V. I_min is Unknown (50 µA here); component values are
illustrative, not the build. Skipped when ngspice is not installed.
"""

import math
import shutil

import numpy as np
import pytest
from scipy.linalg import expm

from plasma_rc.circuit_checks import corner_hz, mid_gain
from plasma_rc.sim import PART, V_B, V_E, bulb, pulse, thev, tran
from plasma_rc.sim import spice as _spice

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="needs ngspice")

I_MIN = 50e-6  # Unknown; one value inside the swept range
B = bulb(I_MIN)
R_ON, V_M, I_OP = B["r_on"], B["V_m"], 0.3e-3


def spice(tmp_path, analysis, V_s, **kw):
    return _spice(tmp_path, analysis, V_s, I_MIN, **kw)


def test_rest_node_is_thevenin_and_silent(tmp_path):
    t, v, ib, _ = tran(spice(tmp_path, "tran 10u 50m", V_s=77))
    assert v[-1] == pytest.approx(thev(77)[0], abs=0.01)  # 69.94 V, inside V_e < V_s' < V_b
    assert ib.max() < 1e-9


def test_relaxation_period_above_breakdown(tmp_path):
    """C_c out: V_s' > V_b oscillates. Off phase charges V_e -> V_b with R'C (§4.1 recovery); on
    phase discharges V_b -> V_e towards v_on with C (R' ∥ (r_on + R_sense)) (Derived)."""
    t, v, ib, _ = tran(spice(tmp_path, "tran 1u 0.2 0 1u", V_s=90, cc="*"))
    V, R = thev(90)
    r = R_ON + PART["R_sense"]
    v_on = (V * r + V_M * R) / (R + r)
    T = PART["C"] * (R * math.log((V - V_E) / (V - V_B)) + R * r / (R + r) * math.log((V_B - v_on) / (V_E - v_on)))
    strikes = t[1:][np.diff((ib > 1e-6).astype(int)) == 1]
    assert np.median(np.diff(strikes[2:])) == pytest.approx(T, rel=0.02)


def test_input_path_bulb_off(tmp_path):
    """§4.3 with the divider: the node sees Rs ∥ R_d, and C_c sees Re + Rs ∥ R_d below the band."""
    d = spice(tmp_path, "ac dec 100 1m 1Meg", V_s=77, va="DC 0 AC 1")
    f, H = d[:, 0], np.abs(d[:, 1] + 1j * d[:, 2])
    Rp = 1 / (1 / PART["Rs"] + 1 / PART["R_d"])
    assert H.max() == pytest.approx(mid_gain(Rp, PART["Re"]), rel=0.01)
    band = f[H >= H.max() / math.sqrt(2)]
    assert band[-1] == pytest.approx(corner_hz(1 / (1 / Rp + 1 / PART["Re"]), PART["C"]), rel=0.05)
    assert band[0] == pytest.approx(corner_hz(PART["Re"] + Rp, PART["C_c"]), rel=0.05)


def test_recovery_with_input_branch_is_two_pole(tmp_path):
    """After a flash the charged C_c also feeds the node: state (v, w = v - v_a) relaxes as
    C v' = (V'-v)/R' - (v-w)/Re,  C_c w' = (v-w)/Re  (Derived). Slow pole ~ (R'+Re) C_c."""
    t, v, ib, va = tran(spice(tmp_path, "tran 5u 1.2 0 5u", V_s=77, va=pulse(22)))
    V, R = thev(77)
    off = np.flatnonzero(ib > 1e-6)[-1] + 1
    assert t[off] > 0.3101  # input pulse is over: v_a source = 0 from here on
    C, Cc, Re = PART["C"], PART["C_c"], PART["Re"]
    A = np.array([[-(1 / R + 1 / Re) / C, 1 / (Re * C)], [1 / (Re * Cc), -1 / (Re * Cc)]])
    x_inf, x0 = np.array([V, V]), np.array([v[off], v[off] - va[off]])
    ts = t[off::50]
    pred = np.array([(x_inf + expm(A * (tt - t[off])) @ (x0 - x_inf))[0] for tt in ts])
    assert np.max(np.abs(pred - v[off::50])) < 0.3
    assert -1 / np.linalg.eigvals(A).max() == pytest.approx((R + Re) * Cc, rel=0.1)


def test_always_on_current(tmp_path):
    """J_C out (C small), Rs_B: I_op = (V'-V_m)/(R'+r_on+R_sense); §4.2's (V'-V_m)/R' drops r_on."""
    over = dict(Rs=130e3, C=100e-12)
    t, v, ib, _ = tran(spice(tmp_path, "tran 10u 50m", V_s=95, **over))
    V, R = thev(95, **over)
    assert ib[-1] == pytest.approx((V - V_M) / (R + R_ON + PART["R_sense"]), rel=0.01)
    assert I_MIN < ib[-1] < I_OP * 2


@pytest.mark.parametrize("Re", [100e3, 1e6])
def test_latching_follows_supply_parallel_input_branch(tmp_path, Re):
    """A 10 ms input pulse fires the bulb; it stays lit long after the pulse iff
    (V_s' - V_e)/(R' ∥ Re) > I_min (circuit_checks.near_breakdown_window with R_eff = R' ∥ Re)."""
    t, v, ib, _ = tran(spice(tmp_path, "tran 5u 0.8 0 5u", V_s=77, va=pulse(22), Re=Re))
    V, R = thev(77)
    latches = (V - V_E) / (R * Re / (R + Re)) > I_MIN
    lit_after = t[ib > 1e-6].max() - 0.31
    assert (lit_after > 0.05) == latches, lit_after
