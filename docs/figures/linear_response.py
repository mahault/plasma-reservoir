"""Reproduce a bulb-free analytical check, with five fixed seeds and dt halving.

Illustrative limit: Re=1e15 ohm decouples the input; Rth=10 kohm, C=10 nF,
Vth=60 V, initial perturbation=30 V. No physical measurements are used.
"""

from dataclasses import replace
from pathlib import Path
import json
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from plasma_rc.simulation.config import circuit
from plasma_rc.simulation.model import simulate


def main():
    p = replace(
        circuit(),
        bulb=False,
        V_th=60.0,
        R_th=1e4,
        C=1e-8,
        Re=1e15,
        tau_aa=1e-12,
        noise_counts=0.0,
        k_v=0.04,
        adc_bits=10,
        v_ref=5.0,
    )
    rows = []
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.5), layout="constrained")
    for substeps in (4, 8):
        errors = []
        for seed in range(5):
            cap, tr = simulate(
                p,
                np.zeros(6),
                4,
                2665,
                np.random.default_rng(seed),
                substeps,
                channels="3",
                dv0=30.0,
                trace=True,
            )
            expected = 60.0 + 30.0 * np.exp(-tr["t"] / 1e-4)
            errors.append(float(np.max(np.abs(tr["v"] - expected))))
        rows.append({"substeps": substeps, "max_voltage_error_V_per_seed": errors})
        ax[0].plot(tr["t"] * 1e3, tr["v"], ".", label=f"{substeps} substeps/tick")
        ax[1].semilogy(
            tr["t"] * 1e3,
            np.maximum(np.abs(tr["v"] - expected), 1e-14),
            label=f"{substeps} substeps/tick",
        )
    ax[0].plot(
        tr["t"] * 1e3, expected, "k-", alpha=0.5, label="one-pole analytical limit"
    )
    ax[0].set(
        xlabel="Time [ms]", ylabel="Node voltage [V]", title="Bulb-free transient"
    )
    ax[1].set(
        xlabel="Time [ms]",
        ylabel="Absolute error [V]",
        title="Numerical versus limiting solution",
    )
    for a in ax:
        a.legend(fontsize=8)
        a.grid(alpha=0.2)
    out = Path(__file__).parent
    fig.savefig(out / "linear_response.svg")
    fig.savefig(out / "linear_response.png", dpi=160)
    print(json.dumps({"seeds": list(range(5)), "checks": rows}, indent=2))


if __name__ == "__main__":
    main()
