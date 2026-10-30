"""S1: simulation evidence for circuit A and the acquisition chain (technical.md §10).

Runs ngspice (bulb = hysteretic switch, D-20) and simavr (real firmware ELF), and writes every
number with its provenance to results/sim_evidence.json, traces to results/sim_traces.npz.
No bench values are used: bulb values are the NE-2AS datasheet (Cited, lit. review [2]) or a
swept range (I_min, Unknown); component values are illustrative (plasma_rc.sim.PART).
Figures: python docs/diagrams/sim_figs.py
"""

from __future__ import annotations

import datetime
import json
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from experiments.ne2.common import RESULTS
from scipy.linalg import expm

from plasma_rc.stimuli import replica_levels
from plasma_rc.circuit_checks import corner_hz, mid_gain, supply_for
from plasma_rc.sim import (
    PART,
    RUN_TICKS,
    STEPS,
    TICK,
    V_E,
    arduino_cli,
    bulb,
    firmware_sim,
    pulse,
    spice,
    thev,
    tran,
)

I_MIN = 50e-6  # Unknown; nominal value for the single-case rows, swept in the robustness grid
SWEEP = dict(
    V_b=[60.0, 76.0, 90.0],
    I_min=[20e-6, 50e-6, 100e-6, 200e-6],
    Re=[100e3, 330e3, 1e6, 3.3e6],
)


def sh(*cmd) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def provenance() -> dict:
    return {
        "date": datetime.date.today().isoformat(),
        "git_commit": sh("git", "rev-parse", "--short", "HEAD")
        + (" (dirty)" if sh("git", "status", "--porcelain") else ""),
        "ngspice": sh("ngspice", "-v").splitlines()[1].strip("* "),
        "simavr": sh("dpkg-query", "-W", "-f=${Version}", "simavr"),
        "arduino_cli": sh(arduino_cli(), "version"),
        "bulb_model": "hysteretic switch, D-20 (model hypothesis); no breakdown delay, no plasma dynamics",
        "bulb_values": "NE-2AS datasheet, lit. review [2] (Cited): V_b 60/76/90 V, 58 V @ 0.3 mA, V_e >= 50 V",
        "I_min": "Unknown: 50 uA nominal, swept 20-200 uA",
        "components": {"values": PART, "source": "illustrative, not the build"},
    }


def rel(sim: float, pred: float) -> dict:
    return {
        "sim": float(sim),
        "pred": float(pred),
        "rel_err": float((sim - pred) / pred),
    }


def circuit(work: Path, traces: dict) -> dict:
    out = {}
    V77, R77 = thev(77)
    t, v, ib, _ = tran(spice(work, "tran 10u 50m", 77, I_MIN))
    out["rest_node_V"] = rel(v[-1], V77) | {
        "lit": bool(ib.max() > 1e-9),
        "test": "test_rest_node_is_thevenin_and_silent",
    }

    d = spice(work, "ac dec 100 1m 1Meg", 77, I_MIN, va="DC 0 AC 1")
    f, H = d[:, 0], np.abs(d[:, 1] + 1j * d[:, 2])
    traces |= {"bode_f": f, "bode_H": H}
    Rp = 1 / (1 / PART["Rs"] + 1 / PART["R_d"])
    band = f[H >= H.max() / math.sqrt(2)]
    out["input_path"] = {
        "mid_gain": rel(H.max(), mid_gain(Rp, PART["Re"])),
        "f_LP_Hz": rel(
            band[-1], corner_hz(Rp * PART["Re"] / (Rp + PART["Re"]), PART["C"])
        ),
        "f_HP_Hz": rel(band[0], corner_hz(PART["Re"] + Rp, PART["C_c"])),
        "f_HP_Hz_old_formula_Re_only": corner_hz(PART["Re"], PART["C_c"]),
        "test": "test_input_path_bulb_off",
    }

    t, v, ib, _ = tran(spice(work, "tran 1u 0.2 0 1u", 90, I_MIN, cc="*"))
    V, R = thev(90)
    b = bulb(I_MIN)
    r = b["r_on"] + PART["R_sense"]
    v_on = (V * r + b["V_m"] * R) / (R + r)
    T_off = PART["C"] * R * math.log((V - V_E) / (V - b["V_b"]))
    T_on = PART["C"] * R * r / (R + r) * math.log((b["V_b"] - v_on) / (V_E - v_on))
    strikes = t[1:][np.diff((ib > 1e-6).astype(int)) == 1]
    out["relaxation_period_s"] = rel(np.median(np.diff(strikes[2:])), T_off + T_on) | {
        "textbook_off_phase_only_s": T_off,
        "test": "test_relaxation_period_above_breakdown",
    }

    C, Cc, Re = PART["C"], PART["C_c"], 1e6
    A = np.array(
        [[-(1 / R77 + 1 / Re) / C, 1 / (Re * C)], [1 / (Re * Cc), -1 / (Re * Cc)]]
    )
    taus = sorted(-1 / np.linalg.eigvals(A).real)
    for Re_i in (1e6, 100e3):  # single flash vs latch, same 22 V / 10 ms pulse
        t, v, ib, va = tran(
            spice(work, "tran 5u 1.2 0 5u", 77, I_MIN, va=pulse(22), Re=Re_i)
        )
        traces |= {f"t_{Re_i:.0f}": t, f"v_{Re_i:.0f}": v, f"ib_{Re_i:.0f}": ib}
        out[f"lit_after_pulse_ms_Re_{Re_i:.0f}"] = float(
            (t[ib > 1e-6].max() - 0.31) * 1e3
        )
        if Re_i == Re:
            off = np.flatnonzero(ib > 1e-6)[-1] + 1
            x_inf, x0 = np.full(2, V77), np.array([v[off], v[off] - va[off]])
            pred = np.array(
                [(x_inf + expm(A * (tt - t[off])) @ (x0 - x_inf))[0] for tt in t[off:]]
            )
            traces |= {"recovery_t": t[off:], "recovery_pred": pred}
            out["recovery_two_pole"] = {
                "max_abs_err_V": float(np.max(np.abs(pred - v[off:]))),
                "tau_fast_s": taus[0],
                "tau_slow_s": taus[1],
                "tau_slow_approx_s": (R77 + Re) * Cc,
                "tau_old_formula_RchC_s": R77 * C,
                "test": "test_recovery_with_input_branch_is_two_pole",
            }
    return out


def robustness(work: Path) -> dict:
    """Does (V'-V_e)/(R' ∥ Re) > I_min predict latching across the datasheet V_b range and swept I_min?"""
    rows = []
    Rp = 1 / (1 / PART["Rs"] + 1 / PART["R_d"])
    for V_b in SWEEP["V_b"]:
        Vn = V_E + 0.5 * (V_b - V_E)  # rest point mid-way in V_e < V' < V_b
        V_s = supply_for(Vn, PART["R_f"] + PART["Rs"], PART["R_d"])
        Vp, R = thev(V_s)
        for I_min in SWEEP["I_min"]:
            for Re in SWEEP["Re"]:
                amp = (
                    1.5 * (V_b - Vp) / mid_gain(Rp, Re)
                )  # 50 % above the firing margin
                t, v, ib, _ = tran(
                    spice(
                        work,
                        "tran 5u 0.8 0 5u",
                        V_s,
                        I_min,
                        V_b=V_b,
                        va=pulse(amp),
                        Re=Re,
                    )
                )
                lit = t[ib > 1e-6]
                margin = (
                    (Vp - V_E) / (R * Re / (R + Re)) / I_min
                )  # supply current at V_e over I_min
                lit_ms = float((lit.max() - 0.31) * 1e3) if lit.size else None
                rows.append(
                    {
                        "V_b": V_b,
                        "I_min": I_min,
                        "Re": Re,
                        "fired": bool(lit.size),
                        "margin": margin,
                        "lit_after_pulse_ms": lit_ms,
                        "latched": bool(lit.size and lit_ms > 50),
                        "pred_latch": bool(margin > 1),
                    }
                )
    return {
        "cases": rows,
        "n": len(rows),
        "latch_criterion_ms": 50,
        "agree": sum(r["fired"] and r["latched"] == r["pred_latch"] for r in rows),
        "missed_latches": sum(r["latched"] and not r["pred_latch"] for r in rows),
        "test": "test_latching_follows_supply_parallel_input_branch",
    }


def firmware(work: Path, traces: dict) -> dict:
    s = firmware_sim(work)
    cap = s["cap"]
    err = cap.flash_times_s() * 16e6 - (s["pulses"] - s["start"])
    cycles, levels = s["dac"].T
    want = np.append(replica_levels(*STEPS[:4]), 128)
    at = s["start"] + (np.arange(len(want)) * STEPS[4] + STEPS[4] // 2) * TICK
    got = levels[np.searchsorted(cycles, at, side="right") - 1]
    traces |= {"flash_err_cycles": err, "dac_want": want, "dac_got": got}
    nbytes = (work / "uart.bin").stat().st_size
    counts = {p: cap.channel(p)[1].astype(int) for p in "0123"}
    return {
        "samples": len(cap.ticks),
        "expected_samples": RUN_TICKS,
        "dropped": cap.dropped,
        "adc_err_counts": {
            p: int(np.abs(c - (int(p) + 1) / 5 * 1024).max()) for p, c in counts.items()
        },
        "flash_err_cycles": err.tolist(),
        "flash_err_us_max": float(np.abs(err).max() / 16),
        "dac_steps_match": int((got == want).sum()),
        "dac_steps": len(want),
        "serial_bytes_per_s": nbytes / (RUN_TICKS * TICK / 16e6),
        "serial_capacity_bytes_per_s": 1e6 / 10,
        "tests": "tests/test_firmware_sim.py",
    }


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    traces: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        out = {
            "provenance": provenance(),
            "circuit": circuit(work, traces),
            "robustness": robustness(work),
            "firmware": firmware(work, traces),
        }
    (RESULTS / "sim_evidence.json").write_text(json.dumps(out, indent=1, default=float))
    np.savez(RESULTS / "sim_traces.npz", **traces)
    r = out["robustness"]
    print(
        f"wrote {RESULTS}/sim_evidence.json; latching rule agrees in {r['agree']}/{r['n']} cases"
    )


if __name__ == "__main__":
    main()
