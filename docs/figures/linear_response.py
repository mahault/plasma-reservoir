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
    # Diagram Design light palette; use local fonts for reproducible scientific exports.
    ink, muted, accent, paper = "#2d3142", "#4f5d75", "#bf4520", "#f5f5f5"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "text.color": ink, "axes.labelcolor": muted,
                         "xtick.color": muted, "ytick.color": muted,
                         "axes.edgecolor": "#bfc0c0", "svg.fonttype": "none"})
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.5), facecolor=paper)
    fig.subplots_adjust(left=.08, right=.98, bottom=.28, top=.78, wspace=.32)
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
        color = accent if substeps == 8 else muted
        ax[0].plot(tr["t"] * 1e3, tr["v"], linestyle="none",
                   marker="x" if substeps == 8 else "o", markersize=7,
                   markerfacecolor="none", markeredgewidth=1.4, color=color,
                   label=f"{substeps} substeps / tick")
        ax[1].semilogy(
            tr["t"] * 1e3,
            np.maximum(np.abs(tr["v"] - expected), 1e-14),
            color=color, linewidth=1.8 if substeps == 8 else 1.4,
            linestyle="-" if substeps == 8 else "--",
        )
    # Include t=0 in the analytical reference; numerical points stay at actual sample times.
    analytic_t = np.linspace(0., 1e-3, 300)
    ax[0].plot(analytic_t * 1e3, 60. + 30. * np.exp(-analytic_t / 1e-4),
               color=ink, linewidth=1.2, alpha=.7, label="Analytical limit", zorder=1)
    ax[0].set(xlabel="Time [ms]", ylabel="Node voltage [V]", xlim=(0, 1.0), ylim=(59., 92.))
    ax[1].set(xlabel="Time [ms]", ylabel="Absolute error [V]", xlim=(0, 1.2), ylim=(7e-15, 3e-10))
    for a, title in zip(ax, ("01  Response", "02  Numerical error")):
        a.set_facecolor(paper)
        a.set_title(title, loc="left", fontsize=12, color=ink, pad=14, fontweight="bold")
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y", color="#d8dade", linewidth=.7)
        a.tick_params(length=3)
        a.set_axisbelow(True)
    fig.suptitle("Linear circuit check", x=.08, y=.98, ha="left",
                 fontsize=20, fontfamily="DejaVu Serif", color=ink)
    fig.text(.08, .88, "Model response versus a known one-pole limit · halving the integration step",
             fontsize=10, color=muted)
    handles, labels = ax[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.5, .12),
               ncol=3, frameon=False, fontsize=10)
    fig.text(.08, .045, "Illustrative bulb-free model · R = 10 kΩ · C = 10 nF · no noise · errors below 10⁻¹⁴ V clipped for display",
             fontsize=9, color=muted)
    out = Path(__file__).parent
    fig.savefig(out / "linear_response.svg")
    svg = out / "linear_response.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    fig.savefig(out / "linear_response.png", dpi=180)
    print(json.dumps({"seeds": list(range(5)), "checks": rows}, indent=2))


if __name__ == "__main__":
    main()
