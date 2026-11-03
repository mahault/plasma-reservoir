"""Exploratory NARMA-10 sweep for an uncalibrated NE-2H switch hypothesis."""

import itertools
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np

from plasma_rc.neon.analysis import (
    characterize_ipc,
    conditional_contraction,
    held_drive,
    input_delays,
    narma10_target,
    narma_score,
    step_samples,
)
from plasma_rc.neon.config import StudyConfig
from plasma_rc.neon.metrics import nmse
from plasma_rc.neon.spice import NeonSwitch, run_transient

LAMP_KEYS = ("strike_v", "extinction_v", "intercept_v", "on_resistance_ohm")
ALPHAS = (0.01, 0.1, 1.0, 10.0)
BALLAST_OHM = 30_000.0
BIAS_V, GAIN_V = 105.0, 100.0
STEP_S, START_S, RISE_S = 1e-3, 0.01, 1e-6


def candidate_grid():
    """Return explicit exploratory values, never presented as NE-2H measurements."""
    axes = (
        ("strike_v", (120.0, 135.0)),
        ("extinction_v", (60.0, 80.0)),
        ("intercept_v", (40.0, 50.0)),
        ("on_resistance_ohm", (10_000.0, 40_000.0)),
        ("parasitic_capacitance_f", (1e-9, 1e-8)),
    )
    return [
        {**dict(zip((key for key, _ in axes), values)),
         "parameter_status": "exploratory assumption"}
        for values in itertools.product(*(choices for _, choices in axes))
    ]


def _splits(n_steps):
    washout = max(10, n_steps // 10)
    train = (washout, n_steps // 2)
    validation = (train[1], n_steps * 7 // 10)
    test = (validation[1], n_steps - 1)
    if test[1] - test[0] < 2:
        raise ValueError("n_steps leaves too few test samples")
    return train, validation, test


def _lamp_params(candidate):
    return {key: candidate[key] for key in LAMP_KEYS}


def _states(trace, edges):
    return step_samples(trace, edges, 4)


def _choose_alpha(states_by_seed, inputs, train, validation):
    scores = {
        alpha: [
            narma_score(states, inputs[seed], train, validation, alpha)
            for seed, states in states_by_seed.items()
        ]
        for alpha in ALPHAS
    }
    means = {alpha: float(np.mean(values)) for alpha, values in scores.items()}
    alpha = min(ALPHAS, key=means.get)
    return alpha, means[alpha], {str(a): values for a, values in scores.items()}


def _score_summary(values):
    values = np.asarray(values, dtype=float)
    return {"per_seed": values.tolist(), "mean": float(values.mean()),
            "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0}


def _simulate(trace_dir, config, candidate, drive, duration, max_step_s):
    return run_transient(config, drive, duration, max_step_s, trace_dir,
                         bulb=NeonSwitch(**_lamp_params(candidate)))


def _conditional_stability(root, config, candidate):
    reference = [(0.0, 0.0), (1e-6, 180.0), (1.1e-3, 180.0),
                 (1.2e-3, 180.0), (1.20025e-3, 180.0), (1.23e-3, 180.0)]
    perturbed = [(0.0, 0.0), (1e-6, 180.0), (1.1e-3, 180.0),
                 (1.2e-3, 175.0), (1.20025e-3, 180.0), (1.23e-3, 180.0)]
    model = NeonSwitch(**_lamp_params(candidate))
    a = run_transient(config, reference, 1.23e-3, 0.25e-6, root / "reference", bulb=model)
    b = run_transient(config, perturbed, 1.23e-3, 0.25e-6, root / "perturbed", bulb=model)
    try:
        rate = conditional_contraction(a, b, 1.201e-3, 1.221e-3)
        expected = -(1 / config.ballast_ohm + 1 / model.on_resistance_ohm) / candidate["parasitic_capacitance_f"]
        return {
            "status": "estimated for the deterministic, continuously-on one-capacitor model segment",
            "interpretation": "not a physical Lyapunov exponent and not a general hybrid-system exponent",
            "finite_time_log_divergence_slope_per_s": rate,
            "linear_on_branch_analytic_rate_per_s": expected,
            "relative_difference": abs(rate - expected) / abs(expected),
            "interval_s": [1.201e-3, 1.221e-3],
        }
    except ValueError as error:
        return {"status": "not_estimated", "interpretation": "not a physical Lyapunov exponent",
                "reason": str(error)}


def run_ne2h_study(output, *, seeds=(11, 23, 37, 51, 79), n_steps=450,
                   candidates=None, max_step_s=20e-6, n_shuffles=20):
    """Tune explicit switch hypotheses on validation NMSE, then report a held-out test."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    seeds = tuple(seeds)
    candidates = candidate_grid() if candidates is None else list(candidates)
    if (len(seeds) < 1 or len(set(seeds)) != len(seeds) or not candidates or
            n_steps < 80 or not np.isfinite(max_step_s) or max_step_s <= 0):
        raise ValueError("need distinct seeds, candidates, at least 80 steps, and positive timestep")
    train, validation, test = _splits(n_steps)
    def config_for(candidate):
        return StudyConfig(BALLAST_OHM, candidate["parasitic_capacitance_f"])

    inputs = {seed: np.random.default_rng(seed).uniform(0, 0.5, n_steps) for seed in seeds}
    for seed, u in inputs.items():
        np.save(output / f"input-seed-{seed}.npy", u)
    edges = START_S + np.arange(n_steps + 1) * STEP_S
    drive_by_seed = {seed: held_drive(u, BIAS_V, GAIN_V, STEP_S, START_S, RISE_S)[0]
                     for seed, u in inputs.items()}

    sweep_rows = []
    for index, candidate in enumerate(candidates):
        states, validation_scores = {}, {}
        config = config_for(candidate)
        for seed in seeds:
            with tempfile.TemporaryDirectory(prefix="ne2h-sweep-") as temp:
                trace = _simulate(Path(temp) / "trace", config, candidate,
                                  drive_by_seed[seed], float(edges[-1]), max_step_s)
            states[seed] = _states(trace, edges)
            validation_scores[seed] = {
                str(alpha): narma_score(states[seed], inputs[seed], train, validation, alpha)
                for alpha in ALPHAS
            }
        mean_by_alpha = {
            str(alpha): float(np.mean([validation_scores[s][str(alpha)] for s in seeds]))
            for alpha in ALPHAS
        }
        best_alpha = min(ALPHAS, key=lambda alpha: mean_by_alpha[str(alpha)])
        score = mean_by_alpha[str(best_alpha)]
        row = {"index": index, "parameters": candidate, "validation_nmse_by_alpha": mean_by_alpha,
               "selected_alpha": best_alpha, "mean_validation_nmse": score}
        sweep_rows.append(row)
    selected = min(sweep_rows, key=lambda row: row["mean_validation_nmse"])
    best_candidate = selected["parameters"]
    best_index, alpha = selected["index"], selected["selected_alpha"]
    best_states = {}
    for seed in seeds:
        trace = _simulate(output / "best" / f"seed-{seed}", config_for(best_candidate),
                          best_candidate, drive_by_seed[seed], float(edges[-1]), max_step_s)
        best_states[seed] = _states(trace, edges)
        np.save(output / "best" / f"seed-{seed}" / "features.npy", best_states[seed])
    best_test = {
        seed: narma_score(best_states[seed], inputs[seed], (train[0], validation[1]), test, alpha)
        for seed in seeds
    }

    controls = {}
    for kind, bulb, resistor in (("open", "open", None), ("resistor", "resistor", BALLAST_OHM)):
        per_seed = {}
        for seed in seeds:
            directory = output / "controls" / kind / f"seed-{seed}"
            trace = run_transient(config_for(best_candidate), drive_by_seed[seed], float(edges[-1]),
                                  max_step_s, directory, bulb=bulb, control_resistance_ohm=resistor)
            state = _states(trace, edges)
            if kind == "open":
                state[:, 4:] = 0.0
            np.save(directory / "features.npy", state)
            per_seed[seed] = state
        control_alpha, val_score, val_details = _choose_alpha(per_seed, inputs, train, validation)
        scores = [narma_score(per_seed[s], inputs[s], (train[0], validation[1]), test, control_alpha)
                  for s in seeds]
        controls[kind] = {"alpha": control_alpha, "mean_validation_nmse": val_score,
                          "validation_by_alpha": val_details, **_score_summary(scores)}

    direct = {seed: inputs[seed][:, None] for seed in seeds}
    linear_history = {seed: input_delays(inputs[seed], 10) for seed in seeds}
    benchmark_controls = {}
    for name, states_by_seed in (("current_input", direct), ("10_tap_input_history", linear_history)):
        control_alpha, val_score, val_details = _choose_alpha(states_by_seed, inputs, train, validation)
        scores = [narma_score(states_by_seed[s], inputs[s], (train[0], validation[1]), test, control_alpha)
                  for s in seeds]
        benchmark_controls[name] = {"alpha": control_alpha, "mean_validation_nmse": val_score,
                                    "validation_by_alpha": val_details, **_score_summary(scores)}
    mean_nmse = [nmse(narma10_target(inputs[s])[1:][slice(*test)],
                      np.full(test[1] - test[0], np.mean(narma10_target(inputs[s])[1:][slice(*train)])))
                 for s in seeds]
    benchmark_controls["training_mean"] = _score_summary(mean_nmse)

    ipc_rows, ranks = {}, []
    electrical_regime = {}
    for seed in seeds:
        ipc_rows[seed] = characterize_ipc(best_states[seed], inputs[seed], train, test, 10,
                                           seed=10_000 + int(seed), n_shuffles=n_shuffles)
        trace = np.loadtxt(output / "best" / f"seed-{seed}" / "trace.txt")
        on = trace[:, 3] > 1e-6
        dt = np.diff(trace[:, 0])
        electrical_regime[seed] = {
            "current_threshold_a": 1e-6,
            "on_fraction_time": float(np.sum(dt * on[:-1]) / np.sum(dt)),
            "off_to_on_events": int(np.count_nonzero(on[1:] & ~on[:-1])),
            "mean_current_when_on_a": float(trace[:-1, 3][on[:-1]].mean()) if np.any(on[:-1]) else None,
        }
        centered = best_states[seed][slice(*train)] - best_states[seed][slice(*train)].mean(axis=0)
        eigenvalues = np.linalg.eigvalsh(np.cov(centered, rowvar=False))
        eigenvalues = np.clip(eigenvalues, 0, None)
        probabilities = eigenvalues / eigenvalues.sum() if eigenvalues.sum() else eigenvalues
        rank = float(np.exp(-np.sum(probabilities[probabilities > 0] * np.log(probabilities[probabilities > 0]))))
        ranks.append(rank)

    fine_scores, trace_differences = [], []
    for seed in seeds:
        fine_dir = output / "timestep-half" / f"seed-{seed}"
        fine_trace = _simulate(fine_dir, config_for(best_candidate), best_candidate,
                               drive_by_seed[seed], float(edges[-1]), max_step_s / 2)
        fine_states = _states(fine_trace, edges)
        fine_scores.append(narma_score(fine_states, inputs[seed], (train[0], validation[1]), test, alpha))
        coarse = np.loadtxt(output / "best" / f"seed-{seed}" / "trace.txt")
        rms = float(np.sqrt(np.mean((np.interp(fine_trace.time_s, coarse[:, 0], coarse[:, 2])
                                     - fine_trace.voltage_v) ** 2)))
        trace_differences.append(rms)

    stability = _conditional_stability(output / "stability", config_for(best_candidate), best_candidate)
    summary = {
        "study": "Exploratory NE-2H-labeled NARMA-10 simulation; not physical calibration",
        "device": {"candidate": "CML-IT C2A / NE-2H, if that is the actual bulb",
                   "datasheet_max_initial_breakdown_v_in_light": 135.0,
                   "datasheet_design_current_a": 1.9e-3,
                   "limitations": "no measured strike distribution, extinction/holding point, I-V branch, dynamics, capacitance, or optical response"},
        "circuit": {"topology": "ideal V_D source -> R_B -> V_L node; lamp branch and C_par to return",
                    "ballast_ohm": BALLAST_OHM, "drive_bias_v": BIAS_V, "drive_gain_v": GAIN_V,
                    "drive_equation": "V_D = 105 V + 100 V * u, u uniform on [0, 0.5]",
                    "features": "four within-step samples each of V_L and I_L; I_L is electrical, not calibrated light"},
        "model": "instantaneous hysteretic switch with linear conducting branch; all non-datasheet lamp/circuit values are exploratory assumptions",
        "assumptions": "strike candidates [120,135] V; extinction [60,80] V; intercept [40,50] V; on resistance [10,40] kOhm; parasitic capacitance [1,10] nF",
        "parameters": {"seeds": seeds, "n_steps": n_steps, "ngspice": subprocess.run(
            ["ngspice", "--version"], capture_output=True, text=True, check=True).stdout.strip(),
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "max_step_s": max_step_s, "train": train, "validation": validation, "test": test,
            "selections": "5-seed mean validation NMSE; alpha selected on validation; test used only once for selected model",
            "score": "test MSE divided by test-target variance"},
        "selection": {"criterion": "mean validation NARMA-10 NMSE", "test_used_for_selection": False,
                      "alpha": alpha, "best_candidate_index": best_index},
        "sweep": sweep_rows,
        "best": {"parameters": best_candidate, **_score_summary(list(best_test.values())),
                 "validation_nmse": selected["mean_validation_nmse"]},
        "controls": {**controls, **benchmark_controls},
        "diagnostics": {
            "ipc": {"scope": "held-out degree-1 and degree-2 Legendre targets, lags 0-9; shuffled-cutoff truncated estimate",
                    "per_seed": {str(seed): row for seed, row in ipc_rows.items()},
                    "mean_linear_capacity": float(np.mean([r["linear_capacity"] for r in ipc_rows.values()])),
                    "mean_nonlinear_degree_2": float(np.mean([r["nonlinear_degree_2"] for r in ipc_rows.values()])),
                    "mean_truncated_total": float(np.mean([r["truncated_total"] for r in ipc_rows.values()])),
                    "shuffle_count": n_shuffles},
            "effective_feature_rank": {"mean": float(np.mean(ranks)), "per_seed": ranks, "feature_count": 8},
            "electrical_regime": {"per_seed": {str(seed): row for seed, row in electrical_regime.items()},
                                  "mean_on_fraction_time": float(np.mean(
                                      [row["on_fraction_time"] for row in electrical_regime.values()])),
                                  "mean_off_to_on_events": float(np.mean(
                                      [row["off_to_on_events"] for row in electrical_regime.values()]))},
            "timestep_halving": {"coarse_nmse": _score_summary(list(best_test.values())),
                                 "half_step_nmse": _score_summary(fine_scores),
                                 "mean_voltage_trace_rms_difference_v": float(np.mean(trace_differences)),
                                 "half_step_s": max_step_s / 2},
            "conditional_lyapunov": stability,
        },
        "artifacts": {"inputs": [f"input-seed-{seed}.npy" for seed in seeds],
                      "candidate_validation_scores": "summary.json:sweep",
                      "selected_model_traces": "best/seed-*/",
                      "figures": "figures/"},
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    from plasma_rc.neon.ne2h_report import generate_report
    generate_report(output, summary, inputs, best_states, alpha, train, validation, test, ipc_rows)
    return summary
