"""S3: at what voltage does one NE-2 light? Simulated slow-ramp breakdown test (bench M1).

The supply ramps through R_f + Rs into the node (C in, divider R_d to ground) and the node voltage at
the first flash is read: the apparent breakdown voltage V_app. In the model the static V_b is an input
(datasheet 76 V avg [2]); what the ramp shows is how a measurement departs from it. With an
exponential statistical delay (seed rate Y) and formative time t_f, a node rising at r V/s overshoots:
    E[V_app] - V_b = r (1/Y + t_f),   std(V_app) = r / Y          (Derived, docs/system_guide.md M3)
(a) ramp rate x seed rate Y_bg (light level), no memory;  (b) memory curve: breakdown delay t_d after
a step to 78 V vs afterglow time tau since the last glow (Y_res, tau_res from S2; the measurement
of Marković et al. 2007 in lab neon). 5 seeds x 8 ramps per point.
Mapping onto simulate(): the input branch carries the supply (C_c = 1000 F, a short), Re = R_f + Rs,
R_th = R_d to ground (V_th = 0).
"""

from __future__ import annotations

import json
from multiprocessing import Pool

import numpy as np
from experiments.ne2.common import RESULTS
from plasma_rc.simulation.config import PROFILES, SEED0, circuit

from plasma_rc.bulb_model import simulate

B = PROFILES["teensy41"]
TICK_S = (B.ocr1a + 1) / B.clock_hz
R_D, R_CH, V_PK = 10e6, 2.21e6, 150.0
K = R_D / (R_D + R_CH)  # node / supply in DC
START, TOP, REST_V, V_STEP = (
    75.0,
    95.0,
    60.0,
    78.0,
)  # node volts: ramp start, supply limit, rest (off), step
RATES = [0.1, 1.0, 10.0, 100.0]  # node ramp rate [V/s]
Y_BGS = [1.0, 10.0, 100.0, 1000.0]  # seed-electron rate [1/s]: dark -> lit
RESTS = [1e-3, 3e-3, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0]  # rest after a glow [s]
SEEDS, RAMPS = 5, 8


def ramp_circuit(**over):
    return circuit(V_th=0.0, R_th=R_D, Re=R_CH, C_c=1e3, v_pk=V_PK, **over)


def node_drive(segments) -> np.ndarray:
    """Per-tick drive u from (duration_s, v_from, v_to) node-voltage segments (linear in each)."""
    parts = [
        np.linspace(a, b, max(1, round(d / TICK_S)), endpoint=False)
        for d, a, b in segments
    ]
    return np.concatenate(parts) / K / V_PK


def run(p, segments, seed: int):
    """Flash times [s] and per-tick trace for one node-voltage programme."""
    cap, tr = simulate(
        p,
        node_drive(segments),
        1,
        B.ocr1a,
        np.random.default_rng(seed),
        B.oversample,
        channels="3",
        trace=True,
        clock_hz=B.clock_hz,
    )
    return cap.flash_times_s(), tr


def rate_point(args) -> dict:
    """Node voltage just before the first strike of each ramp (nan: never lit)."""
    r, y, seed = args
    p = ramp_circuit(Y_bg=y, Y_res=0.0)
    span = (
        (p.V_b - START) + 6 * r * (1 / y + p.t_f) + 0.5
    )  # to 6 mean overshoots above V_b
    ramp_s = min(span, TOP - START) / r
    end = START + r * ramp_s  # hold there: the node lags by r (R'C) and
    segs = [
        (0.05, START, START),
        (ramp_s, START, end),
        (6 / y + 0.1, end, end),
    ]  # the strike may still wait
    v = []
    for i in range(RAMPS):
        t, tr = run(p, segs, SEED0 + 1000 * seed + i)
        v.append(
            float(tr["v"][np.searchsorted(tr["t"], t[0]) - 1])
            if len(t)
            else float("nan")
        )
    return {"rate": r, "Y_bg": y, "seed": seed, "v_app": v}


def rest_point(args) -> dict:
    """Memory curve: glow, rest at 60 V (off) for `rest`, then a step to V_STEP. Breakdown delay
    t_d = strike - node crossing V_b; tau = crossing - last glow strike (afterglow time)."""
    rest, seed = args
    p = ramp_circuit()  # base: dark Y_bg 10 /s with memory
    t0 = 0.55 + rest
    segs = [
        (0.05, START, START),
        (0.5, 85.0, 85.0),
        (rest, REST_V, REST_V),
        (2.0, V_STEP, V_STEP),
    ]
    td, tau = [], []
    for i in range(RAMPS):
        t, tr = run(p, segs, SEED0 + 1000 * seed + i)
        cross = tr["t"][np.argmax((tr["t"] >= t0) & (tr["v"] >= p.V_b))]
        after, glow = t[t >= cross], t[t < t0]
        td.append(float(after[0] - cross) if len(after) else float("nan"))
        tau.append(float(cross - glow[-1]) if len(glow) else float("nan"))
    return {"rest_s": rest, "seed": seed, "t_d": td, "tau_s": tau}


def summarise(rows, keys, value) -> list[dict]:
    """mean ± std over the 5 seed means; std over all trials; count of trials that never lit."""
    out = []
    for key in sorted({tuple(r[k] for k in keys) for r in rows}):
        sel = [r for r in rows if tuple(r[k] for k in keys) == key]
        allv = np.concatenate([r[value] for r in sel])
        means = [np.nanmean(r[value]) for r in sel]
        out.append(
            {
                **dict(zip(keys, key)),
                "mean": float(np.mean(means)),
                "std_seeds": float(np.std(means)),
                "std_trials": float(np.nanstd(allv)),
                "n_unlit": int(np.isnan(allv).sum()),
                "n": len(allv),
            }
        )
        if "tau_s" in sel[0]:
            out[-1]["tau_median_s"] = float(
                np.nanmedian(np.concatenate([r["tau_s"] for r in sel]))
            )
    return out


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    p = ramp_circuit()
    with Pool(4) as pool:
        rates = pool.map(
            rate_point, [(r, y, s) for r in RATES for y in Y_BGS for s in range(SEEDS)]
        )
        rests = pool.map(rest_point, [(t, s) for t in RESTS for s in range(SEEDS)])
    out = {
        "setup": {
            "acquisition": __import__("dataclasses").asdict(B),
            "base_circuit": __import__("dataclasses").asdict(circuit(profile=B)),
            "V_b": p.V_b,
            "t_f": p.t_f,
            "Y_bg": p.Y_bg,
            "Y_res": p.Y_res,
            "tau_res": p.tau_res,
            "K_node_per_supply": K,
            "V_step": V_STEP,
            "C": p.C,
            "R_ch": R_CH,
            "R_d": R_D,
            "seeds": SEEDS,
            "ramps_per_seed": RAMPS,
        },
        "rate_sweep": summarise(rates, ("rate", "Y_bg"), "v_app"),
        "memory_curve": summarise(rests, ("rest_s",), "t_d"),
    }
    for row in out["rate_sweep"]:  # Derived prediction next to each simulated point
        row["predicted"] = p.V_b + row["rate"] * (1 / row["Y_bg"] + p.t_f)
    for row in out[
        "memory_curve"
    ]:  # Derived, rate frozen at the crossing: 1/Y(tau) + t_f
        row["predicted"] = (
            1 / (p.Y_bg + p.Y_res * np.exp(-row["tau_median_s"] / p.tau_res)) + p.t_f
        )
    (RESULTS / "sim_breakdown.json").write_text(json.dumps(out, indent=1))
    for row in out["rate_sweep"] + out["memory_curve"]:
        print(row)


if __name__ == "__main__":
    main()
