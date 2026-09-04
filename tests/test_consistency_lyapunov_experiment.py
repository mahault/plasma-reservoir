from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from experiments.consistency_lyapunov import build_report
from plasma_rc.acquisition.serial_io import RawCapture
from plasma_rc.acquisition.session import write_npz


def _write_capture(path: Path, brightness: np.ndarray, audio_in: np.ndarray, fs_hz: int) -> None:
    capture = RawCapture(
        t_us=np.arange(len(brightness), dtype=np.int64) * (1_000_000 // fs_hz),
        audio_in=audio_in.astype(np.uint16),
        brightness=brightness.astype(np.uint16),
        dropped=0,
        frames_sent=1,
        sync_offset_us=0,
        fs_hz=fs_hz,
    )
    write_npz(path, capture)


def test_build_report_computes_stimulus_and_silence_consistency(tmp_path: Path):
    fs_hz = 100
    out_dir = tmp_path / "out"
    stim_dir = out_dir / "raw" / "na" / "consistency" / "noise_repeat"
    silence_dir = out_dir / "raw" / "na" / "silence" / "silence"

    rng = np.random.default_rng(0)
    base = rng.integers(1000, 3000, size=50)
    audio_base = rng.integers(2000, 2100, size=50)  # realistic near-constant ADC tap, never exactly flat
    for i in range(1, 6):
        # near-identical repeats (small noise) -> high consistency expected
        _write_capture(
            stim_dir / f"r{i:02d}.npz",
            base + rng.integers(-2, 2, size=50),
            audio_base + rng.integers(-1, 1, size=50),
            fs_hz,
        )

    for i in range(1, 6):
        # independent noise repeats -> low consistency expected (noise floor)
        _write_capture(
            silence_dir / f"s{i:02d}.npz", rng.integers(2040, 2056, size=50), np.zeros(50), fs_hz
        )

    report = build_report(out_dir, stimulus_label="noise_repeat", discard_s=0.0, fs_hz=fs_hz)

    assert report["stimulus_label"] == "noise_repeat"
    assert report["n_repeats"] == 5
    assert report["n_silence_repeats"] == 5
    assert -1.0 <= report["consistency_brightness"] <= 1.0
    assert -1.0 <= report["consistency_silence_floor"] <= 1.0
    # near-identical repeats should be far more consistent than independent noise
    assert report["consistency_brightness"] > report["consistency_silence_floor"]
    assert "lyapunov_estimate" in report
