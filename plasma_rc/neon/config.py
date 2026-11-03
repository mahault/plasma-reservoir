"""Circuit configuration."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class StudyConfig:
    ballast_ohm: float
    parasitic_capacitance_f: float

    def __post_init__(self):
        if not isfinite(self.ballast_ohm) or self.ballast_ohm <= 0:
            raise ValueError("ballast resistance must be finite and positive")
        if not isfinite(self.parasitic_capacitance_f) or self.parasitic_capacitance_f <= 0:
            raise ValueError("parasitic capacitance must be finite and positive")
