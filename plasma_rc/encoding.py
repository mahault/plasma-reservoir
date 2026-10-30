"""Audio -> drive u(t) for the circuit's input (docs/simulation.md §5).

Three encodings, each a sequence of values in about [-1, 1] that the DAC holds for a fixed number
of ticks; silence maps to 0 (DAC mid-scale, the circuit's rest point):
  raw       the waveform itself, resampled to the tick rate (as designed, D-11)
  envelope  frame RMS, one held value per frame (amplitude only)
  masked    band RMS per frame, mixed by a fixed random binary mask into n_virtual held sub-steps:
            time multiplexing of a single node (Appeltant et al., Nat. Commun. 2, 468, 2011;
            binary mask as Torrejon et al., Nature 547, 428, 2017)
Scaling to [-1, 1] is one constant per dataset (set by the caller), like fixing the volume once.
"""

from __future__ import annotations

import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, resample_poly, sosfilt

MP3_FS = 16000  # ffmpeg decode rate for the recorded words


def load_audio(path: str | Path) -> tuple[np.ndarray, int]:
    """Mono float samples (int16 full scale = 1) and their rate; mp3 is decoded by ffmpeg."""
    path = Path(path)
    if path.suffix.lower() == ".wav":
        fs, x = wavfile.read(path)
    else:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(MP3_FS), "-"],
                             capture_output=True, check=True).stdout
        fs, x = MP3_FS, np.frombuffer(raw, dtype="<i2")
    x = x.astype(np.float64)
    return (x.mean(axis=1) if x.ndim == 2 else x) / 32768.0, int(fs)


def to_ticks(x: np.ndarray, fs: int, tick_hz: float) -> np.ndarray:
    """Resample to one value per tick (polyphase, anti-aliased)."""
    r = Fraction(tick_hz / fs).limit_denominator(1000)
    return resample_poly(x, r.numerator, r.denominator)


def frame_rms(x: np.ndarray, fs: int, frame_s: float) -> np.ndarray:
    n = int(round(frame_s * fs))
    k = len(x) // n
    return np.sqrt(np.mean(x[: k * n].reshape(k, n) ** 2, axis=1))


def band_rms(x: np.ndarray, fs: int, frame_s: float, n_bands: int = 8, f_lo: float = 100.0) -> np.ndarray:
    """(frames, n_bands) RMS of log-spaced 2nd-order Butterworth bands from f_lo to 0.45 fs."""
    edges = np.geomspace(f_lo, 0.45 * fs, n_bands + 1)
    bands = [sosfilt(butter(2, (lo, hi), btype="bandpass", fs=fs, output="sos"), x) for lo, hi in zip(edges, edges[1:])]
    return np.column_stack([frame_rms(b, fs, frame_s) for b in bands])


def binary_mask(n_virtual: int, n_bands: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).choice([-1.0, 1.0], size=(n_virtual, n_bands))


def masked_drive(bands: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Per frame, n_virtual sub-steps mask @ bands[frame], flattened in time order."""
    return (bands @ mask.T).ravel()
