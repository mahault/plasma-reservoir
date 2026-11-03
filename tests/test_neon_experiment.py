"""Acquisition orchestration tested without physical hardware."""
import numpy as np
import pytest

from plasma_rc.neon.capture import RunConditions, load_recording
from plasma_rc.neon.experiment import record_trial, analyze_recording, save_analysis, compare_trials
from plasma_rc.neon.records import Capture
from plasma_rc.neon.figures import generate_figures
from experiments import analyze


def test_trial_logs_seeded_input_and_checks_capture(tmp_path, monkeypatch):
    class FakeBoard:
        def start(self, command):
            self.command = command
        def stop(self):
            return Capture(np.arange(8), np.arange(8), "12", np.array([], dtype=int),
                           np.array([], dtype=int), 999, 0, clock_hz=1e6, adc_bits=12,
                           v_ref=3.3, board="teensy", source="physical")
    board = FakeBoard()
    monkeypatch.setattr("time.sleep", lambda _: None)
    conditions = RunConditions("led", "led", 1000, 5, 0.001)
    path = tmp_path / "trial.npz"
    record_trial(board, path, conditions, seed=1, n_steps=4, ticks_per_step=2, tick_hz=1000)
    assert board.command == "STEPS,0,0,1,4,2"
    cap, saved_conditions, u, tps = load_recording(path)
    assert saved_conditions == conditions
    assert len(u) == 4 and np.all((u >= 0) & (u <= 0.5))
    assert tps == 2
    with np.load(path, allow_pickle=False) as data:
        assert int(data["seed"]) == 1
        assert str(data["stimulus_command"]) == board.command


def test_existing_output_is_rejected_before_board_starts(tmp_path):
    class Board:
        started = False
        def start(self, command):
            self.started = True
    path = tmp_path / "trial.npz"
    path.write_bytes(b"do not replace")
    board = Board()
    with pytest.raises(FileExistsError):
        record_trial(board, path, RunConditions("led", "led", 1000, 5, 0.001),
                     seed=1, n_steps=4, ticks_per_step=2, tick_hz=1000)
    assert board.started is False
    assert path.read_bytes() == b"do not replace"


def test_compare_trials_requires_matching_input_sequences():
    neon = {"input_sha256": "same", "step_duration_s": .001, "recording_id": "n", "conditions": {"device": "neon", "device_id": "B1"}, "narma_nmse": {"combined": 0.3}}
    led = {"input_sha256": "same", "step_duration_s": .001, "recording_id": "l", "conditions": {"device": "led", "device_id": "L1"}, "narma_nmse": {"combined": 0.5}}
    result = compare_trials([neon, led])
    assert result[0]["neon_minus_led_nmse"] == pytest.approx(-0.2)
    assert result[0]["neon_recording"] == "n" and result[0]["led_recording"] == "l"
    led["step_duration_s"] = .1
    assert compare_trials([neon, led]) == []
    led["step_duration_s"] = .001
    led["input_sha256"] = "different"
    assert compare_trials([neon, led]) == []


def test_compare_command_saves_pairs(tmp_path):
    import json
    from experiments import compare
    values = [
        {"input_sha256": "same", "step_duration_s": .001, "recording_id": "n", "conditions": {"device": "neon", "device_id": "B1"}, "narma_nmse": {"combined": 0.3}},
        {"input_sha256": "same", "step_duration_s": .001, "recording_id": "l", "conditions": {"device": "led", "device_id": "L1"}, "narma_nmse": {"combined": 0.5}},
    ]
    paths = [tmp_path / "a.json", tmp_path / "b.json"]
    for path, value in zip(paths, values):
        path.write_text(json.dumps(value))
    output = tmp_path / "pairs.json"
    compare.main([str(output), *map(str, paths)])
    assert len(json.loads(output.read_text())["pairs"]) == 1


def test_analyze_recording_uses_calibrated_channels_and_stored_input(tmp_path):
    from plasma_rc.neon.capture import save_recording
    n, tps = 80, 6
    rng = np.random.default_rng(7)
    u = rng.uniform(0, 0.5, n)
    values = np.empty(n * tps, dtype=int)
    values[0::3] = np.repeat(np.round(u * 1000).astype(int), 2)
    values[1::3] = np.repeat(np.round(u * 1500).astype(int), 2)
    values[2::3] = np.repeat(np.round(u * 2000).astype(int), 2)
    cap = Capture(np.arange(n*tps), values, "012", np.array([], dtype=int), np.array([], dtype=int),
                  999, 0, clock_hz=1e6, adc_bits=12, v_ref=3.3, board="fake", source="physical")
    meta = RunConditions("led", "led", 1000, 5, .001, "L1", 22, 0,
                         "0", "1", "2", 1, 2, 0)
    path = tmp_path / "trial.npz"
    save_recording(path, cap, meta, u, tps)
    result = analyze_recording(path, train=(10, 40), validation=(40, 55), test=(55, 79))
    assert len(result["measured_drive_v"]) == n
    assert result["drive_input_correlation"] > 0.99
    assert set(result["narma_nmse"]) >= {"brightness", "frequency", "oscillation", "voltage", "combined"}
    assert len(result["correlations"]) == 4
    analysis_path = tmp_path / "analysis.json"
    save_analysis(analysis_path, result)
    figures = tmp_path / "figures"
    generate_figures(result, figures)
    assert (figures / "features.png").exists()
    assert (figures / "correlation.png").exists()
    assert (figures / "narma.png").exists()
    with pytest.raises(FileExistsError):
        save_analysis(analysis_path, result)
    analyze.main([str(path), str(tmp_path / "report")])
    assert (tmp_path / "report" / "analysis.json").exists()
    assert (tmp_path / "report" / "figures" / "narma.png").exists()
