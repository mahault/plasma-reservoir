"""Run benchmark comparisons with reproducible artifacts.

Outputs CSV/JSON metrics for:
- BayesNet vs linear readout
- optional physical data baseline if --data-dir is provided
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from plasma_rc.benchmarks.mackey_glass import mackey_glass
from plasma_rc.benchmarks.narma import narma10
from plasma_rc.evaluation.metrics import cod, nmse
from plasma_rc.readout.bayesnet import BayesNetReadout, NodeSpec
from plasma_rc.readout.linear import LinearReadout
from plasma_rc.reservoir.physical import PlasmaDataLoader


def synthetic_states(signal: np.ndarray, dim: int = 24, seed: int = 0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    W = rng.randn(dim, dim) * 0.15
    Win = rng.randn(dim) * 0.25
    x = np.zeros(dim)
    states = np.zeros((len(signal), dim))
    for t, u in enumerate(signal):
        x = np.tanh(W @ x + Win * float(u))
        states[t] = x
    return states


def evaluate_task(states: np.ndarray, target: np.ndarray, split: int) -> dict[str, float]:
    train_x, test_x = states[:split], states[split:]
    train_y, test_y = target[:split], target[split:]

    linear = LinearReadout(bayesian=True)
    linear.fit(train_x, train_y)
    linear_pred = linear.predict(test_x).mean

    dag = BayesNetReadout([NodeSpec("target", is_target=True)])
    dag.fit(train_x, {"target": train_y})
    dag_pred = dag.predict(test_x)["target"].mean

    return {
        "linear_nmse": nmse(test_y, linear_pred),
        "linear_cod": cod(test_y, linear_pred),
        "bayesnet_nmse": nmse(test_y, dag_pred),
        "bayesnet_cod": cod(test_y, dag_pred),
    }


def maybe_physical_summary(data_dir: str | None) -> dict[str, float]:
    if not data_dir:
        return {}
    loader = PlasmaDataLoader(data_dir)
    trials = loader.list_trials()
    if not trials:
        return {}
    rows = []
    for t in trials:
        signal, states = loader.load_trial(t["word"], t["volume_pct"], t["trial_id"])
        rows.append((np.var(signal), float(np.mean(np.linalg.norm(states, axis=1)))))
    arr = np.asarray(rows)
    return {"physical_signal_var_mean": float(arr[:, 0].mean()), "physical_state_norm_mean": float(arr[:, 1].mean())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-steps", type=int, default=1200)
    parser.add_argument("--split", type=int, default=800)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--out-dir", default="artifacts/benchmarks")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    u_narma, y_narma = narma10(args.n_steps, seed=args.seed)
    states_narma = synthetic_states(u_narma, seed=args.seed)
    narma_res = evaluate_task(states_narma, y_narma, args.split)

    mg = mackey_glass(args.n_steps)
    states_mg = synthetic_states(mg, seed=args.seed + 1)
    mg_res = evaluate_task(states_mg, mg, args.split)

    metrics = {
        "narma10": narma_res,
        "mackey_glass": mg_res,
        "physical_summary": maybe_physical_summary(args.data_dir),
        "seed": args.seed,
    }

    json_path = out_dir / "metrics.json"
    json_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    csv_path = out_dir / "metrics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["task", "model", "nmse", "cod"])
        for task, res in [("narma10", narma_res), ("mackey_glass", mg_res)]:
            writer.writerow([task, "linear", res["linear_nmse"], res["linear_cod"]])
            writer.writerow([task, "bayesnet", res["bayesnet_nmse"], res["bayesnet_cod"]])

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
