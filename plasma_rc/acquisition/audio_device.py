"""Play trial audio to the breakout; decode mp3; remember the output device."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import Config, persist_audio_device


@dataclass
class PlayResult:
    t_play_start_pc: float
    t_play_end_pc: float
    true_duration_s: float
    measured_wall_s: float
    process_overhead_s: float


def list_output_devices() -> list[dict[str, Any]]:
    sd = _sounddevice()
    devices = []
    for i, dev in enumerate(sd.query_devices()):
        if int(dev.get("max_output_channels", 0)) > 0:
            devices.append(
                {
                    "index": i,
                    "name": dev.get("name", ""),
                    "max_output_channels": int(dev["max_output_channels"]),
                }
            )
    return devices


def select_device(cfg: Config) -> int:
    if cfg.audio_device is not None:
        return cfg.audio_device
    devices = list_output_devices()
    if not devices:
        raise RuntimeError("no audio output devices")
    print("Audio output devices:")
    for d in devices:
        print(f"  {d['index']}: {d['name']}")
    raw = input("Select device index: ").strip()
    index = int(raw)
    persist_audio_device(cfg, index)
    return index


def decode(path: str | Path) -> tuple[np.ndarray, int]:
    path = Path(path)
    try:
        import soundfile as sf

        data, sr = sf.read(str(path), dtype="float32", always_2d=False)
        return np.asarray(data, dtype=np.float32), int(sr)
    except Exception:
        pass
    try:
        from pydub import AudioSegment
    except ImportError as exc:
        raise RuntimeError(
            "cannot decode audio: install soundfile with mp3 support, or pydub+ffmpeg"
        ) from exc
    seg = AudioSegment.from_file(str(path))
    samples = np.array(seg.get_array_of_samples())
    if seg.channels > 1:
        samples = samples.reshape((-1, seg.channels))
    peak = float(1 << (8 * seg.sample_width - 1))
    data = samples.astype(np.float32) / peak
    return data, int(seg.frame_rate)


def play(path: str | Path, device: int) -> PlayResult:
    import time

    sd = _sounddevice()
    samples, sr = decode(path)
    true_duration_s = float(samples.shape[0]) / float(sr)
    t0 = time.perf_counter()
    sd.play(samples, sr, device=device)
    sd.wait()
    t1 = time.perf_counter()
    measured = t1 - t0
    return PlayResult(
        t_play_start_pc=t0,
        t_play_end_pc=t1,
        true_duration_s=true_duration_s,
        measured_wall_s=measured,
        process_overhead_s=measured - true_duration_s,
    )


def _sounddevice():
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("sounddevice is required: pip install -e '.[acquisition]'") from exc
    return sd
