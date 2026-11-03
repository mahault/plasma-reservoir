"""Verify the minimal circuit against independent load-line calculations."""
import shutil

import numpy as np
import pytest

from plasma_rc.neon.config import StudyConfig
from plasma_rc.neon.spice import NeonSwitch, LED, run_transient
from plasma_rc.neon.analysis import conditional_contraction

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice required")


def test_open_circuit_step_has_analytic_rc_response(tmp_path):
    config = StudyConfig(ballast_ohm=1e6, parasitic_capacitance_f=1e-9)
    trace = run_transient(config, [(0, 0), (1e-6, 10)], 0.01, 1e-5, tmp_path / "run", bulb="open")
    # At 1 ms after the ramp, the off-state response is 10*(1-exp(-1)).
    actual = np.interp(0.001001, trace.time_s, trace.voltage_v)
    assert actual == pytest.approx(10 * (1 - np.exp(-1)), abs=0.02)
    assert np.max(np.abs(trace.current_a)) < 1e-15


def test_resistor_control_obeys_load_line(tmp_path):
    config = StudyConfig(ballast_ohm=1e6, parasitic_capacitance_f=1e-9)
    trace = run_transient(config, [(0, 10), (0.01, 10)], 0.01, 1e-5, tmp_path / "run",
                          bulb="resistor", control_resistance_ohm=1e6)
    assert trace.voltage_v[-1] == pytest.approx(5, abs=0.01)
    assert trace.current_a[-1] == pytest.approx(5e-6, rel=0.005)


def test_existing_output_directory_is_not_overwritten(tmp_path):
    config = StudyConfig(ballast_ohm=1e6, parasitic_capacitance_f=1e-9)
    path = tmp_path / "existing"
    path.mkdir()
    with pytest.raises(FileExistsError):
        run_transient(config, [(0, 0), (1, 0)], 1, 0.001, path, bulb="open")


def test_switch_strikes_sustains_and_extinguishes(tmp_path):
    config = StudyConfig(ballast_ohm=1e6, parasitic_capacitance_f=1e-9)
    # These are hypothetical test values, not measured lamp parameters.
    model = NeonSwitch(strike_v=75, extinction_v=52, intercept_v=50, on_resistance_ohm=100e3)
    drive = [(0, 0), (0.0001, 90), (0.005, 90), (0.0051, 40), (0.01, 40)]
    trace = run_transient(config, drive, 0.01, 1e-6, tmp_path / "run", bulb=model)
    assert np.interp(0.004, trace.time_s, trace.voltage_v) == pytest.approx(53.63636, abs=0.05)
    assert np.interp(0.004, trace.time_s, trace.current_a) == pytest.approx(36.36e-6, rel=0.01)
    assert abs(np.interp(0.009, trace.time_s, trace.current_a)) < 1e-12
    assert np.interp(0.009, trace.time_s, trace.voltage_v) == pytest.approx(40, abs=0.3)


def test_switch_waveform_converges_when_timestep_is_halved(tmp_path):
    config = StudyConfig(ballast_ohm=1e6, parasitic_capacitance_f=1e-9)
    model = NeonSwitch(75, 52, 50, 100e3)
    drive = [(0, 0), (0.0001, 90), (0.005, 90), (0.0051, 40), (0.01, 40)]
    coarse = run_transient(config, drive, 0.01, 2e-6, tmp_path / "coarse", bulb=model)
    fine = run_transient(config, drive, 0.01, 1e-6, tmp_path / "fine", bulb=model)
    def strike_time(trace):
        return trace.time_s[np.flatnonzero(trace.current_a > 1e-6)[0]]
    assert abs(strike_time(coarse) - strike_time(fine)) < 5e-6
    assert np.interp(0.004, coarse.time_s, coarse.voltage_v) == pytest.approx(
        np.interp(0.004, fine.time_s, fine.voltage_v), abs=0.05
    )


def test_continuously_lit_linear_branch_contracts_at_analytic_rate(tmp_path):
    config = StudyConfig(ballast_ohm=1e6, parasitic_capacitance_f=1e-9)
    model = NeonSwitch(75, 52, 50, 100e3)
    reference = [(0, 0), (0.0001, 90), (0.01, 90)]
    perturbed = [(0, 0), (0.0001, 90), (0.004, 90), (0.0041, 91),
                 (0.006, 91), (0.0061, 90), (0.01, 90)]
    a = run_transient(config, reference, 0.01, 1e-6, tmp_path / "a", bulb=model)
    b = run_transient(config, perturbed, 0.01, 1e-6, tmp_path / "b", bulb=model)
    rate = conditional_contraction(a, b, start_s=0.00612, end_s=0.0066)
    # -(1/Rballast + 1/Ron)/C = -11000 per second.
    assert rate == pytest.approx(-11000, rel=0.03)


def test_led_control_draws_forward_current_with_its_own_low_voltage_drive(tmp_path):
    config = StudyConfig(ballast_ohm=1000, parasitic_capacitance_f=1e-9)
    led = LED(saturation_current_a=1e-18, ideality=2, max_drive_v=5)
    trace = run_transient(config, [(0, 0), (0.001, 3.3), (0.01, 3.3)], 0.01, 1e-5,
                          tmp_path / "led", bulb=led)
    assert 0 < trace.current_a[-1] < 0.0033
    assert 0 < trace.voltage_v[-1] < 3.3


def test_led_control_rejects_neon_voltage(tmp_path):
    config = StudyConfig(ballast_ohm=1000, parasitic_capacitance_f=1e-9)
    led = LED(saturation_current_a=1e-18, ideality=2, max_drive_v=5)
    with pytest.raises(ValueError, match="LED drive"):
        run_transient(config, [(0, 0), (0.001, 90)], 0.01, 1e-5, tmp_path / "led", bulb=led)
    assert not (tmp_path / "led").exists()
