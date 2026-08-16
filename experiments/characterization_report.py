"""Run reservoir characterization and generate publication-ready figures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plasma_rc.characterization.dimensionality import effective_dimensionality
from plasma_rc.characterization.memory_capacity import memory_capacity
from plasma_rc.characterization.separation import separation_matrix
from plasma_rc.reservoir.physical import PlasmaDataLoader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", default="artifacts/characterization")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    loader = PlasmaDataLoader(args.data_dir)
    trials = loader.list_trials()
    if not trials:
        raise RuntimeError("No trials found.")

    grouped: dict[str, list[np.ndarray]] = {}
    first_signal = None
    all_states = []
    for t in trials:
        signal, states = loader.load_trial(t["word"], t["volume_pct"], t["trial_id"])
        first_signal = signal if first_signal is None else first_signal
        key = f"{t['word']}_{t['volume_pct']}"
        grouped.setdefault(key, []).append(states)
        all_states.append(states)

    stacked = np.concatenate(all_states, axis=0)
    max_delay = max(1, min(20, len(first_signal) - 1))
    mc, mc_per_delay = memory_capacity(stacked[: len(first_signal)], first_signal, max_delay=max_delay)
    n_dims, cumvar = effective_dimensionality(stacked)

    class_data = {k: np.stack(v, axis=0) for k, v in grouped.items() if len(v) >= 1}
    sep, labels = separation_matrix(class_data)

    fig1 = plt.figure(figsize=(7, 4))
    plt.plot(np.arange(1, len(mc_per_delay) + 1), mc_per_delay)
    plt.title("Memory capacity by delay")
    plt.xlabel("Delay")
    plt.ylabel("R^2")
    plt.tight_layout()
    fig1.savefig(out_dir / "memory_capacity.png", dpi=150)
    plt.close(fig1)

    fig2 = plt.figure(figsize=(5, 4))
    plt.imshow(sep, interpolation="nearest")
    plt.xticks(np.arange(len(labels)), labels, rotation=45, ha="right")
    plt.yticks(np.arange(len(labels)), labels)
    plt.title("Separation matrix")
    plt.colorbar()
    plt.tight_layout()
    fig2.savefig(out_dir / "separation_matrix.png", dpi=150)
    plt.close(fig2)

    fig3 = plt.figure(figsize=(7, 4))
    plt.plot(cumvar)
    plt.axhline(0.95, linestyle="--")
    plt.title("Cumulative PCA explained variance")
    plt.xlabel("Components")
    plt.ylabel("Explained variance")
    plt.tight_layout()
    fig3.savefig(out_dir / "effective_dimensionality.png", dpi=150)
    plt.close(fig3)

    summary = {"memory_capacity": mc, "effective_dims_95pct": n_dims}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
