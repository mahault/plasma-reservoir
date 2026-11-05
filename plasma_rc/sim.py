"""Event-driven simulation of the minimal circuit (research doc §4.2), for circuit and analysis checks only (SIM-01).

State: driver output V_D (first-order pole tau_drv; 0 = ideal) and node voltage v at N2.
    dV_D/dt = (V_cmd - V_D)/tau_drv
    C_s dv/dt = (V_D - v)/R_B' - v/R_d - s·(v - V_m)/(r_on + R_S),   s ∈ {0, 1}
Lamp: hysteretic switch. Off -> on a strike delay t_d after v rises through V_b (cancelled if v has fallen
below V_b by then); on -> off when i_L = (v - V_m)/(r_on + R_S) falls below I_x. The lamp has no afterglow
kinetics: with iid_delay it is the history-independent-delay N-A surrogate (with hysteresis and timer state) (NULL-01).
Integration: scipy solve_ivp (Radau, exact Jacobian) between events, with terminal event detection.
"""
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp


@dataclass
class Trace:
    t: np.ndarray        # (n_steps, M) sample times [s]
    v_d: np.ndarray      # driver output [V]
    v: np.ndarray        # node N2 voltage [V]
    v_s: np.ndarray      # sense voltage R_S·i_L [V]
    flashes: np.ndarray  # strike times [s]
    edges: np.ndarray    # (n_steps + 1,) step boundaries [s]


def iid_delay(t_f, t_s_mean):
    """Strike delay independent of history: formative t_f plus exponential statistical delay [s]."""
    return lambda rest_s, rng: t_f + (rng.exponential(t_s_mean) if t_s_mean > 0 else 0.0)


def rest_dependent_delay(t_f, t_s, tau_mem):
    """HYPOTHETICAL memory lamp for validating the analysis only: delay grows with rest time
    (direction as in lab-tube memory curves, Spasić et al. 2003); not an NE-2H model."""
    return lambda rest_s, rng: t_f + t_s * (1.0 - np.exp(-rest_s / tau_mem))


def afterglow_delay(t_f, t_s, tau_mem, scale=1.0):
    """HYPOTHETICAL memory lamp for validating the analysis only (fresh instance per run): each discharge adds
    one unit to an afterglow variable a that decays with tau_mem during rests; delay = t_f + t_s·exp(-a/scale).
    Memory spans many flashes, unlike rest_dependent_delay. Not an NE-2H model."""
    a = [0.0]

    def delay(rest_s, rng):
        a[0] *= np.exp(-rest_s / tau_mem)
        d = t_f + t_s * np.exp(-a[0] / scale)
        a[0] += 1.0
        return d
    return delay


def simulate(cfg, x, t_step, samples_per_step, delay, seed, rtol=1e-8, v0=0.0):
    """Drive held levels x[k] in [0, 1] for t_step[k] seconds (scalar = equal steps); sample M points
    at the midpoints of M equal sub-intervals of each step. v0: initial node voltage (twin-trajectory
    divergence uses two nearby values with the same seed)."""
    c = lambda name: cfg.get("circuit", name)  # noqa: E731
    rb, rd, rs, cs, tau = c("R_B") + c("Z_o"), c("R_d"), c("R_S"), c("C_s"), c("tau_drv")
    v_b, v_m, i_x = cfg.get("lamp", "V_b"), cfg.get("lamp", "V_m"), cfg.get("lamp", "I_x")
    r_lit = cfg.get("lamp", "r_on") + rs
    v_on = v_b * (1 - 1e-9)  # event root lands within solver tolerance of V_b
    rng = np.random.default_rng(seed)
    n, m = len(x), samples_per_step
    edges = np.concatenate([[0.0], np.cumsum(np.broadcast_to(t_step, n))])
    t_samp = edges[:-1, None] + np.diff(edges)[:, None] * (np.arange(m) + 0.5) / m
    out = np.zeros((3, n, m))  # V_D, v, lamp state
    y = np.array([cfg.drive(x[0]), float(v0)])
    lit, pending, last_off, flashes = False, None, 0.0, []

    def rhs(t, y, v_cmd, s):
        dvd = (v_cmd - y[0]) / tau if tau > 0 else 0.0
        return [dvd, ((y[0] - y[1]) / rb - y[1] / rd - s * (y[1] - v_m) / r_lit) / cs]

    def jac(t, y, v_cmd, s):
        return [[-1 / tau if tau > 0 else 0.0, 0.0], [1 / (rb * cs), -(1 / rb + 1 / rd + s / r_lit) / cs]]

    def strike(t, y, v_cmd, s):
        return y[1] - v_b
    strike.terminal, strike.direction = True, 1

    def extinguish(t, y, v_cmd, s):
        return (y[1] - v_m) / r_lit - i_x
    extinguish.terminal, extinguish.direction = True, -1

    for k in range(n):
        v_cmd, t0, t_end = cfg.drive(x[k]), edges[k], edges[k + 1]
        if tau == 0:
            y[0] = v_cmd
        while t0 < t_end:
            if not lit and pending is None and y[1] >= v_on:
                pending = t0 + delay(t0 - last_off, rng)
            if pending is not None and pending <= t0:   # strike delay elapsed
                if y[1] >= v_on:
                    lit = True
                    flashes.append(t0)
                pending = None
                continue
            stop = min(t_end, pending) if pending is not None else t_end
            events = [extinguish] if lit else ([] if pending is not None else [strike])
            sol = solve_ivp(rhs, (t0, stop), y, method="Radau", jac=jac, events=events,
                            args=(v_cmd, int(lit)), rtol=rtol, atol=1e-9, dense_output=True)
            t1 = sol.t[-1]
            inside = (t_samp[k] >= t0) & (t_samp[k] < t1) if t1 < t_end else (t_samp[k] >= t0)
            if inside.any():
                out[:2, k, inside] = sol.sol(t_samp[k][inside])
            out[2, k, inside] = lit
            y, t0 = sol.y[:, -1].copy(), t1
            if sol.status == 1 and lit:
                lit, last_off = False, t1
            elif sol.status == 1:
                pending = t1 + delay(t1 - last_off, rng)
    v_d, v, s = out
    return Trace(t_samp, v_d, v, s * rs * (v - v_m) / r_lit, np.asarray(flashes), edges)
