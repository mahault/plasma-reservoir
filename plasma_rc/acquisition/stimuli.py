"""Generate silence/noise stimuli wav files for the acquisition pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt


def generate_silence(duration_s: float, fs: int) -> np.ndarray:
    n_samples = int(duration_s * fs)
    return np.zeros(n_samples, dtype=np.float32)


def generate_noise(
    duration_s: float,
    fs: int,
    band: tuple[float, float] = (300.0, 3400.0),
    seed: int | None = None,
    peak: float = 0.316,  # ~-10 dBFS, measured median peak of the existing word corpus
) -> np.ndarray:
    n_samples = int(duration_s * fs)
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(n_samples)
    sos = butter(4, band, btype="bandpass", fs=fs, output="sos")
    filtered = sosfiltfilt(sos, white)
    normalized = filtered / np.max(np.abs(filtered)) * peak
    return normalized.astype(np.float32)


def write_wav(path: Path, samples: np.ndarray, fs: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), samples, fs, subtype="PCM_16")


_PREFIX = {"silence": "s", "noise": "n"}


def generate_dataset(
    kind: str,
    count: int,
    audio_root: Path,
    duration_s: float = 1.5,
    fs: int = 44100,
) -> list[Path]:
    prefix = _PREFIX[kind]
    paths = []
    for i in range(1, count + 1):
        if kind == "silence":
            samples = generate_silence(duration_s, fs)
        else:
            samples = generate_noise(duration_s, fs, seed=i)
        path = audio_root / kind / f"{prefix}{i:02d}.wav"
        write_wav(path, samples, fs)
        paths.append(path)
    return paths
