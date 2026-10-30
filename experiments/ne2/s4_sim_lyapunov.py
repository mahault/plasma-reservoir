"""S4: conditional Lyapunov exponent λ of the driven circuit (simulated, Teensy 4.1 profile).

Twin runs share the drive (random held steps, as E4) and all noise, and start 1 mV apart in node
voltage; λ = slope of ln|Δ(v, w)| (bulb_model.conditional_lyapunov). λ < 0 means the circuit forgets
its initial state and is driven by the input alone (echo state property); 1/|λ| is how long a state
difference survives. Reference (Derived): bulb removed, λ = the slowest eigenvalue of the linear
network, set by the coupling capacitor C_c. Runs: the four S2 bulb models, a drive-amplitude sweep
for the base model, a C_c sweep (bulb vs removed: when C_c is small the node mode, which flashes reset,
becomes the slowest), and two checks (dt halved, delta 100x smaller). 5 seeds.
"""

from __future__ import annotations

import json
from multiprocessing import Pool

import numpy as np
from experiments.ne2.common import RESULTS
from plasma_rc.simulation.config import PROFILES, CONDITIONS, SEED0, circuit

from plasma_rc.stimuli import xorshift32_levels
from plasma_rc.bulb_model import conditional_lyapunov

B = PROFILES["teensy41"]
N_STEPS, SEEDS, SKIP_S = 500, 5, 0.05  # 10 s of 20 ms steps per run
V_PKS = [0.0, 0.4, 0.8, 1.2, 1.65]
C_CS = [1e-6, 0.1e-6, 10e-9]


def job(args) -> dict:
    tag, over, seed, oversample, delta = args
    lam = conditional_lyapunov(
        circuit(**over),
        xorshift32_levels(SEED0 + seed, N_STEPS),
        B.tps,
        B.ocr1a,
        seed,
        delta,
        SKIP_S,
        oversample,
        B.clock_hz,
    )
    return {"tag": tag, "seed": seed, **lam}


def slowest_eigenvalue(p) -> float:
    a = np.array(
        [
            [-(1 / p.R_th + 1 / p.Re) / p.C, 1 / (p.Re * p.C)],
            [1 / (p.Re * p.C_c), -1 / (p.Re * p.C_c)],
        ]
    )
    return float(max(np.linalg.eigvals(a).real))


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    os_ = B.oversample
    jobs = [
        (n, dict(o), s, os_, 1e-3) for n, o in CONDITIONS.items() for s in range(SEEDS)
    ]
    jobs += [
        (f"v_pk={v:g}", {"v_pk": v}, s, os_, 1e-3) for v in V_PKS for s in range(SEEDS)
    ]
    jobs += [
        (f"C_c={c:g}, {n}", {"C_c": c, **CONDITIONS[n]}, s, os_, 1e-3)
        for c in C_CS
        for n in ("linear", "delay+memory")
        for s in range(SEEDS)
    ]
    jobs += [("check: dt halved", {}, s, 2 * os_, 1e-3) for s in range(2)]
    jobs += [("check: delta 1e-5", {}, s, os_, 1e-5) for s in range(2)]
    with Pool(10) as pool:
        rows = pool.map(job, jobs)
    out = {
        "setup": {
            "acquisition": __import__("dataclasses").asdict(B),
            "base_circuit": __import__("dataclasses").asdict(circuit(profile=B)),
            "board": "teensy41",
            "n_steps": N_STEPS,
            "step_s": B.tps * (B.ocr1a + 1) / B.clock_hz,
            "skip_s": SKIP_S,
            "seeds": SEEDS,
            "slowest_eigenvalue_per_s": slowest_eigenvalue(circuit()),
            "slowest_eigenvalue_by_C_c": {
                f"{c:g}": slowest_eigenvalue(circuit(C_c=c)) for c in C_CS
            },
        },
        "results": {},
    }
    for tag in dict.fromkeys(r["tag"] for r in rows):
        sel = [r for r in rows if r["tag"] == tag]
        lam = [r["lambda"] for r in sel]
        out["results"][tag] = {
            "lambda_per_s": [float(np.mean(lam)), float(np.std(lam))],
            "jumps": [r["jumps"] for r in sel],
            "n_points": [r["n_points"] for r in sel],
        }
        print(tag, out["results"][tag])
    (RESULTS / "sim_lyapunov.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
