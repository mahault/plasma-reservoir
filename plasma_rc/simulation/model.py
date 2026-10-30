"""Circuit A with a stochastic neon bulb: simulated UNO trials for the E4/E6 analysis (docs/simulation.md).

Circuit (technical.md §4, ngspice-checked): node v and coupling-capacitor voltage w = v - v_a,
supply V', R' (Thevenin, C_f taken as ideal), input v_in = v_pk * u through Re and C_c:
    C   dv/dt = (V' - v)/R' + (v_in - v + w)/Re - i_b
    C_c dw/dt = -(v_in - v + w)/Re
Bulb = hysteretic switch (D-20) plus breakdown delay: while v >= V_b, seed electrons appear at rate
    Y(tau) = Y_bg + Y_res * exp(-tau / tau_res),   tau = time since the last extinction,
(exponential statistical delay, Laue; residual charge from the last glow shortens it, the neon
"memory effect": Marković et al., Phys. Plasmas 14, 103504, 2007), followed by a Gaussian formative
time (Maluckov et al., Phys. Plasmas 11, 5328, 2004). On: i_b = (v - V_m)/r_on (r_on includes
R_sense) until v < V_e. Light is taken proportional to i_b (Inferred). Linear segments are
integrated exactly (matrix exponential), so dt only sets the event timing resolution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm

from plasma_rc.trials.capture import Capture

CPU_HZ = 16_000_000


@dataclass(frozen=True)
class NeonCircuit:
    V_th: float  # Thevenin node voltage V' [V]
    R_th: float  # Thevenin resistance R' [ohm]
    C: float  # node capacitor [F]
    C_c: float  # coupling capacitor [F]
    Re: float  # input resistor [ohm]
    v_pk: float  # input source peak for |u| = 1 [V]
    V_b: float  # breakdown voltage [V]
    V_e: float  # extinction voltage [V]
    V_m: float  # on-line intercept [V]
    r_on: float  # on-line slope incl. R_sense [ohm]
    Y_bg: float  # background seed-electron rate [1/s]; inf = no statistical delay
    Y_res: float  # residual-charge rate just after extinction [1/s]
    tau_res: float  # residual-charge decay time [s]
    t_f: float  # mean formative time [s]
    sigma_f: float  # formative time spread [s]
    g_light: float  # A1 volts per ampere of i_b (photodiode TIA, light ∝ i_b)
    g_i: float  # A2 volts per ampere (R_sense and its amplifier)
    k_v: float  # A3 volts per node volt (R_d2 / R_d)
    tau_aa: float  # anti-alias RC time constant [s]
    noise_counts: float  # ADC noise, standard deviation [counts]
    bulb: bool = True  # False: bulb removed (linear network control)
    adc_bits: int = 10  # ADC resolution: UNO 10, Teensy 4.1 12
    v_ref: float = 5.0  # ADC full scale [V]: UNO 5 V, Teensy 4.1 3.3 V


def _discrete(A: np.ndarray, b0: np.ndarray, bu: np.ndarray, dt: float):
    """Exact step x' = Phi x + c0 + cu * v_in for dx/dt = A x + b0 + bu * v_in."""
    phi = expm(A * dt)
    psi = np.linalg.solve(A, phi - np.eye(2))
    return phi, psi @ b0, psi @ bu


def simulate(
    p: NeonCircuit,
    drive: np.ndarray,
    tps: int,
    ocr1a: int,
    rng: np.random.Generator,
    oversample: int = 16,
    channels: str = "123",
    trace: bool = False,
    clock_hz: float = CPU_HZ,
    dv0: float = 0.0,
):
    """One run as the firmware records it: drive[k] held for tps ticks of (ocr1a + 1) / clock_hz s,
    one ADC sample per tick from tick 1 (round robin over channels), flash time stamps.
    drive: uint8 DAC levels, or float u in [-1, 1] (audio). Breakdown draws use their own stream
    seeded from rng, so two runs from equal seeds share all noise. dv0 offsets the initial node
    voltage. Returns a Capture (+ per-tick trace of t, v, w, i_b)."""
    drive = np.asarray(drive)
    if drive.ndim != 1 or not len(drive) or not np.isfinite(drive).all():
        raise ValueError("drive must be a nonempty finite vector")
    if (
        tps < 1
        or int(tps) != tps
        or oversample < 1
        or int(oversample) != oversample
        or clock_hz <= 0
        or not 0 <= ocr1a <= 65535
    ):
        raise ValueError("invalid simulation timing")
    if (
        not channels
        or set(channels) - set("123")
        or len(set(channels)) != len(channels)
    ):
        raise ValueError("simulation channels must be distinct pins 1..3")
    tick_dt = (ocr1a + 1) / clock_hz
    dt = tick_dt / oversample
    u = (
        (drive.astype(float) - 127.5) / 127.5
        if drive.dtype == np.uint8
        else np.asarray(drive, float)
    )
    ev = np.random.default_rng(rng.integers(2**63))
    A_off = np.array(
        [
            [-(1 / p.R_th + 1 / p.Re) / p.C, 1 / (p.Re * p.C)],
            [1 / (p.Re * p.C_c), -1 / (p.Re * p.C_c)],
        ]
    )
    b0_off, bu = (
        np.array([p.V_th / (p.R_th * p.C), 0.0]),
        np.array([1 / (p.Re * p.C), -1 / (p.Re * p.C_c)]),
    )
    A_on = A_off - np.array([[1 / (p.r_on * p.C), 0.0], [0.0, 0.0]])
    b0_on = b0_off + np.array([p.V_m / (p.r_on * p.C), 0.0])
    mats = {
        False: _discrete(A_off, b0_off, bu, dt),
        True: _discrete(A_on, b0_on, bu, dt),
    }

    n_ticks = (len(u) + 1) * tps
    order = [int(c) - 1 for c in channels]
    alpha = 1 - math.exp(-dt / p.tau_aa)
    v = w = p.V_th  # rest: C_c charged to V' with v_in = 0
    v += dv0
    lit, t_ext, need, acc, strike_at = False, -math.inf, ev.exponential(), 0.0, math.inf
    y = [0.0, 0.0, p.k_v * v]  # anti-aliased A1, A2, A3 [V]
    values, flash_t, tr, full = (
        np.empty(n_ticks - 1, dtype=np.uint16),
        [],
        [],
        2**p.adc_bits,
    )
    for tick in range(n_ticks - 1):
        k = tick // tps
        v_in = p.v_pk * u[k] if k < len(u) else 0.0
        for sub in range(oversample):
            P, c0, cu = mats[lit]
            v, w = (
                P[0, 0] * v + P[0, 1] * w + c0[0] + cu[0] * v_in,
                P[1, 0] * v + P[1, 1] * w + c0[1] + cu[1] * v_in,
            )
            t = (tick * oversample + sub + 1) * dt
            if lit and v < p.V_e:
                lit, t_ext, need, acc = False, t, ev.exponential(), 0.0
            elif not lit and p.bulb and v >= p.V_b and strike_at == math.inf:
                acc += (p.Y_bg + p.Y_res * math.exp(-(t - t_ext) / p.tau_res)) * dt
                if acc >= need:
                    strike_at = t + max(0.0, ev.normal(p.t_f, p.sigma_f))
            if strike_at <= t:
                lit, strike_at = True, math.inf
                flash_t.append(t)
            ib = (v - p.V_m) / p.r_on if lit else 0.0
            y[0] += alpha * (p.g_light * ib - y[0])
            y[1] += alpha * (p.g_i * ib - y[1])
            y[2] += alpha * (p.k_v * v - y[2])
        if trace:
            tr.append((t, v, w, ib))
        # State at the end of interval tick is sampled at nominal tick + 1.
        ch = order[tick % len(order)]
        values[tick] = min(
            full - 1,
            max(0, round(y[ch] * full / p.v_ref + rng.normal(0.0, p.noise_counts))),
        )
    cycles = np.rint(np.array(flash_t) * clock_hz).astype(np.int64)
    event_tick, event_sub = np.divmod(cycles, ocr1a + 1)
    cap = Capture(
        ticks=np.arange(1, n_ticks, dtype=np.int64),
        values=values,
        channels=channels,
        flash_tick=event_tick,
        flash_sub=event_sub,
        ocr1a=ocr1a,
        dropped=0,
        clock_hz=clock_hz,
        adc_bits=p.adc_bits,
        v_ref=p.v_ref,
        source="simulation",
    )
    if trace:
        t, vv, ww, ib = np.array(tr).T
        return cap, {"t": t, "v": vv, "w": ww, "ib": ib}
    return cap


def conditional_lyapunov(
    p: NeonCircuit,
    drive: np.ndarray,
    tps: int,
    ocr1a: int,
    seed: int,
    delta: float = 1e-3,
    skip_s: float = 0.0,
    oversample: int = 16,
    clock_hz: float = CPU_HZ,
    floor: float = 1e-10,
) -> dict:
    """Finite-time replica contraction diagnostic [1/s] of the driven circuit: two runs with the same drive
    and the same noise, initial node voltages delta apart (auxiliary-system idea: negative values show contraction over the fitted interval; they do not prove the echo state property). λ is the slope of
    ln d(t), d = |(Δv, Δw)| per tick, fitted from skip_s while d stays above floor."""
    a, b = (
        simulate(
            p,
            drive,
            tps,
            ocr1a,
            np.random.default_rng(seed),
            oversample,
            trace=True,
            clock_hz=clock_hz,
            dv0=d,
        )[1]
        for d in (0.0, delta)
    )
    d = np.hypot(b["v"] - a["v"], b["w"] - a["w"])
    use = a["t"] >= skip_s
    below = np.flatnonzero(use & (d <= floor))
    if below.size:
        use[below[0] :] = False
    t, logd = a["t"][use], np.log(d[use])
    if len(t) < 10:
        return {"lambda": float("nan"), "n_points": len(t), "jumps": 0}
    jumps = int(
        np.sum(np.diff(logd) > 1.0)
    )  # one twin flashed and the other not (threshold switch)
    return {
        "lambda": float(np.polyfit(t, logd, 1)[0]),
        "n_points": len(t),
        "jumps": jumps,
        "diagnostic": "finite-time log-distance slope",
        "t_start": float(t[0]),
        "t_end": float(t[-1]),
        "delta": delta,
    }
