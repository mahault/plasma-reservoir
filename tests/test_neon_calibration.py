import csv
import json
import shutil

import pytest

from plasma_rc.neon.calibration import load_reference, validate_grid, run_parameter_sweep
from plasma_rc.neon.config import StudyConfig
from plasma_rc.neon.spice import NeonSwitch, run_transient


def _grid():
    return {
        "strike_v": [75.0],
        "extinction_v": [52.0],
        "intercept_v": [50.0],
        "on_resistance_ohm": [100_000.0],
        "parasitic_capacitance_f": [1e-9],
        "ballast_ohm": 1e6,
        "max_step_s": 1e-6,
    }


def _write_reference(path, trace):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("time_s", "drive_v", "voltage_v", "current_a"))
        writer.writerows(zip(trace.time_s, trace.drive_v, trace.voltage_v, trace.current_a))


def test_reference_csv_requires_finite_aligned_measurements(tmp_path):
    path = tmp_path / "reference.csv"
    path.write_text("time_s,drive_v,voltage_v\n0,0,0\n0.1,10,5\n")
    reference = load_reference(path)
    assert reference["current_a"] is None
    assert reference["voltage_v"] == pytest.approx([0, 5])

    path.write_text("time_s,drive_v,voltage_v\n0,0,0\n0,10,5\n")
    with pytest.raises(ValueError, match="strictly increasing"):
        load_reference(path)


def test_parameter_grid_requires_explicit_values_and_physical_ordering():
    result = validate_grid(_grid())
    assert len(result["candidates"]) == 1
    mixed = _grid()
    mixed["strike_v"] = [49.0, 75.0]
    result = validate_grid(mixed)
    assert len(result["candidates"]) == 1
    assert len(result["rejected"]) == 1
    invalid = _grid()
    invalid["strike_v"] = [49.0]
    with pytest.raises(ValueError, match="no valid"):
        validate_grid(invalid)


def test_sweep_selects_known_simulated_candidate_and_keeps_validation_separate(tmp_path):
    if not shutil.which("ngspice"):
        pytest.skip("ngspice required")

    config = StudyConfig(ballast_ohm=1e6, parasitic_capacitance_f=1e-9)
    bulb = NeonSwitch(75, 52, 50, 100e3)
    drive = [(0, 0), (0.0001, 90), (0.005, 90), (0.0051, 40), (0.01, 40)]
    trace = run_transient(config, drive, 0.01, 1e-6, tmp_path / "reference-run", bulb=bulb)
    calibration_csv = tmp_path / "calibration.csv"
    _write_reference(calibration_csv, trace)

    validation_trace = run_transient(config, drive, 0.01, 1e-6, tmp_path / "validation-run", bulb=bulb)
    validation_csv = tmp_path / "validation.csv"
    _write_reference(validation_csv, validation_trace)

    grid = _grid()
    grid["strike_v"] = [70.0, 75.0]
    grid["parasitic_capacitance_f"] = [0.5e-9, 1e-9]
    grid_path = tmp_path / "grid.json"
    grid_path.write_text(json.dumps(grid))
    result = run_parameter_sweep(calibration_csv, grid_path, tmp_path / "sweep",
                                 validation_path=validation_csv)

    assert result["best"]["parameters"]["strike_v"] == 75
    assert result["best"]["parameters"]["parasitic_capacitance_f"] == 1e-9
    assert result["best"]["calibration_score"] < 0.01
    assert result["best"]["validation_score"] < 0.01
    assert result["interpretation"] == "sensitivity/calibration candidate; physical accuracy is not established"
    saved = json.loads((tmp_path / "sweep" / "summary.json").read_text())
    assert saved["best"]["parameters"] == result["best"]["parameters"]
    with pytest.raises(FileExistsError):
        run_parameter_sweep(calibration_csv, grid_path, tmp_path / "sweep")
