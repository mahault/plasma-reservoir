from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from scipy.signal import welch

from plasma_rc.acquisition.session import parse_audio_path
from plasma_rc.acquisition.stimuli import (
    generate_dataset,
    generate_noise,
    generate_silence,
    write_wav,
)


def test_generate_silence_correct_length_and_all_zero():
    fs = 44100
    duration_s = 1.5
    samples = generate_silence(duration_s, fs)
    assert samples.shape == (int(duration_s * fs),)
    assert np.all(samples == 0.0)


def test_generate_noise_correct_length():
    fs = 44100
    duration_s = 1.5
    samples = generate_noise(duration_s, fs, seed=0)
    assert samples.shape == (int(duration_s * fs),)


def test_generate_noise_is_band_limited():
    fs = 44100
    duration_s = 3.0
    band = (300.0, 3400.0)
    samples = generate_noise(duration_s, fs, seed=1, band=band)
    freqs, psd = welch(samples, fs=fs, nperseg=4096)
    in_band = (freqs >= band[0]) & (freqs <= band[1])
    out_band = (freqs > 20.0) & ~in_band
    in_power = psd[in_band].mean()
    out_power = psd[out_band].mean()
    assert out_power < in_power * 0.05


def test_generate_noise_reproducible_with_seed():
    fs = 44100
    duration_s = 1.5
    a = generate_noise(duration_s, fs, seed=7)
    b = generate_noise(duration_s, fs, seed=7)
    c = generate_noise(duration_s, fs, seed=8)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_generate_noise_peak_normalized():
    fs = 44100
    duration_s = 1.5
    target_peak = 0.316  # ~-10 dBFS, measured median peak of the existing word corpus
    samples = generate_noise(duration_s, fs, seed=2, peak=target_peak)
    assert np.max(np.abs(samples)) == pytest.approx(target_peak, rel=0.02)


def test_write_wav_roundtrip(tmp_path: Path):
    fs = 44100
    samples = generate_noise(1.0, fs, seed=3)
    path = tmp_path / "nested" / "n01.wav"
    write_wav(path, samples, fs)
    assert path.exists()
    read_back, read_fs = sf.read(str(path), dtype="float32")
    assert read_fs == fs
    np.testing.assert_allclose(read_back, samples, atol=1e-4)


def test_generate_dataset_writes_parseable_silence_files(tmp_path: Path):
    audio_root = tmp_path / "data" / "Data"
    paths = generate_dataset("silence", count=15, audio_root=audio_root, duration_s=1.5, fs=44100)
    assert len(paths) == 15
    for p in paths:
        assert p.exists()
        meta = parse_audio_path(p, audio_root)
        assert meta is not None
        assert meta.condition == "silence"
    assert sorted(p.name for p in paths) == [f"s{i:02d}.wav" for i in range(1, 16)]


def test_generate_dataset_writes_parseable_noise_files(tmp_path: Path):
    audio_root = tmp_path / "data" / "Data"
    paths = generate_dataset("noise", count=15, audio_root=audio_root, duration_s=1.5, fs=44100)
    assert len(paths) == 15
    for p in paths:
        meta = parse_audio_path(p, audio_root)
        assert meta is not None
        assert meta.condition == "noise"
    assert sorted(p.name for p in paths) == [f"n{i:02d}.wav" for i in range(1, 16)]
