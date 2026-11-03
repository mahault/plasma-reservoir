"""Checks for the actual acquisition stream used by the neon experiment."""
import numpy as np
import pytest

from plasma_rc.neon.records import Capture
from plasma_rc.neon.capture import RunConditions, channel_volts, extract_recorded_steps, save_recording, load_recording


def make_capture(dropped=0, v_ref=3.3):
    return Capture(ticks=np.arange(4), values=np.array([0, 2048, 1024, 4095]),
                   channels="12", flash_tick=np.array([], dtype=int),
                   flash_sub=np.array([], dtype=int), ocr1a=999, dropped=dropped,
                   clock_hz=1e6, adc_bits=12, v_ref=v_ref, source="physical")


def test_channel_samples_use_actual_adc_calibration_and_timestamps():
    t, v = channel_volts(make_capture(), "2")
    np.testing.assert_allclose(t, [0.001, 0.003])
    np.testing.assert_allclose(v, [1.65, 4095 * 3.3 / 4096])


def test_rejects_dropped_samples_and_missing_calibration():
    with pytest.raises(ValueError):
        channel_volts(make_capture(dropped=1), "1")
    with pytest.raises(ValueError):
        channel_volts(make_capture(v_ref=None), "1")


def test_led_is_not_mislabelled_as_neon_breakdown():
    with pytest.raises(ValueError, match="regime"):
        RunConditions(device="led", regime="near-breakdown", ballast_ohm=1000,
                      voltage_limit_v=5, current_limit_a=0.001)


def test_physical_run_requires_positive_current_limit():
    with pytest.raises(ValueError, match="current"):
        RunConditions(device="neon", regime="always-on", ballast_ohm=1e6,
                      voltage_limit_v=100, current_limit_a=0)


def test_recorded_step_features_use_measured_samples_and_flash_timing():
    cap = Capture(ticks=np.arange(8), values=np.array([100, 200, 300, 400, 200, 100, 400, 300]),
                  channels="12", flash_tick=np.array([1]), flash_sub=np.array([0]),
                  ocr1a=999, dropped=0, clock_hz=1e6, adc_bits=10, v_ref=1.024,
                  source="physical")
    x = extract_recorded_steps(cap, ticks_per_step=4, n_steps=2, light_pin="1", voltage_pin="2",
                               dark_voltage_v=0.0, divider_gain=10.0)
    # Light in sensor volts, ignition rate in Hz, within-step variation, bulb volts.
    np.testing.assert_allclose(x, [[0.2, 250, 0.1, 3.0], [0.3, 0, 0.1, 2.0]])


def test_recorded_steps_reject_empty_measurement_window():
    with pytest.raises(ValueError, match="sample"):
        extract_recorded_steps(make_capture(), ticks_per_step=1, n_steps=4, light_pin="1", voltage_pin="2",
                               dark_voltage_v=0.0, divider_gain=10.0)


def test_save_recording_keeps_input_and_capture_without_overwriting(tmp_path):
    capture = make_capture()
    conditions = RunConditions("led", "led", 1000, 5, 0.001)
    path = tmp_path / "trial.npz"
    save_recording(path, capture, conditions, np.array([0., 0.5]), ticks_per_step=2)
    with np.load(path, allow_pickle=False) as data:
        np.testing.assert_array_equal(data["input_u"], [0., 0.5])
        np.testing.assert_array_equal(data["values"], capture.values)
        assert int(data["ticks_per_step"]) == 2
    recovered, recovered_conditions, input_u, ticks_per_step = load_recording(path)
    np.testing.assert_array_equal(recovered.values, capture.values)
    assert recovered_conditions == conditions
    assert ticks_per_step == 2
    np.testing.assert_array_equal(input_u, [0., 0.5])
    with pytest.raises(FileExistsError):
        save_recording(path, capture, conditions, np.array([0., 0.5]), ticks_per_step=2)


def test_save_recording_rejects_unknown_or_corrupted_capture(tmp_path):
    conditions = RunConditions("led", "led", 1000, 5, 0.001)
    with pytest.raises(ValueError):
        save_recording(tmp_path / "trial.npz", make_capture(dropped=None), conditions,
                       np.array([0., 0.5]), ticks_per_step=2)
    assert not (tmp_path / "trial.npz").exists()


def test_save_recording_rejects_incomplete_step_stream(tmp_path):
    conditions = RunConditions("led", "led", 1000, 5, 0.001)
    with pytest.raises(ValueError, match="incomplete"):
        save_recording(tmp_path / "trial.npz", make_capture(), conditions,
                       np.array([0., 0.1, 0.2]), ticks_per_step=2)


def test_recording_preserves_bulb_and_ambient_metadata(tmp_path):
    conditions = RunConditions("neon", "near-breakdown", 1e6, 100, 0.001,
                               device_id="B1", temperature_c=22.0, warmup_s=60.0)
    path = tmp_path / "trial.npz"
    save_recording(path, make_capture(), conditions, np.array([0., 0.5]), 2)
    _, saved, _, _ = load_recording(path)
    assert saved.device_id == "B1"
    assert saved.temperature_c == 22.0
    assert saved.warmup_s == 60.0


def test_recording_rejects_missing_required_drive_channel(tmp_path):
    conditions = RunConditions("led", "led", 1000, 5, .001, drive_pin="0", light_pin="1", voltage_pin="2",
                               drive_gain=1, divider_gain=1, dark_voltage_v=0)
    with pytest.raises(ValueError, match="channel"):
        save_recording(tmp_path / "trial.npz", make_capture(), conditions, np.array([0., 0.5]), 2)
