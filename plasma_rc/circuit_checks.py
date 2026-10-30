"""Circuit-A design conditions (technical.md §4, all Derived) as plain functions.

Voltages in V, resistances in Ω, currents in A, capacitances in F, times in s.
Primed quantities are the Thevenin values seen by the node with the divider R_d attached.
"""

from __future__ import annotations

import math


def thevenin(V_s: float, R_ch: float, R_d: float) -> tuple[float, float]:
    """V_s' and R_ch' of the supply branch loaded by the node divider R_d (D-31)."""
    return V_s * R_d / (R_ch + R_d), R_ch * R_d / (R_ch + R_d)


def supply_for(V_eff: float, R_ch: float, R_d: float) -> float:
    """Module voltage V_s that gives the node an open-circuit voltage V_eff."""
    return V_eff * (R_ch + R_d) / R_d


def rs_min(V_s_max: float, V_e: float, I_max: float) -> float:
    """Smallest series resistance that keeps the bulb current below I_max at full module output."""
    return (V_s_max - V_e) / I_max


def near_breakdown_window(V_b: float, V_e: float, I_min: float, R_eff: float) -> tuple[float, float] | None:
    """V_s' range: silent at rest (V_e < V_s' < V_b) and no latching ((V_s' - V_e)/R_eff < I_min).

    R_eff = R_ch' ∥ Re: right after a flash the coupling capacitor C_c, charged to V_s', feeds the
    node through Re as well as the supply through R_ch' (Derived; ngspice-checked).
    """
    lo, hi = V_e, min(V_b, V_e + I_min * R_eff)
    return (lo, hi) if hi > lo else None


def always_on_window(V_b: float, V_m: float, I_min: float, I_max: float, R_eff: float, r_on: float = 0.0) -> tuple[float, float] | None:
    """Affine bulb: V_m is the intercept, r_on includes sense resistance.

    r_on=0 is explicitly the constant-voltage approximation.
    """
    R_eff += r_on
    lo, hi = max(V_b, V_m + I_min * R_eff), V_m + I_max * R_eff
    return (lo, hi) if hi > lo else None


def mid_gain(Rs: float, Re: float) -> float:
    """Mid-band node gain of the input path with the bulb off: Rs / (Rs + Re)."""
    return Rs / (Rs + Re)


def droop(T_step: float, R: float, C_c: float) -> float:
    """Fractional droop of a held step through R·C_c, R = Re + Rs ∥ R_d (valid for R·C_c >> T_step)."""
    return T_step / (R * C_c)


def corner_hz(R: float, C: float) -> float:
    """First-order RC corner frequency 1 / (2π R C)."""
    return 1.0 / (2 * math.pi * R * C)
