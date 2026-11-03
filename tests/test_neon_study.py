import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest

from plasma_rc.neon.study import run_study, run_pulse_study
from plasma_rc.neon.report import analyze_study, summarize_scores, correct_open_controls
from plasma_rc.neon.optical import analyze_optical
from plasma_rc.neon.figures import generate_figures, regime_title

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice required")


def test_study_saves_paired_results_and_does_not_overwrite(tmp_path):
    out = tmp_path / "study"
    run_study(out, seeds=[7], n_steps=80)
    report = json.loads((out / "summary.json").read_text())
    assert report["seeds"] == [7]
    assert set(report["runs"][0]["scores"]) >= {"near_switch", "near_open", "active_switch", "active_open"}
    assert "led" in report["runs"][0]["scores"]
    led = json.loads((out / "seed-7" / "led" / "config.json").read_text())
    assert max(voltage for _, voltage in led["drive"]) <= 5
    assert (out / "seed-7" / "near_switch" / "circuit.cir").exists()
    # Open control has no physical current channel; solver leakage must not be standardized into signal.
    features = np.load(out / "seed-7" / "near_open" / "features.npy")
    assert np.all(features[:, 4:] == 0)
    with pytest.raises(FileExistsError):
        run_study(out, seeds=[7], n_steps=80)


def test_study_accepts_timestep_for_convergence_check(tmp_path):
    out = tmp_path / "fine"
    report = run_study(out, seeds=[8], n_steps=80, max_step_s=10e-6)
    assert report["timing"]["max_step_s"] == pytest.approx(10e-6)
    source = Path(__file__).resolve().parents[1] / "plasma_rc/neon/spice.py"
    assert report["source_sha256"]["spice.py"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_report_reads_saved_run_and_checks_glow(tmp_path):
    out = tmp_path / "study"
    run_study(out, seeds=[4], n_steps=80)
    analysis = analyze_study(out)
    assert analysis["seeds"]["4"]["active_switch"]["switch_events"] >= 0
    assert "truncated_total" in analysis["seeds"]["4"]["near_switch"]["ipc"]
    assert "led" in analysis["seeds"]["4"]
    assert len(analysis["seeds"]["4"]["near_switch"]["delay_capacity"]["degree_1"]) == 10
    assert (out / "analysis.json").exists()


def test_study_records_capacitance_sensitivity_setting(tmp_path):
    out = tmp_path / "sensitivity"
    run_study(out, seeds=[4], n_steps=80, capacitance_f=2e-9)
    config = json.loads((out / "seed-4" / "near_switch" / "config.json").read_text())
    assert config["circuit"]["parasitic_capacitance_f"] == pytest.approx(2e-9)


def test_study_uses_specified_neon_ballast(tmp_path):
    out = tmp_path / "ballast"
    run_study(out, seeds=[4], n_steps=80, ballast_ohm=2e6)
    config = json.loads((out / "seed-4" / "near_switch" / "config.json").read_text())
    assert config["circuit"]["ballast_ohm"] == pytest.approx(2e6)
    led = json.loads((out / "seed-4" / "led" / "config.json").read_text())
    assert led["circuit"]["ballast_ohm"] == 1000
    result = json.loads((out / "summary.json").read_text())["runs"][0]
    assert result["regime_valid"]["active_switch"] is False
    assert result["scores"]["active_switch"] is None


def test_near_regime_does_not_claim_an_always_latched_bulb(tmp_path):
    out = tmp_path / "latched"
    report = run_study(out, seeds=[4], n_steps=80, ballast_ohm=0.5e6)
    result = report["runs"][0]
    assert result["regime_valid"]["near_switch"] is False
    assert result["scores"]["near_switch"] is None
    assert "invalid" in regime_title(result, "near_switch").lower()


def test_score_summary_reports_paired_difference():
    data = {"runs": [{"scores": {"near_switch": 0.4, "near_open": 0.6}},
                     {"scores": {"near_switch": 0.8, "near_open": 0.5}}]}
    result = summarize_scores(data)
    assert result["near_switch"]["mean"] == pytest.approx(0.6)
    assert result["near_switch_minus_open"]["mean"] == pytest.approx(0.05)


def test_score_summary_ignores_invalid_regimes_in_paired_comparisons():
    data = {"runs": [{"scores": {"active_switch": None, "active_open": 0.6}},
                     {"scores": {"active_switch": 0.8, "active_open": 0.5}}]}
    result = summarize_scores(data)
    assert result["active_switch"]["mean"] == pytest.approx(0.8)
    assert result["active_switch_minus_open"]["mean"] == pytest.approx(0.3)


def test_correction_does_not_standardize_open_circuit_leakage(tmp_path):
    out = tmp_path / "study"
    run_study(out, seeds=[4], n_steps=80)
    path = out / "seed-4" / "near_open" / "features.npy"
    x = np.load(path)
    x[:, 4:] = np.random.default_rng(1).normal(0, 1e-16, x[:, 4:].shape)
    np.save(path, x)
    corrected = correct_open_controls(out)
    original = json.loads((out / "summary.json").read_text())
    assert corrected["runs"][0]["scores"]["near_open"] == pytest.approx(original["runs"][0]["scores"]["near_open"])
    analysis = analyze_study(out)
    assert analysis["seeds"]["4"]["near_open"]["delay_capacity"]["degree_1"] == pytest.approx(
        corrected["runs"][0]["corrected_delay_capacity"]["near_open"]["degree_1"])


def test_optical_study_preserves_dark_control_and_reports_all_channels(tmp_path):
    source, out = tmp_path / "study", tmp_path / "optical"
    run_study(source, seeds=[4], n_steps=80)
    result = analyze_optical(source, out)
    run = result["runs"][0]
    assert set(run["scores"]["near_switch"]) == {"brightness", "frequency", "oscillation", "combined", "combined_voltage"}
    assert "led" in run["scores"]
    assert len(run["correlations"]["near_switch"]) == 4
    assert np.any(np.load(out / "seed-4" / "led.npy")[:, 0] > 0)
    assert np.all(np.load(out / "seed-4" / "near_resistor.npy") == 0)
    with pytest.raises(FileExistsError):
        analyze_optical(source, out)


def test_optical_study_records_sampling_resolution(tmp_path):
    source, out = tmp_path / "study", tmp_path / "optical"
    run_study(source, seeds=[4], n_steps=80)
    result = analyze_optical(source, out, samples=8)
    assert result["samples_per_step"] == 8


def test_figures_generate_from_saved_data_without_overwriting(tmp_path):
    source, optical, figures, pulse = tmp_path / "study", tmp_path / "optical", tmp_path / "figures", tmp_path / "pulse"
    run_study(source, seeds=[4], n_steps=80)
    analyze_study(source)
    analyze_optical(source, optical, samples=8)
    run_pulse_study(pulse, [0.5e6, 2e6], 1e-9)
    generate_figures(source, optical, figures, pulse)
    assert (figures / "narma.png").is_file()
    assert (figures / "correlation.png").is_file()
    assert (figures / "traces.png").is_file()
    assert (figures / "prediction.png").is_file()
    prediction = np.load(figures / "prediction.npz")
    expected = json.loads((optical / "summary.json").read_text())["runs"][0]["scores"]["near_switch"]["combined_voltage"]
    assert np.mean((prediction["target"] - prediction["prediction"]) ** 2) / np.var(prediction["target"]) == pytest.approx(expected)
    assert (figures / "ipc.png").is_file()
    assert (figures / "pulse.png").is_file()
    with pytest.raises(FileExistsError):
        generate_figures(source, optical, figures, pulse)


def test_ballast_changes_time_to_first_ignition(tmp_path):
    result = run_pulse_study(tmp_path / "pulses", [0.5e6, 2e6], capacitance_f=1e-9)
    fast, slow = result["runs"]
    assert 0 < fast["first_strike_delay_s"] < slow["first_strike_delay_s"]


def test_experiment_command_saves_results_and_figures(tmp_path):
    output = tmp_path / "run"
    subprocess.run([sys.executable, "-m", "experiments.neon", str(output), "--steps", "80",
                    "--seeds", "1", "--ballast", "2000000", "--capacitance", "2e-9"], check=True, capture_output=True)
    assert (output / "study" / "summary.json").exists()
    assert (output / "optical" / "summary.json").exists()
    assert (output / "figures" / "narma.png").exists()
    assert (output / "pulse" / "summary.json").exists()
    config = json.loads((output / "study" / "seed-0" / "near_switch" / "config.json").read_text())
    assert config["circuit"]["ballast_ohm"] == 2e6
