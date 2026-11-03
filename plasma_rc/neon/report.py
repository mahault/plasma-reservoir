"""Analysis of saved minimal-circuit simulation traces."""

import json
from pathlib import Path

import numpy as np

from plasma_rc.neon.analysis import characterize_ipc, delayed_capacities, narma_score


def correct_open_controls(path):
    """Recompute open controls using zero current; preserve original runs and scores."""
    path = Path(path)
    corrected = json.loads((path / "summary.json").read_text())
    train = tuple(corrected["splits"]["train"])
    validation = tuple(corrected["splits"]["validation"])
    test = tuple(corrected["splits"]["test"])
    alphas = (0.01, 0.1, 1.0, 10.0)
    corrected["correction"] = "Open circuit current features set to zero; original raw files preserved."
    for row in corrected["runs"]:
        seed_dir = path / f"seed-{row['seed']}"
        u = np.load(seed_dir / "input.npy")
        row["corrected_delay_capacity"] = {}
        for regime in ("near", "active"):
            name = f"{regime}_open"
            x = np.load(seed_dir / name / "features.npy")
            x[:, 4:] = 0.0
            alpha = alphas[int(np.argmin([narma_score(x, u, train, validation, a) for a in alphas]))]
            row["alpha"][name] = alpha
            row["scores"][name] = narma_score(x, u, (train[0], validation[1]), test, alpha)
            row["corrected_delay_capacity"][name] = delayed_capacities(x, u, (train[0], validation[1]), test, 10)
    with (path / "summary_corrected.json").open("x") as f:
        json.dump(corrected, f, indent=2, allow_nan=False)
    return corrected


def summarize_scores(summary):
    """Aggregate per-seed scores and paired switch-minus-open differences."""
    runs = summary["runs"]
    if not runs:
        raise ValueError("no complete runs")
    values = {name: np.array([np.nan if run["scores"][name] is None else run["scores"][name] for run in runs], dtype=float)
              for name in runs[0]["scores"]}
    for regime in ("near", "active"):
        if f"{regime}_switch" in values and f"{regime}_open" in values:
            values[f"{regime}_switch_minus_open"] = values[f"{regime}_switch"] - values[f"{regime}_open"]
    result = {}
    for name, a in values.items():
        finite = a[np.isfinite(a)]
        result[name] = {"mean": float(finite.mean()) if len(finite) else None,
                        "std": float(finite.std()) if len(finite) else None,
                        "per_seed": [float(x) if np.isfinite(x) else None for x in a]}
    return result


def analyze_study(path):
    """Compute held-out single-delay scores and conduction from saved traces."""
    path = Path(path)
    summary = json.loads((path / "summary.json").read_text())
    out = {"scope": "held-out Legendre degrees 1 and 2 through lag 9; shuffled-cutoff truncated IPC, not full IPC",
           "threshold_a": 1e-6, "seeds": {}}
    train = (summary["splits"]["train"][0], summary["splits"]["validation"][1])
    test = tuple(summary["splits"]["test"])
    start = summary["timing"]["start_s"]
    for seed in summary["seeds"]:
        directory = path / f"seed-{seed}"
        u = np.load(directory / "input.npy")
        records = {}
        for regime in ("near", "active", "led"):
            for kind in (("led",) if regime == "led" else ("switch", "open", "resistor")):
                name = "led" if kind == "led" else f"{regime}_{kind}"
                features = np.load(directory / name / "features.npy")
                if kind == "open":
                    features[:, 4:] = 0.0
                raw = np.loadtxt(directory / name / "trace.txt")
                raw = raw[raw[:, 0] >= start]
                on = raw[:, 3] > out["threshold_a"]
                dt = np.diff(raw[:, 0])
                records[name] = {
                    "regime_valid": next(r for r in summary["runs"] if r["seed"] == seed).get("regime_valid", {}).get(name),
                    "delay_capacity": delayed_capacities(features, u, train, test, 10),
                    "ipc": characterize_ipc(features, u, train, test, 10, seed=10000 + int(seed)),
                    "switch_events": int(np.count_nonzero(on[1:] & ~on[:-1])),
                    "on_fraction_time": float(np.sum(dt * on[:-1]) / np.sum(dt)),
                    "min_current_a": float(np.min(raw[:, 3])),
                }
        out["seeds"][str(seed)] = records
    with (path / "analysis.json").open("x") as f:
        json.dump(out, f, indent=2, allow_nan=False)
    return out
