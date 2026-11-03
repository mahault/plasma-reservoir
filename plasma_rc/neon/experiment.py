"""Acquire a seeded NARMA input trial."""

import math
import json
import hashlib
import time
from pathlib import Path
from dataclasses import asdict
import numpy as np

from plasma_rc.neon.capture import RunConditions, channel_volts, extract_recorded_steps, load_recording, save_recording
from plasma_rc.neon.analysis import characterize_ipc, feature_correlations, narma_score
from plasma_rc.neon.stimuli import xorshift32_levels


def compare_trials(trials):
    """Return matched-input neon/LED pairs without pooling repeated observations."""
    neon = [r for r in trials if r["conditions"]["device"] == "neon"]
    leds = [r for r in trials if r["conditions"]["device"] == "led"]
    return [{"input_sha256": a["input_sha256"], "neon": a["conditions"], "led": b["conditions"],
             "neon_recording": a["recording_id"], "led_recording": b["recording_id"],
             "step_duration_s": a["step_duration_s"],
             "neon_minus_led_nmse": a["narma_nmse"]["combined"] - b["narma_nmse"]["combined"]}
            for a in neon for b in leds if a["input_sha256"] and a["input_sha256"] == b["input_sha256"]
            and a.get("splits") == b.get("splits") and a.get("step_duration_s") is not None
            and math.isclose(a["step_duration_s"], b.get("step_duration_s", 0), rel_tol=1e-9)]


def save_analysis(path, result):
    """Save finite JSON without replacing an earlier analysis."""
    payload = json.dumps(result, indent=2, allow_nan=False)
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(payload)


def analyze_recording(path, train, validation, test):
    """Analyze recorded signals; benchmark target uses logged commanded steps."""
    capture, meta, u, tps = load_recording(path)
    if meta.drive_pin is None:
        raise ValueError("recording lacks sensor channel calibration")
    x = extract_recorded_steps(capture, tps, len(u), meta.light_pin, meta.voltage_pin,
                               meta.dark_voltage_v, meta.divider_gain)
    drive_t, drive_adc = channel_volts(capture, meta.drive_pin)
    drive_step = np.rint(drive_t * capture.tick_hz).astype(int) // tps
    measured_drive = []
    for k in range(len(u)):
        values = drive_adc[drive_step == k]
        if not len(values):
            raise ValueError(f"missing drive sample in step {k}")
        measured_drive.append(float(values.mean() * meta.drive_gain))
    subsets = {"brightness": x[:, :1], "frequency": x[:, 1:2], "oscillation": x[:, 2:3],
               "voltage": x[:, 3:], "optical": x[:, :3], "combined": x}
    alphas = (0.01, 0.1, 1.0, 10.0)
    scores, selected = {}, {}
    for name, features in subsets.items():
        alpha = alphas[int(np.argmin([narma_score(features, u, train, validation, a) for a in alphas]))]
        selected[name] = alpha
        scores[name] = narma_score(features, u, (train[0], validation[1]), test, alpha)
    return {"conditions": asdict(meta), "input_kind": "commanded, quantized; measured drive is separately recorded",
            "recording_id": str(Path(path).resolve()), "step_duration_s": tps / capture.tick_hz,
            "input_sha256": hashlib.sha256(np.asarray(u, dtype="<f8").tobytes()).hexdigest(),
            "measured_drive_v": measured_drive,
            "drive_input_correlation": feature_correlations(np.column_stack((u, measured_drive)))[0][1],
            "narma_nmse": scores, "alpha": selected,
            "correlations": feature_correlations(x[slice(*train)]),
            "ipc": characterize_ipc(x, u, (train[0], validation[1]), test, 10, seed=1),
            "ipc_caveat": "continuous Legendre basis is approximate for quantized input; finite sample and truncated basis",
            "features": x.tolist(), "splits": {"train": train, "validation": validation, "test": test}}


def record_trial(board, path, conditions, seed, n_steps, ticks_per_step, tick_hz):
    """Record one board-generated sequence; voltage/current limits are operator settings, not interlocks."""
    if not isinstance(conditions, RunConditions):
        raise ValueError("validated run conditions are required")
    if Path(path).exists():
        raise FileExistsError(path)
    if (not isinstance(n_steps, int) or n_steps <= 0 or not isinstance(ticks_per_step, int) or
            ticks_per_step <= 0 or not math.isfinite(tick_hz) or tick_hz <= 0):
        raise ValueError("invalid acquisition timing")
    levels = xorshift32_levels(seed, n_steps)
    command = f"STEPS,0,0,{seed},{n_steps},{ticks_per_step}"
    board.start(command)
    try:
        time.sleep((n_steps + 1) * ticks_per_step / tick_hz + 0.2)
    finally:
        capture = board.stop()
    if not math.isclose(capture.tick_hz, tick_hz, rel_tol=1e-9):
        raise ValueError("capture clock disagrees with requested timing")
    save_recording(path, capture, conditions, levels.astype(float) / 510, ticks_per_step,
                   seed=seed, stimulus_command=command)
