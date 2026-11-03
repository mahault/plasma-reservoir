"""CLI contract exercised with a synthetic board, never real hardware."""
import numpy as np

from experiments import neon_acquire as neon
from plasma_rc.neon.capture import load_recording
from plasma_rc.neon.records import Capture


def test_cli_records_device_metadata_and_commanded_input(tmp_path, monkeypatch):
    class FakeBoard:
        clock_hz = 1e6
        v_ref = None
        def configure(self, period, channels):
            self.period, self.channels = period, channels
        def start(self, command):
            self.command = command
        def stop(self):
            return Capture(np.arange(1, 29), np.arange(28), self.channels, np.array([], dtype=int),
                           np.array([], dtype=int), self.period, 0, clock_hz=self.clock_hz,
                           adc_bits=12, v_ref=self.v_ref, board="fake", source="physical")
        def close(self):
            pass
    fake = FakeBoard()
    monkeypatch.setattr(neon, "open_board", lambda port: fake)
    monkeypatch.setattr("time.sleep", lambda _: None)
    dest = tmp_path / "trial.npz"
    neon.main([str(dest), "--port", "fake", "--device", "led", "--regime", "led",
               "--device-id", "LED1", "--ballast", "1000", "--voltage-limit", "5",
               "--current-limit", "0.001", "--adc-ref", "3.3", "--temperature", "22",
               "--warmup", "60", "--timer", "999", "--channels", "012", "--ticks-per-step", "7",
               "--drive-pin", "0", "--light-pin", "1", "--voltage-pin", "2",
               "--drive-gain", "2", "--divider-gain", "10", "--dark-voltage", "0.02",
               "--steps", "4", "--seed", "1"])
    _, meta, u, _ = load_recording(dest)
    assert meta.device_id == "LED1" and meta.temperature_c == 22
    assert meta.drive_pin == "0" and meta.drive_gain == 2 and meta.divider_gain == 10 and meta.dark_voltage_v == 0.02
    assert len(u) == 4
    assert fake.command == "STEPS,0,0,1,4,7"


def test_cli_rejects_insufficient_samples_before_opening_board(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(neon, "open_board", lambda port: pytest.fail("must reject before opening"))
    with pytest.raises(SystemExit):
        neon.main([str(tmp_path / "trial.npz"), "--port", "fake", "--device", "led", "--regime", "led",
                   "--device-id", "L1", "--ballast", "1000", "--voltage-limit", "5", "--current-limit", "0.001",
                   "--adc-ref", "3.3", "--temperature", "22", "--warmup", "60", "--timer", "999",
                   "--channels", "012", "--ticks-per-step", "3", "--steps", "4", "--seed", "1",
                   "--drive-pin", "0", "--light-pin", "1", "--voltage-pin", "2", "--drive-gain", "1",
                   "--divider-gain", "1", "--dark-voltage", "0"])
