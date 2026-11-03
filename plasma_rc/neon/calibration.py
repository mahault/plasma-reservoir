"""Grid calibration of the electrical switch model against measured traces."""

import csv
from itertools import product
import json
import math
from pathlib import Path

import numpy as np

from plasma_rc.neon.config import StudyConfig
from plasma_rc.neon.spice import NeonSwitch, run_transient

LAMP_PARAMETERS = ("strike_v", "extinction_v", "intercept_v", "on_resistance_ohm")
PARAMETERS = (*LAMP_PARAMETERS, "parasitic_capacitance_f")
MAX_CANDIDATES = 500


def load_reference(path):
    """Load synchronized drive and bulb-voltage samples from a CSV trace."""
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"time_s", "drive_v", "voltage_v"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"reference CSV must contain columns {sorted(required)}")
        has_current = "current_a" in reader.fieldnames
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError("reference CSV must contain at least two samples")
    try:
        times = np.asarray([float(row["time_s"]) for row in rows])
        drive = np.asarray([float(row["drive_v"]) for row in rows])
        voltage = np.asarray([float(row["voltage_v"]) for row in rows])
        current = np.asarray([float(row["current_a"]) for row in rows]) if has_current else None
    except (TypeError, ValueError) as error:
        raise ValueError("reference CSV contains a missing or non-numeric value") from error
    arrays = (times, drive, voltage) if current is None else (times, drive, voltage, current)
    if any(not np.isfinite(values).all() for values in arrays):
        raise ValueError("reference CSV values must be finite")
    if times[0] != 0 or np.any(np.diff(times) <= 0):
        raise ValueError("reference times must start at zero and be strictly increasing")
    return {"time_s": times, "drive_v": drive, "voltage_v": voltage, "current_a": current}


def validate_grid(raw):
    """Validate explicit candidate values; no device-specific defaults are supplied."""
    required = set(PARAMETERS) | {"ballast_ohm", "max_step_s"}
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError(f"grid must contain exactly {sorted(required)}")
    values, settings = {}, {}
    for name in PARAMETERS:
        candidates = raw[name]
        if not isinstance(candidates, list) or not candidates:
            raise ValueError(f"{name} must be a non-empty list")
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) for value in candidates):
            raise ValueError(f"{name} values must be finite numbers")
        values[name] = candidates
    for name in ("ballast_ohm", "max_step_s"):
        value = raw[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
        settings[name] = float(value)

    count = math.prod(len(values[name]) for name in PARAMETERS)
    if count > MAX_CANDIDATES:
        raise ValueError(f"grid has {count} combinations; maximum is {MAX_CANDIDATES}")
    combinations = list(product(*(values[name] for name in PARAMETERS)))
    accepted, rejected = [], []
    for combination in combinations:
        params = dict(zip(PARAMETERS, map(float, combination)))
        try:
            NeonSwitch(**{name: params[name] for name in LAMP_PARAMETERS})
            StudyConfig(ballast_ohm=settings["ballast_ohm"],
                        parasitic_capacitance_f=params["parasitic_capacitance_f"])
            accepted.append(params)
        except ValueError as error:
            rejected.append({"parameters": params, "reason": str(error)})
    if not accepted:
        raise ValueError("grid has no valid lamp parameter combinations")
    return {"candidates": accepted, "rejected": rejected, "ranges": values, "circuit": settings}


def _score(reference, trace):
    if reference["time_s"][0] < trace.time_s[0] or reference["time_s"][-1] > trace.time_s[-1]:
        raise ValueError("simulation trace does not cover every reference sample")
    scores = {}
    for channel in ("voltage_v", "current_a"):
        observed = reference[channel]
        if observed is None:
            continue
        scale = float(np.std(observed))
        if scale == 0:
            raise ValueError(f"reference {channel} must vary to be scored")
        predicted = np.interp(reference["time_s"], trace.time_s, getattr(trace, channel))
        scores[channel] = float(np.sqrt(np.mean((observed - predicted) ** 2)) / scale)
    return scores, float(np.mean(list(scores.values())))


def _simulate(reference, params, circuit, output_dir):
    config = StudyConfig(ballast_ohm=circuit["ballast_ohm"],
                         parasitic_capacitance_f=params["parasitic_capacitance_f"])
    drive = list(zip(reference["time_s"].tolist(), reference["drive_v"].tolist()))
    trace = run_transient(config, drive, float(reference["time_s"][-1]),
                          circuit["max_step_s"], output_dir,
                          bulb=NeonSwitch(**{name: params[name] for name in LAMP_PARAMETERS}))
    return _score(reference, trace)


def run_parameter_sweep(reference_path, grid_path, output_dir, *, validation_path=None):
    """Rank explicit model candidates against a calibration trace and optional holdout."""
    reference = load_reference(reference_path)
    validation = load_reference(validation_path) if validation_path is not None else None
    grid = validate_grid(json.loads(Path(grid_path).read_text()))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    candidates_dir = output / "candidates"
    candidates_dir.mkdir()
    results = []
    for index, params in enumerate(grid["candidates"]):
        scores, combined = _simulate(reference, params, grid["circuit"],
                                     candidates_dir / f"candidate-{index:04d}")
        results.append({"parameters": params, "channel_scores": scores,
                        "calibration_score": combined})
    best = min(results, key=lambda item: item["calibration_score"])
    best["validation_score"] = None
    best["validation_channel_scores"] = None
    if validation is not None:
        (output / "validation").mkdir()
        scores, combined = _simulate(validation, best["parameters"], grid["circuit"],
                                     output / "validation" / "best-candidate")
        best["validation_score"] = combined
        best["validation_channel_scores"] = scores
    report = {
        "interpretation": "sensitivity/calibration candidate; physical accuracy is not established",
        "model": "instantaneous hysteretic switch with linear conducting branch",
        "score": "mean channel-wise RMSE divided by observed channel standard deviation",
        "reference_channels": ["voltage_v"] + (["current_a"] if reference["current_a"] is not None else []),
        "calibration_trace": str(reference_path),
        "validation_trace": str(validation_path) if validation_path is not None else None,
        "grid": grid["ranges"],
        "circuit": grid["circuit"],
        "rejected_combinations": grid["rejected"],
        "results": results,
        "best": best,
    }
    (output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    return report
