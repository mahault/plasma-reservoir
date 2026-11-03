"""Decode calibrated acquisition channels."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile
from math import isfinite
import numpy as np


def load_recording(path):
    """Load a physical capture without allowing pickled data."""
    from plasma_rc.neon.records import Capture

    with np.load(path, allow_pickle=False) as data:
        conditions = RunConditions(**json.loads(str(data["conditions"])))
        capture = Capture(ticks=data["ticks"], values=data["values"], channels=str(data["channels"]),
                          flash_tick=data["flash_tick"], flash_sub=data["flash_sub"],
                          ocr1a=int(data["ocr1a"]), dropped=int(data["dropped"]),
                          clock_hz=float(data["clock_hz"]), adc_bits=int(data["adc_bits"]),
                          v_ref=float(data["v_ref"]), board=str(data["board"]), source=str(data["source"]))
        capture.require_integrity()
        return capture, conditions, data["input_u"].copy(), int(data["ticks_per_step"])


def save_recording(path, capture, conditions, input_u, ticks_per_step, *, seed=None, stimulus_command=None):
    """Atomically save raw physical samples and commanded benchmark input."""
    capture.require_integrity()
    if capture.source != "physical" or capture.adc_bits is None or capture.v_ref is None:
        raise ValueError("physical capture and ADC calibration are required")
    if not isinstance(conditions, RunConditions):
        raise ValueError("run conditions are required")
    if conditions.drive_pin is not None and not {conditions.drive_pin, conditions.light_pin,
                                                 conditions.voltage_pin}.issubset(capture.channels):
        raise ValueError("capture is missing a required channel")
    u = np.asarray(input_u, dtype=float)
    if (u.ndim != 1 or not len(u) or not np.isfinite(u).all() or np.any((u < 0) | (u > 0.5))
            or not isinstance(ticks_per_step, int) or ticks_per_step <= 0):
        raise ValueError("invalid commanded input or step timing")
    if not len(capture.ticks) or capture.ticks[-1] < len(u) * ticks_per_step - 1:
        raise ValueError("incomplete input-step capture")
    path = Path(path)
    if path.suffix != ".npz":
        raise ValueError("recording path must end in .npz")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".capture-", delete=False) as temp:
            temp_name = temp.name
            np.savez(temp, ticks=capture.ticks, values=capture.values, channels=capture.channels,
                     flash_tick=capture.flash_tick, flash_sub=capture.flash_sub, ocr1a=capture.ocr1a,
                     clock_hz=capture.clock_hz, dropped=capture.dropped, adc_bits=capture.adc_bits,
                     v_ref=capture.v_ref, board=capture.board, source=capture.source,
                     conditions=json.dumps(asdict(conditions)), input_u=u, ticks_per_step=ticks_per_step,
                     seed=seed if seed is not None else -1, stimulus_command=stimulus_command or "")
        os.link(temp_name, path)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def extract_recorded_steps(capture, ticks_per_step, n_steps, light_pin, voltage_pin, dark_voltage_v, divider_gain):
    """Per-step light sensor volts, flash rate, light variation and bulb volts.

    Divider gain is measured bulb-volts per ADC-pin volt. Flash events require
    a correctly configured and calibrated hardware comparator.
    """
    if (not isinstance(ticks_per_step, int) or ticks_per_step <= 0 or
            not isinstance(n_steps, int) or n_steps <= 0 or light_pin == voltage_pin or
            not isfinite(dark_voltage_v) or not isfinite(divider_gain) or divider_gain <= 0):
        raise ValueError("invalid step timing or channel calibration")
    light_t, light = channel_volts(capture, light_pin)
    voltage_t, voltage = channel_volts(capture, voltage_pin)
    light_step = np.rint(light_t * capture.tick_hz).astype(int) // ticks_per_step
    voltage_step = np.rint(voltage_t * capture.tick_hz).astype(int) // ticks_per_step
    event_step = capture.flash_tick // ticks_per_step
    rows = []
    for k in range(n_steps):
        light_values = light[light_step == k] - dark_voltage_v
        voltage_values = voltage[voltage_step == k] * divider_gain
        if not len(light_values) or not len(voltage_values):
            raise ValueError(f"missing sensor sample in step {k}")
        frequency = np.count_nonzero(event_step == k) * capture.tick_hz / ticks_per_step
        rows.append((light_values.mean(), frequency, light_values.std(), voltage_values.mean()))
    return np.asarray(rows)


@dataclass(frozen=True)
class RunConditions:
    device: str
    regime: str
    ballast_ohm: float
    voltage_limit_v: float
    current_limit_a: float
    device_id: str = "unknown"
    temperature_c: float | None = None
    warmup_s: float | None = None
    drive_pin: str | None = None
    light_pin: str | None = None
    voltage_pin: str | None = None
    drive_gain: float | None = None
    divider_gain: float | None = None
    dark_voltage_v: float | None = None

    def __post_init__(self):
        regimes = {"neon": {"near-breakdown", "always-on"}, "led": {"led"}}
        if self.device not in regimes or self.regime not in regimes[self.device]:
            raise ValueError("device and regime do not match")
        for name in ("ballast_ohm", "voltage_limit_v", "current_limit_a"):
            value = getattr(self, name)
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not self.device_id.strip():
            raise ValueError("device ID is required")
        if self.temperature_c is not None and not isfinite(self.temperature_c):
            raise ValueError("temperature must be finite or unknown")
        if self.warmup_s is not None and (not isfinite(self.warmup_s) or self.warmup_s < 0):
            raise ValueError("warm-up must be nonnegative or unknown")
        calibration = (self.drive_pin, self.light_pin, self.voltage_pin,
                       self.drive_gain, self.divider_gain, self.dark_voltage_v)
        if any(v is not None for v in calibration):
            if any(v is None for v in calibration):
                raise ValueError("all channel mappings and gains must be supplied together")
            pins = (self.drive_pin, self.light_pin, self.voltage_pin)
            if len(set(pins)) != 3 or set(pins) - set("01234"):
                raise ValueError("recorded pins must be distinct ADC channels")
            if (not isfinite(self.drive_gain) or self.drive_gain <= 0 or
                    not isfinite(self.divider_gain) or self.divider_gain <= 0 or not isfinite(self.dark_voltage_v)):
                raise ValueError("invalid channel calibration")


def channel_volts(capture, pin):
    """Return sample times and calibrated ADC-pin voltage, not bulb voltage."""
    capture.require_integrity()
    if capture.adc_bits is None or capture.v_ref is None or pin not in capture.channels:
        raise ValueError("ADC calibration and a recorded channel are required")
    ticks, values = capture.channel(pin)
    return ticks / capture.tick_hz, values.astype(float) * capture.v_ref / (2 ** capture.adc_bits)
