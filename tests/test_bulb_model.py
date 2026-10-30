"""plasma_rc.bulb_model against Derived formulas and against ngspice (same switch bulb)."""

import dataclasses
import math
import shutil

import numpy as np
import pytest

from plasma_rc.stimuli import xorshift32_levels
from plasma_rc.bulb_model import NeonCircuit, conditional_lyapunov, simulate
from plasma_rc.sim import PART, bulb, thev

OCR1A, TPS = 2665, 60  # tick 166.6 µs, step 10.0 ms
TICK_S = (OCR1A + 1) / 16e6
B = bulb(50e-6)
V77, R77 = thev(77)
P = NeonCircuit(V_th=V77, R_th=R77, C=PART["C"], C_c=PART["C_c"], Re=PART["Re"], v_pk=22.0, V_b=B["V_b"],
                V_e=B["V_e"], V_m=B["V_m"], r_on=B["r_on"] + PART["R_sense"], Y_bg=math.inf, Y_res=0.0, tau_res=1.0,
                t_f=0.0, sigma_f=0.0, g_light=4000.0, g_i=4000.0, k_v=0.05, tau_aa=0.53e-3, noise_counts=0.0)


def test_relaxation_period_matches_derived():
    """No input coupling, V' > V_b: T = R'C ln((V'-V_e)/(V'-V_b)) + C (R' ∥ r) ln((V_b-v_on)/(V_e-v_on))."""
    V, R = thev(90)
    p = dataclasses.replace(P, V_th=V, R_th=R, Re=1e15)
    cap = simulate(p, np.full(40, 128, np.uint8), TPS, OCR1A, np.random.default_rng(0))
    r = p.r_on
    v_on = (V * r + p.V_m * R) / (R + r)
    T = p.C * (R * math.log((V - p.V_e) / (V - p.V_b)) + R * r / (R + r) * math.log((p.V_b - v_on) / (p.V_e - v_on)))
    assert np.median(np.diff(cap.flash_times_s()[2:])) == pytest.approx(T, rel=0.01)


def test_statistical_delay_is_exponential_with_mean_one_over_Y():
    """V' above V_b from t = 0, constant Y: first-flash time = Exp(1/Y) + t_f (Laue)."""
    V, R = thev(90)
    p = dataclasses.replace(P, V_th=V, R_th=R, Re=1e15, Y_bg=200.0, t_f=1e-3)
    rng = np.random.default_rng(1)
    first = [simulate(p, np.full(4, 128, np.uint8), TPS, OCR1A, rng).flash_times_s()[0] for _ in range(1000)]
    assert np.mean(first) == pytest.approx(1 / 200 + 1e-3, rel=0.12)
    assert np.std(first) == pytest.approx(1 / 200, rel=0.15)


def test_linear_network_step_gain():
    """Bulb removed: a held input step moves A3 by k_v * v_pk * du * Rp/(Rp+Re) (§4.3, droop negligible)."""
    p = dataclasses.replace(P, bulb=False, v_pk=2.0, R_th=1e6, Re=1e6, C_c=10e-6)
    levels = np.array([128] * 20 + [255] * 20, np.uint8)
    cap = simulate(p, levels, TPS, OCR1A, np.random.default_rng(0), channels="3")
    counts = cap.values.astype(float)
    step_v = (counts[30 * TPS:39 * TPS].mean() - counts[10 * TPS:19 * TPS].mean()) * 5 / 1024
    du = (255 - 128) / 127.5
    assert step_v == pytest.approx(0.05 * 2.0 * du * 0.5, abs=0.01)


@pytest.mark.skipif(not shutil.which("ngspice"), reason="needs ngspice")
def test_recovery_matches_ngspice(tmp_path):
    """Deterministic switch, one 22 V / 10 ms input pulse: after the flash the node voltage is within
    0.3 V of ngspice (ngspice keeps R_f, C_f and R_sense explicit; the model uses the Thevenin source)."""
    from plasma_rc.sim import pulse, spice, tran

    step_s = TPS * TICK_S
    k0 = 30
    t_s, v_s, _, _ = tran(spice(tmp_path, "tran 5u 0.8 0 5u", 77, 50e-6, va=pulse(22, t0=k0 * step_s, width=step_s)))
    levels = np.full(int(0.8 / step_s), 127, np.uint8)  # u = -0.004: 0.09 V input offset, below tolerance
    levels[k0] = 255
    _, tr = simulate(P, levels, TPS, OCR1A, np.random.default_rng(0), trace=True)
    after = (t_s > (k0 + 2) * step_s) & (t_s < 0.8)
    assert np.max(np.abs(np.interp(t_s[after], tr["t"], tr["v"]) - v_s[after])) < 0.3


def test_float_drive_equals_dac_levels():
    """Audio path: a float drive u in [-1, 1] gives the same run as the DAC levels it encodes."""
    levels = np.array([0, 255, 128, 40] * 5, np.uint8)
    a = simulate(P, levels, TPS, OCR1A, np.random.default_rng(3))
    b = simulate(P, (levels.astype(float) - 127.5) / 127.5, TPS, OCR1A, np.random.default_rng(3))
    assert np.array_equal(a.values, b.values) and np.array_equal(a.flash_tick, b.flash_tick)


def test_linear_lyapunov_equals_slowest_eigenvalue():
    """Bulb removed: twins with common noise converge at the slowest eigenvalue of the off-state
    matrix (Derived: linear system, d(t) ∝ exp(λ_max t) once the fast mode has decayed)."""
    p = dataclasses.replace(P, bulb=False, C_c=0.1e-6)
    A = np.array([[-(1 / p.R_th + 1 / p.Re) / p.C, 1 / (p.Re * p.C)], [1 / (p.Re * p.C_c), -1 / (p.Re * p.C_c)]])
    lam = conditional_lyapunov(p, xorshift32_levels(7, 150), TPS, OCR1A, seed=0, skip_s=0.2)
    assert lam["lambda"] == pytest.approx(max(np.linalg.eigvals(A).real), rel=0.02)


def test_ramp_overshoot_is_rate_times_delay():
    """Deterministic delay t_f, node ramping at r V/s: first flash at v = V_b + r t_f (Derived)."""
    p = dataclasses.replace(P, V_th=0.0, R_th=1e9, Re=1e3, C_c=1e3, C=1e-9, v_pk=100.0, t_f=2e-3)
    u = np.linspace(0.70, 0.80, 600)  # 70 -> 80 V in 0.1 s: r = 100 V/s
    cap, tr = simulate(p, u, 1, OCR1A, np.random.default_rng(0), trace=True)
    before = np.searchsorted(tr["t"], cap.flash_times_s()[0]) - 1  # last tick end before the strike
    assert tr["v"][before] == pytest.approx(p.V_b + 100.0 * 2e-3, abs=0.05)


def test_teensy_adc_scaling():
    """12-bit, 3.3 V reference: the linear step reads k_v v_pk du Rp/(Rp+Re) in 3.3/4096 V counts."""
    p = dataclasses.replace(P, bulb=False, v_pk=1.5, R_th=1e6, Re=1e6, C_c=10e-6, k_v=0.04, adc_bits=12, v_ref=3.3)
    levels = np.array([128] * 20 + [255] * 20, np.uint8)
    cap = simulate(p, levels, TPS, OCR1A, np.random.default_rng(0), channels="3")
    counts = cap.values.astype(float)
    step_v = (counts[30 * TPS:39 * TPS].mean() - counts[10 * TPS:19 * TPS].mean()) * 3.3 / 4096
    assert counts.max() > 1023 and step_v == pytest.approx(0.04 * 1.5 * (255 - 128) / 127.5 * 0.5, abs=0.005)


def test_existing_formative_law_can_fire_below_breakdown():
    """Document unresolved physics without silently adopting a cancellation law."""
    p = dataclasses.replace(P,V_th=70.,t_f=.05)
    drive = np.r_[np.zeros(10),np.ones(1),np.zeros(30)]
    cap,tr = simulate(p,drive,TPS,OCR1A,np.random.default_rng(0),trace=True)
    assert len(cap.flash_tick) == 1
    v = tr['v'][np.searchsorted(tr['t'],cap.flash_times_s()[0])]
    assert v < p.V_b
