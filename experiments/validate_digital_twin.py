"""Validate digital twin fidelity against held-out indexed trials with logged inputs.

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
from plasma_rc.trials.storage import trials, load_trial
from plasma_rc.stimuli import levels_to_u
from plasma_rc.characterization.features import step_features


def run_validation(data_dir: str, min_cod: float, max_nmse: float) -> dict[str, float | bool]:
    session = Path(data_dir)
    if not (session/"index.csv").exists():
        raise ValueError("validation needs trial records with logged inputs, not legacy CSV timestamps")
    records = trials([session], "ipc")
    if len(records) < 2:
        raise ValueError("need at least two trials with logged inputs")
    arrays = []
    for row in records:
        cap = load_trial(row["raw_file"])
        cap.require_integrity()
        with np.load(row["raw_file"]) as d:
            signal = levels_to_u(d["levels"])
        states = step_features(cap,int(row["ticks_per_step"]),len(signal))[:,:3]
        arrays.append((signal, states))
    # Construct windows within each trial: never invent transitions across recordings.
    windows = [np.lib.stride_tricks.sliding_window_view(u,5) for u,_ in arrays[:-1]]
    train_inputs = np.concatenate(windows)
    train_states = np.concatenate([x[4:] for _,x in arrays[:-1]])
    val_inputs, val_states = arrays[-1]
    twin = PlasmaDigitalTwin(noise_scale=0.0, seed=0)
    twin.fit(train_inputs, train_states)
    preds = twin.drive(val_inputs)[4:]
    val_states = val_states[4:]

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
    parser.add_argument("--data-dir", required=True, help="Session containing indexed trials with logged input levels.")
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
