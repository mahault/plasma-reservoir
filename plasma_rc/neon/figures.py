"""Plots of simulation outputs and physical recordings."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from plasma_rc.neon.analysis import narma_predict, step_samples
from plasma_rc.neon.spice import Trace


def regime_title(run, name):
    label = name.replace("_", " ")
    return label + " (invalid regime)" if run.get("regime_valid", {}).get(name) is False else label


def generate_recording_figures(result, output):
    """Write per-step features, training correlations and held-out scores from an analyzed physical recording."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    x = np.asarray(result["features"])
    labels = ("light sensor (V)", "event rate (Hz)", "light variation (V)", "bulb voltage (V)")
    fig, axes = plt.subplots(4, 1, figsize=(9, 7), sharex=True, layout="constrained")
    for i, ax in enumerate(axes):
        ax.plot(x[:, i])
        ax.set_ylabel(labels[i])
    axes[-1].set_xlabel("Input step")
    fig.savefig(output / "features.png", dpi=160)
    plt.close(fig)
    corr = np.array([[np.nan if z is None else z for z in row] for row in result["correlations"]])
    fig, ax = plt.subplots(figsize=(6, 5), layout="constrained")
    im = ax.imshow(corr, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(4), labels, rotation=35)
    ax.set_yticks(range(4), labels)
    ax.set_title("Training-set correlations")
    fig.colorbar(im, ax=ax)
    fig.savefig(output / "correlation.png", dpi=160)
    plt.close(fig)
    scores = result["narma_nmse"]
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    ax.bar(list(scores), list(scores.values()))
    ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("Held-out NARMA-10 NMSE")
    fig.savefig(output / "narma.png", dpi=160)
    plt.close(fig)


def generate_simulation_figures(source, optical, output, pulse):
    """Save independent explanatory plots from a completed simulation study."""
    source, optical, output = map(Path, (source, optical, output))
    study = json.loads((source / "summary.json").read_text())
    metrics = json.loads((optical / "summary.json").read_text())
    output.mkdir(parents=True, exist_ok=False)
    names = ("near_switch", "active_switch", "led", "near_open", "near_resistor")
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    for i, name in enumerate(names):
        values = np.array([r["scores"][name]["combined_voltage"] for r in metrics["runs"] if r["scores"][name]["combined_voltage"] is not None])
        if len(values):
            ax.bar(i, values.mean(), yerr=values.std(), capsize=4)
        else:
            ax.text(i, 0, "invalid regime", rotation=90, ha="center", va="bottom")
    ax.set_xticks(range(len(names)), [n.replace("_", " ") for n in names], rotation=15)
    ax.set_ylabel("NARMA-10 NMSE (lower is better)")
    ax.set_title("Simulated optical proxies and bulb voltage · mean ± SD")
    fig.savefig(output / "narma.png", dpi=160)
    plt.close(fig)
    corr = metrics["runs"][0]["correlations"]["near_switch"]
    corr = np.array([[np.nan if a is None else a for a in row] for row in corr])
    fig, ax = plt.subplots(figsize=(6, 5), layout="constrained")
    image = ax.imshow(corr, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(4), ["light proxy", "event rate", "variation", "voltage"], rotation=30)
    ax.set_yticks(range(4), ["light proxy", "event rate", "variation", "voltage"])
    ax.set_title(regime_title(study["runs"][0], "near_switch") + ": training correlations, first seed")
    fig.colorbar(image, ax=ax)
    fig.savefig(output / "correlation.png", dpi=160)
    plt.close(fig)
    first = study["seeds"][0]
    fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True, layout="constrained")
    for ax, name in zip(axes, ("near_switch", "active_switch")):
        raw = np.loadtxt(source / f"seed-{first}" / name / "trace.txt")
        start = study["timing"]["start_s"]
        raw = raw[(raw[:, 0] >= start) & (raw[:, 0] <= start + 0.05)]
        ax.plot(raw[:, 0] * 1000, raw[:, 2], label="bulb voltage")
        ax.plot(raw[:, 0] * 1000, raw[:, 1], alpha=.6, label="drive voltage")
        ax.set(ylabel="Voltage (V)", title=regime_title(study["runs"][0], name))
        ax.legend()
    axes[-1].set_xlabel("Time (ms)")
    fig.savefig(output / "traces.png", dpi=160)
    plt.close(fig)
    seed_dir = source / f"seed-{first}"
    u = np.load(seed_dir / "input.npy")
    raw = np.loadtxt(seed_dir / "near_switch" / "trace.txt")
    trace = Trace(*raw.T)
    step = study["timing"]["step_s"]
    edges = study["timing"]["start_s"] + np.arange(len(u) + 1) * step
    samples = metrics["samples_per_step"]
    voltage = step_samples(trace, edges, samples)[:, :samples].mean(axis=1, keepdims=True)
    states = np.column_stack((np.load(optical / f"seed-{first}" / "near_switch.npy"), voltage))
    split = study["splits"]
    alpha = metrics["runs"][0]["alpha"]["near_switch"]["combined_voltage"]
    if alpha is None:
        expected = prediction = np.array([])
    else:
        expected, prediction = narma_predict(states, u, (split["train"][0], split["validation"][1]), split["test"], alpha)
    np.savez(output / "prediction.npz", target=expected, prediction=prediction)
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    ax.plot(expected, label="target")
    ax.plot(prediction, label="prediction", alpha=.8)
    ax.set(xlabel="Held-out input step", ylabel="NARMA-10 output", title=regime_title(study["runs"][0], "near_switch") + ": first seed")
    ax.legend()
    fig.savefig(output / "prediction.png", dpi=160)
    plt.close(fig)
    details = json.loads((source / "analysis.json").read_text())["seeds"]
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    for name in ("near_switch", "active_switch", "led", "near_open"):
        rows = [v[name]["delay_capacity"]["degree_1"] for v in details.values()
                if v[name].get("regime_valid") is not False]
        if rows:
            values = np.array(rows)
            ax.plot(range(values.shape[1]), values.mean(axis=0), marker="o", label=name.replace("_", " "))
    ax.axhline(0, color="grey", linewidth=.7)
    ax.set(xlabel="Input delay (steps)", ylabel="Held-out linear reconstruction score", title="Linear memory by delay")
    ax.legend()
    fig.savefig(output / "ipc.png", dpi=160)
    plt.close(fig)
    pulse = Path(pulse)
    runs = json.loads((pulse / "summary.json").read_text())["runs"]
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    for i, row in enumerate(runs):
        data = np.loadtxt(pulse / f"ballast-{i}" / "trace.txt")
        data = data[(data[:, 0] >= .019) & (data[:, 0] <= .035)]
        ax.plot(data[:, 0] * 1000, data[:, 2], label=f"{row['ballast_ohm'] / 1e6:g} MΩ")
    ax.set(xlabel="Time (ms)", ylabel="Bulb voltage (V)", title="Illustrative ballast pulse responses")
    ax.legend()
    fig.savefig(output / "pulse.png", dpi=160)
    plt.close(fig)


def generate_figures(*args, **kwargs):
    """Unified entrypoint dispatching to recording or simulation figures."""
    if len(args) == 2 or ("result" in kwargs and "output" in kwargs):
        return generate_recording_figures(*args, **kwargs)
    return generate_simulation_figures(*args, **kwargs)
