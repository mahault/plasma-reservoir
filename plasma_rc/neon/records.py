"""Validated samples and event times, independent of hardware transport."""

from dataclasses import dataclass
import numpy as np


@dataclass
class Capture:
    ticks: np.ndarray
    values: np.ndarray
    channels: str
    flash_tick: np.ndarray
    flash_sub: np.ndarray
    ocr1a: int
    dropped: int | None
    clock_hz: float = 16_000_000
    adc_bits: int | None = None
    v_ref: float | None = None
    board: str = "unknown"
    source: str = "unknown"

    def __post_init__(self):
        for name in ("ticks", "values", "flash_tick", "flash_sub"):
            a = np.asarray(getattr(self, name))
            if (
                a.ndim != 1
                or not np.isfinite(a).all()
                or (a < 0).any()
                or (a != np.floor(a)).any()
            ):
                raise ValueError(f"{name} must be a finite nonnegative integer vector")
            setattr(self, name, a)
        if len(self.ticks) != len(self.values) or len(self.flash_tick) != len(
            self.flash_sub
        ):
            raise ValueError("sample/event array lengths differ")
        if (
            not self.channels
            or len(set(self.channels)) != len(self.channels)
            or set(self.channels) - set("01234")
        ):
            raise ValueError("channels must be distinct pins 0..4")
        if (
            not np.isfinite(self.clock_hz)
            or self.clock_hz <= 0
            or not 0 <= self.ocr1a <= 65535
            or int(self.ocr1a) != self.ocr1a
        ):
            raise ValueError("invalid timer clock or period")
        if (np.diff(self.ticks.astype(float)) <= 0).any() or (
            self.flash_sub > self.ocr1a
        ).any():
            raise ValueError("unordered samples or noncanonical flash subticks")
        if (np.diff(self.flash_times_s()) < 0).any():
            raise ValueError("unordered flash events")
        if self.dropped is not None and (
            self.dropped < 0 or int(self.dropped) != self.dropped
        ):
            raise ValueError("invalid dropped count")
        if self.adc_bits is not None and (
            int(self.adc_bits) != self.adc_bits or not 1 <= self.adc_bits <= 16
        ):
            raise ValueError("invalid ADC bit depth")
        if (self.values >= 2 ** (self.adc_bits or 16)).any():
            raise ValueError("samples exceed ADC range")
        if self.v_ref is not None and (not np.isfinite(self.v_ref) or self.v_ref <= 0):
            raise ValueError("invalid ADC reference")
        if self.source not in ("unknown", "physical", "simulation"):
            raise ValueError("unknown capture source")

    @property
    def tick_hz(self):
        return self.clock_hz / (self.ocr1a + 1)

    def channel(self, pin):
        # Acquisition starts with the first configured channel, including when tick0=1.
        phase = (
            (self.ticks - self.ticks[0]) % len(self.channels)
            if len(self.ticks)
            else self.ticks
        )
        mask = np.array(list(self.channels))[phase.astype(int)] == pin
        return self.ticks[mask], self.values[mask]

    def flash_times_s(self):
        return (
            self.flash_tick.astype(float) * (self.ocr1a + 1) + self.flash_sub
        ) / self.clock_hz

    def require_integrity(self, allow_legacy=False):
        if self.dropped not in (0, None) or (self.dropped is None and not allow_legacy):
            raise ValueError(
                "dropped data or unknown legacy integrity; use allow_legacy for unknown records"
            )
        if (
            self.source in ("physical", "simulation")
            and len(self.ticks)
            and self.ticks[0] not in (0, 1)
        ):
            raise ValueError("missing initial sample origin")
        if len(self.ticks) > 1 and not np.all(np.diff(self.ticks) == 1):
            raise ValueError("missing sample ticks")
