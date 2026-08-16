"""Validate digital twin fidelity against held-out recorded trials.

Usage:
    python experiments/validate_digital_twin.py --data-dir data/plasma
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from plasma_rc.evaluation.metrics import cod, nmse
from plasma_rc.reservoir.digital_twin import PlasmaDigitalTwin
from plasma_rc.reservoir.physical import PlasmaDataLoader


def run_validation(data_dir: str, min_cod: float, max_nmse: float) -> dict[str, float | bool]:
    loader = PlasmaDataLoader(data_dir)
    trials = loader.list_trials()
    if len(trials) < 2:
        raise RuntimeError("Need at least 2 trials for train/validation split.")

    arrays = []
    for trial in trials:
        signal, states = loader.load_trial(trial["word"], trial["volume_pct"], trial["trial_id"])
        arrays.append((signal, states))

    # Deterministic split: all but last for training, last for validation.
    train_inputs = np.concatenate([x for x, _ in arrays[:-1]])
    train_states = np.concatenate([s for _, s in arrays[:-1]])
    val_inputs, val_states = arrays[-1]

    twin = PlasmaDigitalTwin(noise_scale=0.0)
    twin.fit(train_inputs, train_states)
    twin.reset()

    preds = np.zeros_like(val_states)
    for idx, u in enumerate(val_inputs):
        preds[idx] = twin.step(float(u)).as_array()

    nmse_vals = [nmse(val_states[:, i], preds[:, i]) for i in range(3)]
    cod_vals = [cod(val_states[:, i], preds[:, i]) for i in range(3)]
    mean_nmse = float(np.mean(nmse_vals))
    mean_cod = float(np.mean(cod_vals))

    return {
        "mean_nmse": mean_nmse,
        "mean_cod": mean_cod,
        "pass_nmse": mean_nmse <= max_nmse,
        "pass_cod": mean_cod >= min_cod,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, help="Directory containing plasma trial CSV files.")
    parser.add_argument("--min-cod", type=float, default=0.30)
    parser.add_argument("--max-nmse", type=float, default=1.20)
    parser.add_argument("--out", default="artifacts/twin_validation.json")
    args = parser.parse_args()

    result = run_validation(args.data_dir, args.min_cod, args.max_nmse)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
