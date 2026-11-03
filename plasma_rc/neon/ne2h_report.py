"""Figures and explanatory Markdown for the exploratory NE-2H simulation."""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from plasma_rc.neon.analysis import narma_predict


FIGURE_DESCRIPTIONS = {
    "circuit.png": (
        "Conceptual topology used in the simulation: an ideal drive source feeds the "
        "modeled lamp through a 30 kΩ ballast, with parallel capacitance at the lamp "
        "node. The lamp is an idealized switch model, not a physical NE-2H or optical model."
    ),
    "timestep_convergence.png": (
        "The selected model's held-out NMSE is nearly unchanged when the maximum "
        "integration step is halved. This checks numerical sensitivity for this run, "
        "not the physical accuracy of the circuit model."
    ),
    "parameter_sweep.png": (
        "The 12 lowest validation-NMSE candidates from the assumed parameter grid are "
        "shown; lower is better. These scores choose a task-performing assumption, "
        "not a physically calibrated bulb parameter set."
    ),
    "narma_prediction.png": (
        "Target and readout prediction over the held-out NARMA-10 segment for the first "
        "input seed. This single-seed trace illustrates prediction quality; the summary "
        "table reports results across all five seeds."
    ),
    "waveform.png": (
        "Simulated drive, lamp-node voltage, and model current over the displayed initial "
        "time window. These are electrical outputs of the idealized model, not measured "
        "signals from a bulb."
    ),
    "ipc.png": (
        "Held-out input-reconstruction scores across delays for degree-1 and same-delay "
        "degree-2 targets. The plotted view is truncated and does not include every "
        "cross-delay target used in the reported IPC total."
    ),
    "narma_comparison.png": (
        "Mean held-out NARMA-10 NMSE and standard deviation across seeds for the selected "
        "switch model and controls; lower is better. The switch model does not outperform "
        "the open control, and the input-history baseline is substantially better."
    ),
    "conditional_contraction.png": (
        "Log voltage separation for two model trajectories on a continuously-on RC "
        "branch, compared with fitted and analytic slopes. This conditional model "
        "diagnostic is not a physical or general hybrid-system Lyapunov exponent."
    ),
}


def _circuit_figure(path):
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.set(xlim=(0, 10), ylim=(0, 4))
    ax.axis("off")
    ax.plot([0.6, 2.0], [2, 2], color="black")
    ax.add_patch(plt.Rectangle((2, 1.65), 1.5, 0.7, fill=False, lw=1.5))
    ax.text(2.75, 2, "R_B\n30 kΩ", ha="center", va="center")
    ax.plot([3.5, 5.2], [2, 2], color="black")
    ax.scatter([5.2], [2], color="black", s=18)
    ax.text(5.2, 2.25, "V_L node", ha="center")
    ax.plot([5.2, 6.4], [2, 2], color="black")
    ax.add_patch(plt.Rectangle((6.4, 1.45), 1.8, 1.1, fill=False, lw=1.5))
    ax.text(7.3, 2, "NE-2H\nswitch model", ha="center", va="center")
    ax.plot([8.2, 8.8], [2, 2], color="black")
    ax.plot([8.8, 8.8], [2, 0.7], color="black")
    ax.plot([8.45, 9.15], [0.7, 0.7], color="black")
    ax.plot([8.55, 9.05], [0.52, 0.52], color="black")
    ax.plot([8.65, 8.95], [0.34, 0.34], color="black")
    ax.plot([5.2, 5.2], [2, 3.15], color="black")
    ax.add_patch(plt.Rectangle((4.8, 3.15), 0.8, 0.45, fill=False, lw=1.3))
    ax.text(5.2, 3.38, "C_par", ha="center", va="center")
    ax.plot([5.2, 5.2], [3.6, 3.85], color="black")
    ax.plot([4.7, 5.7], [3.85, 3.85], color="black")
    ax.text(0.65, 2.3, "V_D(t)", ha="center")
    ax.text(7.3, 1.1, "I_L", ha="center")
    ax.text(5, 0.05, "Ideal source, switch thresholds and linear lit branch; no optical or internal plasma state", ha="center", fontsize=9)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plots(root, summary, inputs, states, alpha, train, validation, test, ipc):
    figures = root / "figures"
    figures.mkdir()
    _circuit_figure(figures / "circuit.png")

    sweep = sorted(summary["sweep"], key=lambda row: row["mean_validation_nmse"])[:12]
    fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
    labels = [f"#{row['index']} S{row['parameters']['strike_v']:.0f}/C{row['parameters']['parasitic_capacitance_f']*1e9:g}" for row in sweep]
    ax.barh(range(len(sweep)), [row["mean_validation_nmse"] for row in sweep], color="#5b8db8")
    ax.set(yticks=range(len(sweep)), yticklabels=labels, xlabel="Mean validation NARMA-10 NMSE",
           title="Top candidates selected only on validation data")
    ax.invert_yaxis()
    fig.savefig(figures / "parameter_sweep.png", dpi=160)
    plt.close(fig)

    seed = summary["parameters"]["seeds"][0]
    prediction, expected = narma_predict(states[seed], inputs[seed], (train[0], validation[1]), test, alpha)
    np.savez(figures / "narma_prediction.npz", target=prediction, prediction=expected)
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    ax.plot(prediction, label="NARMA-10 target")
    ax.plot(expected, label="switch-model readout", alpha=.8)
    ax.set(xlabel="Held-out step", ylabel="Target / prediction", title="Held-out NARMA-10: first input seed")
    ax.legend()
    fig.savefig(figures / "narma_prediction.png", dpi=160)
    plt.close(fig)

    names = ("NE-2H switch", "open circuit", "resistor", "current input", "10-tap input history", "training mean")
    rows = (summary["best"], summary["controls"]["open"], summary["controls"]["resistor"],
            summary["controls"]["current_input"], summary["controls"]["10_tap_input_history"],
            summary["controls"]["training_mean"])
    fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
    means = [row["mean"] for row in rows]
    errors = [row["std"] for row in rows]
    ax.bar(range(len(names)), means, yerr=errors, capsize=4, color="#517a57")
    ax.set(xticks=range(len(names)), xticklabels=names, ylabel="Held-out NARMA-10 NMSE (lower is better)",
           title="Test results after validation-only selection")
    ax.tick_params(axis="x", rotation=20)
    fig.savefig(figures / "narma_comparison.png", dpi=160)
    plt.close(fig)

    trace = np.loadtxt(root / "best" / f"seed-{seed}" / "trace.txt")
    shown = trace[trace[:, 0] <= START_DISPLAY]
    fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True, layout="constrained")
    axes[0].plot(shown[:, 0] * 1000, shown[:, 1], label="drive")
    axes[0].plot(shown[:, 0] * 1000, shown[:, 2], label="bulb-node voltage")
    axes[0].set_ylabel("Voltage (V)")
    axes[0].legend()
    axes[1].plot(shown[:, 0] * 1000, shown[:, 3], color="#a44")
    axes[1].set(xlabel="Time (ms)", ylabel="Model current (A)")
    fig.savefig(figures / "waveform.png", dpi=160)
    plt.close(fig)

    ipc_rows = list(ipc.values())
    linear = np.asarray([row["targets"]["degree_1"] for row in ipc_rows])
    nonlinear = np.asarray([row["targets"]["degree_2"] for row in ipc_rows])
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    lags = np.arange(10)
    ax.plot(lags, linear.mean(axis=0), marker="o", label="degree 1")
    ax.plot(lags, nonlinear.mean(axis=0), marker="s", label="degree 2, same-lag")
    ax.set(xlabel="Input delay (steps)", ylabel="Held-out reconstruction score",
           title="Truncated IPC by degree and lag (mean over seeds)")
    ax.legend()
    fig.savefig(figures / "ipc.png", dpi=160)
    plt.close(fig)

    convergence = summary["diagnostics"]["timestep_halving"]
    coarse_us = summary["parameters"]["max_step_s"] * 1e6
    fig, ax = plt.subplots(figsize=(6, 4), layout="constrained")
    ax.bar([f"{coarse_us:g} µs", f"{coarse_us / 2:g} µs"],
           [convergence["coarse_nmse"]["mean"], convergence["half_step_nmse"]["mean"]],
           color=("#688eaa", "#85aa78"))
    ax.set(ylabel="Selected-model test NMSE", title="Maximum-step halving check")
    fig.savefig(figures / "timestep_convergence.png", dpi=160)
    plt.close(fig)

    _stability_plot(root, figures / "conditional_contraction.png", summary["diagnostics"]["conditional_lyapunov"])
    return [path.name for path in figures.glob("*.png")]


START_DISPLAY = 0.04


def _stability_plot(root, path, diagnostic):
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    if diagnostic["status"] == "not_estimated":
        ax.text(.5, .5, diagnostic["reason"], ha="center", va="center", wrap=True)
    else:
        traces = [np.loadtxt(root / "stability" / name / "trace.txt") for name in ("reference", "perturbed")]
        times = np.linspace(*diagnostic["interval_s"], 200)
        distance = np.abs(np.interp(times, traces[0][:, 0], traces[0][:, 2]) -
                          np.interp(times, traces[1][:, 0], traces[1][:, 2]))
        x = (times - times[0]) * 1e6
        log_distance = np.log(distance)
        fitted = log_distance[0] + diagnostic["finite_time_log_divergence_slope_per_s"] * (times - times[0])
        analytic = log_distance[0] + diagnostic["linear_on_branch_analytic_rate_per_s"] * (times - times[0])
        ax.plot(x, log_distance, label="observed")
        ax.plot(x, fitted, "--", label="fitted finite-time slope")
        ax.plot(x, analytic, ":", label="analytic linear-branch rate")
        ax.set(xlabel="Time after shared drive resumes (µs)", ylabel="Log separation (V)",
               title="Finite-time contraction on a continuously-on model branch")
        ax.legend()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def generate_report(root, summary, inputs, states, alpha, train, validation, test, ipc):
    """Write all explanatory figures and the required caveated report."""
    root = Path(root)
    figures = _plots(root, summary, inputs, states, alpha, train, validation, test, ipc)
    best = summary["best"]
    selected = best["parameters"]
    ipc_summary = summary["diagnostics"]["ipc"]
    stability = summary["diagnostics"]["conditional_lyapunov"]
    nmse_lines = [
        f"| NE-2H-labeled switch model | {best['mean']:.4f} | {best['std']:.4f} |",
        *[f"| {name.replace('_', ' ')} | {row['mean']:.4f} | {row['std']:.4f} |"
          for name, row in summary["controls"].items()],
    ]
    figure_text = "\n\n".join(
        f"{_figure_caption(name, FIGURE_DESCRIPTIONS[name])}\n\n{FIGURE_DESCRIPTIONS[name]}"
        for name in figures
        if name != "circuit.png"
    )
    source_review = Path(
        os.path.relpath(Path("docs/research/ne2h_model_parameters.md").resolve(), root.resolve())
    ).as_posix()
    text = f"""# Exploratory NE-2H-labeled reservoir simulation

**Status:** simulation-only exploratory result, not a physical experiment or calibrated NE-2H model. No measured NE-2H trace or bulb-specific parameter was available. All 32 candidates are assumptions. Results describe the selected model and protocol only.

## 1. Simulation circuit

The simulated topology is an ideal programmable voltage source V_D(t), a series ballast R_B = {summary['circuit']['ballast_ohm'] / 1000:g} kΩ, a neon branch whose node voltage V_L and current I_L are observed, and a lumped parallel capacitance C_par. The input mapping is V_D = {summary['circuit']['drive_bias_v']:g} V + {summary['circuit']['drive_gain_v']:g} V × u, with u uniformly sampled from [0, 0.5] and held for 1 ms. The model is an instantaneous hysteretic switch plus a linear conducting branch; it has no internal plasma state. Its current is an electrical state feature, **not measured light**.

{_figure_caption('circuit.png', FIGURE_DESCRIPTIONS['circuit.png'])}

{FIGURE_DESCRIPTIONS['circuit.png']}

## 2. NE-2H facts and model limitations

The reviewed CML-IT datasheet identifies C2A as NE-2H and lists 1.9 mA design current, 95 VAC / 135 VDC maximum initial breakdown in light, and a 150 V minimum DC circuit voltage for high-brightness lamps. The 150 V value is source-circuit voltage, not bulb strike or maintaining voltage. The datasheet does not provide a typical strike distribution, extinction/holding point, conducting I–V slope, dynamic delay, parasitic capacitance, or optical response. These facts are recorded in [the source review]({source_review}).

For this run, 135 V is used only as one upper-edge strike scenario; 120 V and every extinction, intercept, on-resistance, capacitance, and the 30 kΩ ballast are explicitly exploratory assumptions. They are **not** calibrated device values or a recipe for a physical circuit. The sweep cannot find physically accurate parameters without measurement data. Selecting by NARMA validation error instead finds the best task-performing member of this assumed grid and can overfit that validation protocol.

## 3. Figures and what this simulation can show

The plots show what can be evaluated within this ideal switch model: benchmark prediction, sensitivity to assumed parameters, electrical state trajectories, truncated input reconstruction, timestep sensitivity, and local deterministic contraction. They do not demonstrate that a real NE-2H bulb is a viable reservoir. In particular, omitted optical and internal discharge dynamics cannot appear in the model's results.

{figure_text}

## 4. Protocol and selected scenario

The experiment used {len(summary['parameters']['seeds'])} input seeds and {summary['parameters']['n_steps']} steps per seed. The chronological ranges are washout/training {summary['parameters']['train']}, validation {summary['parameters']['validation']}, and held-out test {summary['parameters']['test']}. Grid candidates and ridge alpha were selected using only mean validation NARMA-10 NMSE; the test split was evaluated once for the selected candidate. Maximum transient step was {summary['parameters']['max_step_s']*1e6:g} µs, with a second run at half that step.

Selected **validation-best assumptions**: strike = {selected['strike_v']:g} V, extinction = {selected['extinction_v']:g} V, conducting intercept = {selected['intercept_v']:g} V, on-resistance = {selected['on_resistance_ohm']/1000:g} kΩ, C_par = {selected['parasitic_capacitance_f']*1e9:g} nF, readout alpha = {alpha:g}. These values are selected for benchmark performance, not physical accuracy.

## 5. Results

### NARMA-10

NMSE is test MSE divided by test-target variance; lower is better. Values below are mean ± standard deviation across input seeds (not confidence intervals).

| Readout state/control | Mean test NMSE | SD |
|---|---:|---:|
{chr(10).join(nmse_lines)}

The direct input and 10-tap input-history baselines help establish task difficulty. The open-circuit and resistor controls reveal whether the switch's electrical nonlinearity adds useful information within this model. A lower score for one simulated candidate is not evidence that an actual lamp computes; no real-bulb or calibrated optical control was tested.

### IPC and state dimension

The reported IPC is deliberately truncated: held-out degree-1 and degree-2 Legendre targets for delays 0–9, with shuffled-input maximum cutoffs (n={ipc_summary['shuffle_count']}). Mean linear capacity = **{ipc_summary['mean_linear_capacity']:.4f}**; degree-2 capacity including cross-delay products = **{ipc_summary['mean_nonlinear_degree_2']:.4f}**; truncated total = **{ipc_summary['mean_truncated_total']:.4f}**. This is not complete theoretical IPC. The IPC plot shows same-delay degree-2 targets for clarity; all cross-delay targets and their per-seed scores are retained in `summary.json`. The effective rank of the eight sampled voltage/current features is {summary['diagnostics']['effective_feature_rank']['mean']:.3f}; it is a descriptive finite-sample feature statistic, not the physical state dimension.

### Electrical regime

At the declared 1 µA numerical on-threshold, the best model was conducting for a mean **{summary['diagnostics']['electrical_regime']['mean_on_fraction_time']:.3f}** of the simulated time and had **{summary['diagnostics']['electrical_regime']['mean_off_to_on_events']:.1f}** off-to-on transitions per input sequence. These describe the switch code under the chosen drive and threshold; they are not measured lamp ignition rates.

### Stability-related diagnostic

Status: **{stability['status']}**. The measured quantity, when estimated, is a finite-time voltage-separation slope on the assumed deterministic continuously-on linear RC branch, compared against that branch's analytic rate. This one-capacitor model diagnostic is **not a physical Lyapunov exponent**, does not cover switching/stochastic discharge dynamics, and cannot be transferred to a real bulb.

### Numerical sensitivity

Halving the maximum timestep changed selected-model mean test NMSE from {summary['diagnostics']['timestep_halving']['coarse_nmse']['mean']:.4f} to {summary['diagnostics']['timestep_halving']['half_step_nmse']['mean']:.4f}; mean RMS bulb-voltage difference between coarse and fine trajectories was {summary['diagnostics']['timestep_halving']['mean_voltage_trace_rms_difference_v']:.6g} V. This is a basic timestep sensitivity check, not validation of the model equations.

## 6. Conclusion and what is needed next

This simulation can demonstrate that a specified hysteretic-switch circuit produces benchmark states and can quantify those states' task performance **conditional on the assumptions**. It cannot answer whether a physical NE-2H provides useful nonlinear memory, whether this parameter set matches a bulb, or whether the optical signal has the modeled properties. The decisive next step for physical inference is identifying the actual bulb and recording calibrated, synchronized applied drive, bulb voltage, and lamp current (plus calibrated light if optical readout is studied), with repeated trials and a held-out condition. Until then, call this a model-based NARMA parameter search, not NE-2H calibration or a physical experiment.

## Reproducibility

`summary.json` stores all candidate validation scores, parameters, seeds, splits, software version, IPC results, and numerical checks. Raw traces and sampled states for the selected model are under `best/`; input vectors are saved at the report root. Non-selected candidate traces are not retained, but all candidate settings and scores are. The grid was selected on validation scores only. Re-run with `python -m experiments.neon_ne2h OUTPUT`.
"""
    (root / "report.md").write_text(text)


def _figure_caption(name, description):
    return f"![{description}](figures/{name})"
