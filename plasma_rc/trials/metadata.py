"""Operator metadata; model-equivalent voltage is stored separately in setup."""

from dataclasses import dataclass

REGIMES = ("near-breakdown", "always-on")
CONTROLS = ("none", "resistor", "audio-only")


@dataclass
class RunMeta:
    bulb_id: str
    regime: str
    control: str
    temperature_C: float
    warmup_min: float
    V_s_measured: float | None
    jumpers: str
    repeat: int

    def __post_init__(self):
        if not self.bulb_id.strip():
            raise ValueError("bulb_id is required")
        if self.regime not in REGIMES:
            raise ValueError(f"regime must be one of {REGIMES}")
        if self.control not in CONTROLS:
            raise ValueError(f"control must be one of {CONTROLS}")
