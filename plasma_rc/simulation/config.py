"""Explicit immutable simulation settings; all device values are illustrative assumptions.

V_b/V_e and the 58 V / 0.3 mA operating point follow the existing NE-2AS source;
breakdown rates, I_min, stray capacitance and readout noise are uncalibrated.
"""

from dataclasses import asdict, dataclass
from types import MappingProxyType
import math
import numpy as np
from plasma_rc.circuit_checks import thevenin
from .model import NeonCircuit, simulate


@dataclass(frozen=True)
class AcquisitionProfile:
    board: str
    clock_hz: float
    ocr1a: int
    tps: int
    oversample: int
    adc_bits: int
    v_ref: float
    v_pk: float
    g_light: float
    g_i: float
    k_v: float
    tau_aa: float
    noise_counts: float

    @property
    def adc(self):
        return {
            k: getattr(self, k)
            for k in (
                "adc_bits",
                "v_ref",
                "v_pk",
                "g_light",
                "g_i",
                "k_v",
                "tau_aa",
                "noise_counts",
            )
        }


UNO = AcquisitionProfile(
    "uno", 16e6, 2665, 120, 16, 10, 5.0, 2.5, 4000.0, 4000.0, 0.05, 0.53e-3, 1.0
)
TEENSY41 = AcquisitionProfile(
    "teensy41", 600e6, 24999, 480, 4, 12, 3.3, 1.65, 3000.0, 3000.0, 0.04, 0.1e-3, 6.0
)
PROFILES = MappingProxyType({"uno": UNO, "teensy41": TEENSY41})
SEED0 = 20261024
I_MIN, V_B, V_E, V_OP, I_OP = 50e-6, 76.0, 50.0, 58.0, 0.3e-3
CONDITIONS = MappingProxyType(
    {
        "linear": MappingProxyType({"bulb": False}),
        "switch": MappingProxyType(
            {"Y_bg": math.inf, "Y_res": 0.0, "t_f": 0.0, "sigma_f": 0.0}
        ),
        "delay": MappingProxyType({"Y_res": 0.0}),
        "delay+memory": MappingProxyType({}),
    }
)


def circuit(margin=0.5, I_min=I_MIN, C_c=1e-6, profile=None, **over) -> NeonCircuit:
    """Base design: rest point `margin` V below V_b; components illustrative, latching margin < 1 (§4.1)."""
    profile = profile or TEENSY41
    R_th = thevenin(1.0, 10e3 + 2.2e6, 10e6)[1]  # R_f 10k + Rs 2.2M, divider R_d 10M
    r_on = (V_OP - V_E) / (
        I_OP - I_min
    )  # on-line through (V_e, I_min) and (58 V, 0.3 mA)
    base = dict(
        V_th=V_B - margin,
        R_th=R_th,
        C=10e-9,
        C_c=C_c,
        Re=2.2e6,
        V_b=V_B,
        V_e=V_E,
        V_m=V_E - r_on * I_min,
        r_on=r_on + 1e3,  # + R_sense 1k
        Y_bg=10.0,  # Unknown: dark-box seed rate, mean statistical delay 100 ms
        Y_res=1e5,  # Unknown: seed rate just after a glow (10 µs mean delay)
        tau_res=0.3,  # residual decay "hundreds of ms" in neon at 6.6 mbar (Marković 2007), not NE-2
        t_f=10e-6,
        sigma_f=2e-6,  # Unknown: formative time, Gaussian (Maluckov 2004)
        **profile.adc,
    )  # DAC swing and readout design
    return NeonCircuit(**{**base, **over})


@dataclass(frozen=True)
class SimulationSetup:
    circuit: NeonCircuit
    profile: AcquisitionProfile
    seed: int
    oversample: int | None = None

    def metadata(self):
        return {
            "circuit": asdict(self.circuit),
            "acquisition": asdict(self.profile),
            "seed": self.seed,
            "oversample": self.oversample or self.profile.oversample,
        }

    def run(self, drive, ticks_per_step=None, **kwargs):
        cap = simulate(
            self.circuit,
            drive,
            ticks_per_step or self.profile.tps,
            self.profile.ocr1a,
            np.random.default_rng(self.seed),
            self.oversample or self.profile.oversample,
            clock_hz=self.profile.clock_hz,
            **kwargs,
        )
        cap.board = self.profile.board
        return cap
