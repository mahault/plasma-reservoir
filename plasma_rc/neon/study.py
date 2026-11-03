"""Paired minimal-circuit numerical experiment."""

import json
import hashlib
import subprocess
from itertools import combinations_with_replacement
from pathlib import Path

import numpy as np

from plasma_rc.neon.narma import narma10_target
from plasma_rc.neon.metrics import nmse
from plasma_rc.neon.analysis import held_drive, input_delays, narma_score, step_samples, strike_delay
from plasma_rc.neon.config import StudyConfig
from plasma_rc.neon.spice import LED, NeonSwitch, run_transient


def run_pulse_study(out, ballast_values, capacitance_f):
    """Compare charging-induced delays; instantaneous switch has no intrinsic strike delay."""
    if not ballast_values or len(set(ballast_values)) != len(ballast_values):
        raise ValueError("supply distinct ballast values")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    bulb = NeonSwitch(75, 52, 50, 100e3)
    drive = [(0, 0), (1e-6, 70), (0.02, 70), (0.02001, 90),
             (0.03, 90), (0.03001, 70), (0.05, 70)]
    result = {"model": "instantaneous switch; delay is circuit charging, not intrinsic plasma delay", "runs": []}
    for index, resistance in enumerate(ballast_values):
        config = StudyConfig(resistance, capacitance_f)
        trace = run_transient(config, drive, 0.05, 2e-6, out / f"ballast-{index}", bulb=bulb)
        result["runs"].append({"ballast_ohm": resistance,
            "first_strike_delay_s": strike_delay(trace, 0.02, 0.03),
            "conducting_at_end": bool(trace.current_a[-1] > 1e-6)})
    (out / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    return result


def run_study(out, seeds, n_steps=900, max_step_s=20e-6, capacitance_f=1e-9, ballast_ohm=1e6):
    """Run an exploratory M0 NARMA study; all circuit parameters are illustrative."""
    if n_steps < 60 or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("need at least 60 steps and distinct seeds")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    config = StudyConfig(ballast_ohm, capacitance_f)
    model = NeonSwitch(75, 52, 50, 100e3)
    step_s, start_s, rise_s = 1e-3, 0.01, 1e-6
    train = (max(10, n_steps // 10), n_steps // 2)
    validation = (train[1], n_steps * 7 // 10)
    test = (validation[1], n_steps - 1)
    alphas = (0.01, 0.1, 1.0, 10.0)
    version = subprocess.run(["ngspice", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    module_dir = Path(__file__).resolve().parent
    sources = [module_dir / n for n in ("config.py", "spice.py", "analysis.py", "study.py", "narma.py", "metrics.py")]
    report = {"seeds": list(seeds), "n_steps": n_steps, "ngspice": version, "git_head": commit,
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              "model": "instantaneous hysteretic switch; current is an uncalibrated light proxy",
              "parameter_provenance": "all circuit and lamp parameters illustrative, not measured",
              "ballast_ohm": config.ballast_ohm, "parasitic_capacitance_f": config.parasitic_capacitance_f,
              "timing": {"step_s": step_s, "start_s": start_s, "rise_s": rise_s, "max_step_s": max_step_s},
              "splits": {"train": train, "validation": validation, "test": test},
              "nmse": "test MSE divided by test target variance", "runs": []}
    for seed in seeds:
        u = np.random.default_rng(seed).uniform(0, 0.5, n_steps)
        record = {"seed": seed, "scores": {}, "lit_fraction": {}, "alpha": {}, "regime_valid": {}}
        seed_dir = out / f"seed-{seed}"
        seed_dir.mkdir()
        np.save(seed_dir / "input.npy", u)
        for regime, bias, gain in (("near", 70, 20), ("active", 90, 8)):
            drive, edges = held_drive(u, bias, gain, step_s, start_s, rise_s)
            for kind, bulb, resistance in (("switch", model, None), ("open", "open", None),
                                            ("resistor", "resistor", 1.475e6)):
                name = f"{regime}_{kind}"
                trace = run_transient(config, drive, float(edges[-1]), max_step_s, seed_dir / name,
                                      bulb=bulb, control_resistance_ohm=resistance)
                x = step_samples(trace, edges, 4)
                if kind == "open":
                    # A removed bulb has no current channel; reject numerical leakage from the 1e18-ohm surrogate.
                    x[:, 4:] = 0.0
                np.save(seed_dir / name / "features.npy", x)
                record["lit_fraction"][name] = float(np.mean(x[:, 4:] > 1e-6)) if kind == "switch" else None
                if kind == "switch":
                    on = trace.current_a[trace.time_s >= start_s] > 1e-6
                    valid = bool(np.all(on)) if regime == "active" else bool(np.any(on) and not np.all(on[-max(1, len(on) // 10):]))
                    record["regime_valid"][name] = valid
                    if not valid:
                        record["scores"][name] = None
                        record["alpha"][name] = None
                        continue
                scores = [narma_score(x, u, train, validation, alpha) for alpha in alphas]
                alpha = alphas[int(np.argmin(scores))]
                record["alpha"][name] = alpha
                record["scores"][name] = narma_score(x, u, (train[0], validation[1]), test, alpha)
        # Illustrative low-voltage diode and its own ballast; not a hardware LED rating.
        led_config = StudyConfig(1000, capacitance_f)
        led = LED(saturation_current_a=1e-18, ideality=2, max_drive_v=5)
        drive, edges = held_drive(u, 2, 2, step_s, start_s, rise_s)
        trace = run_transient(led_config, drive, float(edges[-1]), max_step_s, seed_dir / "led", bulb=led)
        x = step_samples(trace, edges, 4)
        np.save(seed_dir / "led" / "features.npy", x)
        alpha = alphas[int(np.argmin([narma_score(x, u, train, validation, a) for a in alphas]))]
        record["alpha"]["led"] = alpha
        record["scores"]["led"] = narma_score(x, u, (train[0], validation[1]), test, alpha)
        delays = input_delays(u, 10)
        products = np.column_stack([delays] + [delays[:, i] * delays[:, j]
                                  for i, j in combinations_with_replacement(range(10), 2)])
        for name, x in (("current_input", u[:, None]), ("linear_history", delays), ("nonlinear_history", products)):
            alpha = alphas[int(np.argmin([narma_score(x, u, train, validation, a) for a in alphas]))]
            record["alpha"][name] = alpha
            record["scores"][name] = narma_score(x, u, (train[0], validation[1]), test, alpha)
        y = narma10_target(u)[1:]
        record["scores"]["train_mean"] = nmse(y[slice(*test)], np.full(test[1] - test[0], y[train[0]:validation[1]].mean()))
        report["runs"].append(record)
        (out / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    return report
