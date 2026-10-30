"""Circuit A in ngspice and the ne2_uno firmware in simavr (tests and experiments/ne2/s1_sim_evidence.py).

Bulb = hysteretic switch (D-20, model hypothesis): strikes at v >= V_b (no breakdown delay),
conducts on v = V_m + r_on i_b, extinguishes when i_b < I_min, i.e. at v = V_e. Defaults are
NE-2AS datasheet values (lit. review [2], Cited): V_b 76 V avg (60 min, 90 max), maintaining
58 V at 0.3 mA, extinguishing >= 50 V. I_min is Unknown. PART values are illustrative.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from plasma_rc.circuit_checks import thevenin

V_B, V_E, V_OP, I_OP = 76.0, 50.0, 58.0, 0.3e-3
PART = dict(
    R_f=10e3, C_f=1e-6, Rs=1e6, C=10e-9, R_d=10e6, R_sense=1e3, Re=1e6, C_c=1e-6
)


def bulb(I_min: float, V_b: float = V_B) -> dict:
    """Switch-model parameters; the on-line runs through (V_e, I_min) and the datasheet point."""
    r_on = (V_OP - V_E) / (I_OP - I_min)
    return dict(V_b=V_b, V_e=V_E, I_min=I_min, r_on=r_on, V_m=V_E - r_on * I_min)


def spice(
    work: Path,
    analysis: str,
    V_s: float,
    I_min: float,
    V_b: float = V_B,
    va: str = "0",
    cc: str = "",
    **over,
) -> np.ndarray:
    """Run ngspice; columns per vector v(n), i(Vmm) = i_b, v(a): (x, y) for tran, (f, re, im) for ac."""
    p, b = {**PART, **over}, bulb(I_min, V_b)
    net = f"""* circuit A
Vs vs 0 {V_s}
Rf vs j {p["R_f"]}
Cf j 0 {p["C_f"]}
Rs j n {p["Rs"]}
C n 0 {p["C"]}
Rd n 0 {p["R_d"]}
S1 n b n sense bulb
.model bulb sw vt={(b["V_b"] + V_E) / 2} vh={(b["V_b"] - V_E) / 2} ron={b["r_on"]} roff=1e13
Vmm b sense {b["V_m"]}
Rsense sense 0 {p["R_sense"]}
{cc}Cc n a {p["C_c"]}
Re a src {p["Re"]}
Va src 0 {va}
.control
{analysis}
wrdata {work}/out.txt v(n) i(Vmm) v(a)
.endc
.end
"""
    (work / "c.cir").write_text(net)
    subprocess.run(
        ["ngspice", "-b", str(work / "c.cir")], check=True, capture_output=True
    )
    return np.loadtxt(work / "out.txt")


def tran(d: np.ndarray):
    return d[:, 0], d[:, 1], d[:, 3], d[:, 5]  # t, v(n), i_b, v(a)


def thev(V_s: float, **over) -> tuple[float, float]:
    p = {**PART, **over}
    return thevenin(V_s, p["R_f"] + p["Rs"], p["R_d"])


def pulse(amp: float, t0: float = 0.3, width: float = 0.01) -> str:
    return f"PWL(0 0 {t0} 0 {t0 + 1e-4} {amp} {t0 + width} {amp} {t0 + width + 1e-4} 0)"
