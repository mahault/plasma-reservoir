"""Diagnostic look at the first real plasma recordings (apple_m, apple_c).

This is NOT the Step 1 characterization pipeline — it deliberately does
not run separation_matrix(), lyapunov_estimate(), or memory_capacity(),
because this dataset can't support them yet:

  - memory_capacity() needs a known input signal (no voltage_in column
    was recorded)
  - separation_matrix() / lyapunov_estimate() need multiple repeated
    trials per class (each file is a single continuous session, not
    repeats)
  - there is no same-session baseline recording, so we can't baseline-
    subtract or check the "clustered vs scattered" claim against a
    baseline the way the original report did

What this script does do: plot both recordings on shared, fixed axes
(no per-plot autoscaling) and report per-recording effective
dimensionality, which is all that's honestly computable from two single
sessions with no input signal or repeats.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plasma_rc.characterization.dimensionality import effective_dimensionality
from plasma_rc.reservoir.physical import PlasmaDataLoader

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHANNELS = ["Brightness", "Frequency_Hz", "Settle_Micros"]


def run_diagnostic():
    loader = PlasmaDataLoader(DATA_DIR)
    recordings = {}
    for trial in loader.list_trials():
        t, states = loader.load_trial(trial["path"].name)
        recordings[trial["name"]] = (t, states)

    # shared axis limits per channel, computed across ALL recordings
    # so no single plot's autoscaling can manufacture a "tight cluster"
    shared_limits = []
    for i in range(3):
        all_vals = np.concatenate([states[:, i] for _, states in recordings.values()])
        pad = 0.05 * (all_vals.max() - all_vals.min() or 1.0)
        shared_limits.append((all_vals.min() - pad, all_vals.max() + pad))

    fig, axes = plt.subplots(len(recordings), 3, figsize=(12, 4 * len(recordings)), squeeze=False)
    for row, (name, (t, states)) in enumerate(recordings.items()):
        for col, channel in enumerate(CHANNELS):
            ax = axes[row][col]
            ax.plot(t, states[:, col], marker="o", markersize=3, alpha=0.7)
            ax.set_ylim(*shared_limits[col])
            ax.set_title(f"{name}: {channel}")
            ax.set_xlabel("time (s)")

    plt.tight_layout()
    out_path = Path(__file__).resolve().parent.parent / "real_data_diagnostic.png"
    plt.savefig(out_path, dpi=150)
    print(f"Saved figure: {out_path.name}\n")

    print("=== Per-recording effective dimensionality (PCA, 95% variance) ===")
    for name, (_, states) in recordings.items():
        n_dims, cumvar = effective_dimensionality(states)
        print(f"  {name}: {n_dims}/3 dims  (cumvar={np.round(cumvar, 3)})")

    print()
    print("=== Not computed, and why ===")
    print("  memory_capacity   : no input_signal recorded (no voltage_in column)")
    print("  separation_matrix : each recording is 1 continuous session, not repeated trials")
    print("  lyapunov_estimate : needs multiple trials of the same input, not available")
    print()
    print("To make those runnable, we need from Majesty: a same-session baseline,")
    print("repeated discrete trials per word/condition, the raw input signal log,")
    print("and a same-syllable-count word pair (e.g. apple vs mango).")


if __name__ == "__main__":
    run_diagnostic()
