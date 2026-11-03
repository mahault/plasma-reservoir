"""Analyze current-derived optical observables from saved ngspice runs."""

import hashlib
import json
from pathlib import Path

import numpy as np

from plasma_rc.neon.analysis import feature_correlations, narma_score, optical_features, step_samples
from plasma_rc.neon.spice import Trace


def analyze_optical(source, out, samples=16):
    """Score optical proxies and bulb voltage with paired held-out NARMA inputs."""
    source, out = Path(source), Path(out)
    summary = json.loads((source / "summary.json").read_text())
    out.mkdir(parents=True, exist_ok=False)
    train = tuple(summary["splits"]["train"])
    validation = tuple(summary["splits"]["validation"])
    test = tuple(summary["splits"]["test"])
    timing = summary["timing"]
    edges = timing["start_s"] + np.arange(summary["n_steps"] + 1) * timing["step_s"]
    alphas = (0.01, 0.1, 1.0, 10.0)
    sources = [Path(__file__), Path(__file__).with_name("analysis.py")]
    results = {"source": str(source), "seeds": summary["seeds"], "splits": summary["splits"], "samples_per_step": samples,
               "features": {"brightness": "mean positive lamp current (uncalibrated optical proxy)",
                            "frequency": "number of current crossings above 1 microamp per step divided by step duration",
                            "oscillation": "standard deviation of current-derived brightness samples per step",
                            "combined_voltage": "all three features plus mean bulb voltage"},
               "controls": "removed bulb and resistor have zero optical features; their voltage is measured",
               "nmse": "test MSE divided by test target variance",
               "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
               "runs": []}
    for seed in summary["seeds"]:
        source_dir = source / f"seed-{seed}"
        seed_dir = out / f"seed-{seed}"
        seed_dir.mkdir()
        u = np.load(source_dir / "input.npy")
        row = {"seed": seed, "scores": {}, "alpha": {}, "correlations": {}}
        for regime in ("near", "active", "led"):
            for kind in (("led",) if regime == "led" else ("switch", "open", "resistor")):
                name = "led" if kind == "led" else f"{regime}_{kind}"
                raw = np.loadtxt(source_dir / name / "trace.txt", ndmin=2)
                trace = Trace(*raw.T)
                optical = optical_features(trace, edges, samples=samples)
                if kind in ("open", "resistor"):
                    optical[:] = 0.0
                np.save(seed_dir / f"{name}.npy", optical)
                voltage = step_samples(trace, edges, samples)[:, :samples].mean(axis=1, keepdims=True)
                groups = {"brightness": optical[:, :1], "frequency": optical[:, 1:2],
                          "oscillation": optical[:, 2:3], "combined": optical,
                          "combined_voltage": np.column_stack((optical, voltage))}
                row["correlations"][name] = feature_correlations(groups["combined_voltage"][slice(*train)])
                row["scores"][name], row["alpha"][name] = {}, {}
                for key, states in groups.items():
                    if kind == "switch" and not next(r for r in summary["runs"] if r["seed"] == seed)["regime_valid"][name]:
                        row["alpha"][name][key] = None
                        row["scores"][name][key] = None
                        continue
                    a = alphas[int(np.argmin([narma_score(states, u, train, validation, alpha) for alpha in alphas]))]
                    row["alpha"][name][key] = a
                    row["scores"][name][key] = narma_score(states, u, (train[0], validation[1]), test, a)
        results["runs"].append(row)
    (out / "summary.json").write_text(json.dumps(results, indent=2, allow_nan=False))
    return results
