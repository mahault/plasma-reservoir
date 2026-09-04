"""Consistency (twin-trial) Lyapunov-proxy experiment for the plasma reservoir.

Computes the pairwise-correlation consistency measure C (Uchida/Yoshimura, see
research/lyapunov_consistency_experimental_design.md) for a repeated stimulus
recorded under data/Data/consistency/<stimulus_label>/r{NN}.wav, alongside a
noise floor from the existing (already bit-identical) silence dataset, and a
cross-check against the repo's existing lyapunov_estimate() slope method.

Usage:
    python experiments/consistency_lyapunov.py --out-dir data/out --stimulus noise_repeat
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from plasma_rc.characterization.consistency import load_repeat_traces, pairwise_consistency
from plasma_rc.characterization.separation import lyapunov_estimate


def build_report(
    out_dir: Path, stimulus_label: str, discard_s: float, fs_hz: int
) -> dict:
    stim_dir = out_dir / "raw" / "na" / "consistency" / stimulus_label
    silence_dir = out_dir / "raw" / "na" / "silence" / "silence"

    stim_npz = sorted(stim_dir.glob("*.npz"))
    silence_npz = sorted(silence_dir.glob("*.npz"))
    if len(stim_npz) < 2:
        raise RuntimeError(f"need at least 2 repeat recordings under {stim_dir}, found {len(stim_npz)}")
    if len(silence_npz) < 2:
        raise RuntimeError(f"need at least 2 silence recordings under {silence_dir}, found {len(silence_npz)}")

    brightness = load_repeat_traces(stim_npz, "brightness", discard_s, fs_hz)
    audio_in = load_repeat_traces(stim_npz, "audio_in", discard_s, fs_hz)
    silence_brightness = load_repeat_traces(silence_npz, "brightness", discard_s, fs_hz)

    c_brightness = pairwise_consistency(brightness)
    c_audio_in = pairwise_consistency(audio_in)
    c_silence_floor = pairwise_consistency(silence_brightness)

    lyap = lyapunov_estimate(brightness[:, :, np.newaxis], dt=1.0 / fs_hz)

    return {
        "stimulus_label": stimulus_label,
        "n_repeats": brightness.shape[0],
        "n_silence_repeats": silence_brightness.shape[0],
        "n_samples_analyzed": brightness.shape[1],
        "consistency_brightness": c_brightness,
        "consistency_audio_in": c_audio_in,
        "consistency_silence_floor": c_silence_floor,
        "above_noise_floor": c_brightness > c_silence_floor,
        "lyapunov_estimate": lyap,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, help="acquisition out_dir (contains raw/ and index.csv)")
    parser.add_argument("--stimulus", required=True, help="consistency stimulus label, e.g. noise_repeat")
    parser.add_argument("--discard-s", type=float, default=0.0, help="transient to discard, seconds")
    parser.add_argument("--fs-hz", type=int, default=100000)
    parser.add_argument("--out", default="artifacts/consistency/report.json")
    args = parser.parse_args()

    report = build_report(Path(args.out_dir), args.stimulus, args.discard_s, args.fs_hz)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
