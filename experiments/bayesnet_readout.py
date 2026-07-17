"""Experiment: Bayesian network readout vs flat linear readout.

Runs on synthetic ESN data until real plasma data is available.

Honest framing (2026-07-17): with linear-Gaussian nodes, a DAG whose
parents are *predicted from the reservoir states* provably collapses to
the flat linear readout — compositions of linear maps are linear — so
flat vs DAG-with-predicted-parents is expected to tie on NMSE. The
structured readout earns its keep in three ways this script measures:

  1. Observed parents: when intermediate observables are measured at
     test time (as plasma channels are), conditioning on them beats the
     flat readout.
  2. Calibrated uncertainty: Monte Carlo propagation accounts for parent
     uncertainty that the plug-in forward pass ignores.
  3. Fair model evidence: p(y | states, parents) vs p(y | states) on the
     same data — does structure carry information beyond the states?
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

    # plug-in: children condition on predicted parent means (old default)
    bn_plugin = bn.predict(test_states)["word_class"]
    # Monte Carlo: parent uncertainty propagated through the DAG
    bn_mc = bn.predict(test_states, n_samples=200)["word_class"]
    # observed parents: energy + oscillation measured at test time
    bn_obs = bn.predict(
        test_states,
        observed={
            "energy": test_targets["energy"],
            "oscillation": test_targets["oscillation"],
        },
    )["word_class"]

    # --- Flat linear readout (baseline) ---
    flat = LinearReadout(bayesian=True)
    flat.fit(train_states, train_targets["word_class"])
    flat_pred = flat.predict(test_states)

    # --- Evaluate ---
    y_true = test_targets["word_class"]

    def report(name, pred):
        line = f"  {name:24s} NMSE {nmse(y_true, pred.mean):.4f}  CoD {cod(y_true, pred.mean):.4f}"
        if pred.std is not None:
            line += f"  ECE {calibration_error(y_true, pred.mean, pred.std):.4f}"
        print(line)

    print("=== word_class readout comparison (test set) ===")
    report("flat linear", flat_pred)
    report("DAG, plug-in parents", bn_plugin)
    report("DAG, MC propagation", bn_mc)
    report("DAG, observed parents", bn_obs)
    print(f"\n  DAG training log-ML (all nodes): {bn_lml:.2f}")
    print()
    print("Flat vs DAG-with-predicted-parents tying on NMSE is expected:")
    print("compositions of linear-Gaussian nodes are linear in the states.")
    print("The structured readout wins when parent observables are measured")
    print("at test time; MC propagation reflects parent uncertainty that the")
    print("plug-in pass ignores.")
    print()

    # --- Model comparison (fair same-data log Bayes factor) ---
    log_bf = bn.model_comparison(train_states, train_targets)
    for node, lbf in log_bf.items():
        verdict = (
            "parents carry information beyond states"
            if lbf > 0 else "flat wins"
        )
        print(f"  log BF p(y|states,parents) vs p(y|states), {node}: "
              f"{lbf:.2f}  ({verdict})")

    # --- Plot ---
    variants = [
        ("Flat readout", flat_pred),
        ("DAG, MC propagation", bn_mc),
        ("DAG, observed parents", bn_obs),
    ]
    fig, axes = plt.subplots(1, len(variants), figsize=(18, 4), sharey=True)
    for ax, (title, pred) in zip(axes, variants):
        ax.set_title(f"{title}: word_class")
        ax.plot(y_true, label="true", alpha=0.7)
        ax.plot(pred.mean, label="predicted", alpha=0.7)
        if pred.std is not None:
            ax.fill_between(
                range(len(y_true)),
                pred.mean - 2 * pred.std,
                pred.mean + 2 * pred.std,
                alpha=0.2, label="95% CI",
            )
        ax.legend()

    plt.tight_layout()
    plt.savefig("bayesnet_vs_flat.png", dpi=150)
    print("\nSaved figure: bayesnet_vs_flat.png")


if __name__ == "__main__":
    run_experiment()
