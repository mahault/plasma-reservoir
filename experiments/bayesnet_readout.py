"""Experiment: Bayesian network readout vs flat linear readout.

Runs on synthetic ESN data until real plasma data is available.
Demonstrates that the DAG structure improves predictions when
the target has genuine hierarchical dependencies.
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from plasma_rc.readout.bayesnet import BayesNetReadout, NodeSpec
from plasma_rc.readout.linear import LinearReadout
from plasma_rc.evaluation.metrics import nmse, cod, calibration_error


def generate_synthetic_reservoir(n_samples: int = 1000, reservoir_dim: int = 50, seed: int = 42):
    """Simulate an echo state network as stand-in for plasma data."""
    rng = np.random.RandomState(seed)

    # random input signal
    u = rng.randn(n_samples)

    # random reservoir weights (sparse)
    W = rng.randn(reservoir_dim, reservoir_dim) * 0.1
    mask = rng.rand(reservoir_dim, reservoir_dim) > 0.9
    W *= mask
    # scale to spectral radius < 1
    sr = np.max(np.abs(np.linalg.eigvals(W)))
    W *= 0.95 / sr

    W_in = rng.randn(reservoir_dim) * 0.5

    # drive the ESN
    states = np.zeros((n_samples, reservoir_dim))
    x = np.zeros(reservoir_dim)
    for t in range(n_samples):
        x = np.tanh(W @ x + W_in * u[t])
        states[t] = x

    # create hierarchical targets that mirror the proposed plasma DAG:
    #   intensity   = f(reservoir)
    #   frequency   = f(reservoir)
    #   oscillation = f(reservoir)
    #   energy      = g(intensity, frequency) + noise
    #   word_class  = h(energy, oscillation) + noise
    W_int = rng.randn(reservoir_dim) * 0.1
    W_freq = rng.randn(reservoir_dim) * 0.1
    W_osc = rng.randn(reservoir_dim) * 0.1

    intensity = states @ W_int + rng.randn(n_samples) * 0.05
    frequency = states @ W_freq + rng.randn(n_samples) * 0.05
    oscillation = states @ W_osc + rng.randn(n_samples) * 0.05
    energy = 0.6 * intensity + 0.4 * frequency + rng.randn(n_samples) * 0.1
    word_class = 0.5 * energy + 0.5 * oscillation + rng.randn(n_samples) * 0.1

    targets = {
        "intensity": intensity,
        "frequency": frequency,
        "oscillation": oscillation,
        "energy": energy,
        "word_class": word_class,
    }
    return states, targets


def run_experiment():
    # generate data
    states, targets = generate_synthetic_reservoir()
    n_train = 700
    train_states, test_states = states[:n_train], states[n_train:]
    train_targets = {k: v[:n_train] for k, v in targets.items()}
    test_targets = {k: v[n_train:] for k, v in targets.items()}

    # --- Bayesian network readout (DAG) ---
    dag_nodes = [
        NodeSpec("intensity", parents=[]),
        NodeSpec("frequency", parents=[]),
        NodeSpec("oscillation", parents=[]),
        NodeSpec("energy", parents=["intensity", "frequency"]),
        NodeSpec("word_class", parents=["energy", "oscillation"], is_target=True),
    ]
    bn = BayesNetReadout(dag_nodes)
    bn_lml = bn.fit(train_states, train_targets)
    bn_result = bn.predict(test_states)

    # --- Flat linear readout (baseline) ---
    flat = LinearReadout(bayesian=True)
    flat.fit(train_states, train_targets["word_class"])
    flat_result = flat.predict(test_states)

    # --- Evaluate ---
    y_true = test_targets["word_class"]

    bn_pred = bn_result["word_class"]
    flat_pred = flat_result

    print("=== Bayesian Network Readout ===")
    print(f"  NMSE:  {nmse(y_true, bn_pred.mean):.4f}")
    print(f"  CoD:   {cod(y_true, bn_pred.mean):.4f}")
    print(f"  ECE:   {calibration_error(y_true, bn_pred.mean, bn_pred.std):.4f}")
    print(f"  log-ML: {bn_lml:.2f}")
    print()
    print("=== Flat Linear Readout ===")
    print(f"  NMSE:  {nmse(y_true, flat_pred.mean):.4f}")
    print(f"  CoD:   {cod(y_true, flat_pred.mean):.4f}")
    if flat_pred.std is not None:
        print(f"  ECE:   {calibration_error(y_true, flat_pred.mean, flat_pred.std):.4f}")
    print()

    # --- Model comparison (log Bayes factor) ---
    log_bf = bn.model_comparison(train_states, train_targets)
    for node, lbf in log_bf.items():
        verdict = "DAG wins" if lbf > 0 else "flat wins"
        print(f"  log BF ({node}): {lbf:.2f}  ({verdict})")

    # --- Plot ---
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].set_title("BayesNet readout: word_class")
    axes[0].plot(y_true, label="true", alpha=0.7)
    axes[0].plot(bn_pred.mean, label="predicted", alpha=0.7)
    axes[0].fill_between(
        range(len(y_true)),
        bn_pred.mean - 2 * bn_pred.std,
        bn_pred.mean + 2 * bn_pred.std,
        alpha=0.2, label="95% CI",
    )
    axes[0].legend()

    axes[1].set_title("Flat readout: word_class")
    axes[1].plot(y_true, label="true", alpha=0.7)
    axes[1].plot(flat_pred.mean, label="predicted", alpha=0.7)
    if flat_pred.std is not None:
        axes[1].fill_between(
            range(len(y_true)),
            flat_pred.mean - 2 * flat_pred.std,
            flat_pred.mean + 2 * flat_pred.std,
            alpha=0.2, label="95% CI",
        )
    axes[1].legend()

    plt.tight_layout()
    plt.savefig("bayesnet_vs_flat.png", dpi=150)
    print("\nSaved figure: bayesnet_vs_flat.png")


if __name__ == "__main__":
    run_experiment()
