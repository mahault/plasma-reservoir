"""Run a capture session: parse the audio tree, stream the Teensy, write npz + index."""

from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .audio_device import PlayResult, play, select_device
from .config import Config
from .serial_io import Board, RawCapture, open_board

INDEX_FIELDS = (
    "session_id",
    "speaker",
    "condition",
    "label",
    "source_file",
    "sample_index",
    "raw_file",
    "sync_offset_us",
    "fs_hz",
    "adc_bits",
    "t_play_start_pc",
    "t_play_end_pc",
    "true_duration_s",
    "measured_wall_s",
    "process_overhead_s",
    "n_samples",
    "dropped",
)

_NAME_RE = re.compile(r"^[abo]?(\d+)\.mp3$", re.IGNORECASE)
_VOLUME = {"50", "75", "100"}
_WORDS = {"apple", "banana", "orange"}
_SILENCE_RE = re.compile(r"^s(\d+)\.wav$", re.IGNORECASE)
_NOISE_RE = re.compile(r"^n(\d+)\.wav$", re.IGNORECASE)
_FSDD_RE = re.compile(r"^([0-9])_([A-Za-z]+)_(\d+)\.wav$")


@dataclass
class TrialMeta:
    speaker: str
    condition: str
    label: str
    sample_index: int
    source_file: str
    stem: str


def _parse_same_word(parts: tuple[str, ...]) -> tuple[str, str, str, int] | None:
    if len(parts) != 4:
        return None
    _, volume, speaker_dir, name = parts
    match = _NAME_RE.match(name)
    if match is None or volume not in _VOLUME:
        return None
    return speaker_dir.lower(), "same_word", volume, int(match.group(1))


def _parse_different_word(parts: tuple[str, ...]) -> tuple[str, str, str, int] | None:
    if len(parts) != 4:
        return None
    _, word, speaker_dir, name = parts
    match = _NAME_RE.match(name)
    word = word.lower()
    if match is None or word not in _WORDS:
        return None
    return speaker_dir.lower(), "different_word", word, int(match.group(1))


def _parse_silence(parts: tuple[str, ...]) -> tuple[str, str, str, int] | None:
    if len(parts) != 2:
        return None
    _, name = parts
    match = _SILENCE_RE.match(name)
    if match is None:
        return None
    return "na", "silence", "silence", int(match.group(1))


def _parse_noise(parts: tuple[str, ...]) -> tuple[str, str, str, int] | None:
    if len(parts) != 2:
        return None
    _, name = parts
    match = _NOISE_RE.match(name)
    if match is None:
        return None
    return "na", "noise", "white_noise", int(match.group(1))


def _parse_fsdd(parts: tuple[str, ...]) -> tuple[str, str, str, int] | None:
    if len(parts) != 2:
        return None
    _, name = parts
    match = _FSDD_RE.match(name)
    if match is None:
        return None
    digit, speaker, index = match.groups()
    return speaker.lower(), "fsdd", digit, int(index)


_DATASET_PARSERS = {
    "same word": _parse_same_word,
    "different word": _parse_different_word,
    "silence": _parse_silence,
    "noise": _parse_noise,
    "fsdd": _parse_fsdd,
}


def parse_audio_path(path: Path, audio_root: Path) -> TrialMeta | None:
    try:
        rel = path.resolve().relative_to(audio_root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if not parts:
        return None
    parser = _DATASET_PARSERS.get(parts[0])
    if parser is None:
        return None
    parsed = parser(parts)
    if parsed is None:
        return None
    speaker, condition, label, sample_index = parsed
    return TrialMeta(
        speaker=speaker,
        condition=condition,
        label=label,
        sample_index=sample_index,
        source_file=str(path),
        stem=path.stem,
    )


_AUDIO_EXTENSIONS = ("*.mp3", "*.wav")


def list_trials(audio_root: Path) -> list[tuple[Path, TrialMeta]]:
    trials = []
    paths = sorted(p for ext in _AUDIO_EXTENSIONS for p in audio_root.rglob(ext))
    for path in paths:
        meta = parse_audio_path(path, audio_root)
        if meta is None:
            print(f"skip {path}")
            continue
        trials.append((path, meta))
    return trials


def raw_path(out_dir: Path, meta: TrialMeta) -> Path:
    return out_dir / "raw" / meta.speaker / meta.condition / meta.label / f"{meta.stem}.npz"


def write_npz(path: Path, capture: RawCapture) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        t_us=capture.t_us,
        audio_in=capture.audio_in,
        brightness=capture.brightness,
        fs_hz=np.int32(capture.fs_hz),
    )


def append_index_row(index_path: Path, row: dict) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not index_path.exists()
    with index_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=INDEX_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({k: row[k] for k in INDEX_FIELDS})


def utc_session_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def run_trial(
    path: Path,
    meta: TrialMeta,
    cfg: Config,
    board: Board,
    device: int,
    session_id: str,
    play_fn=play,
) -> None:
    offset_us = board.sync()
    try:
        time.sleep(cfg.pre_roll_s)
        result: PlayResult = play_fn(path, device)
        time.sleep(cfg.post_roll_s)
    finally:
        capture = board.stop()
    duration_s = cfg.pre_roll_s + result.true_duration_s + cfg.post_roll_s
    expected = cfg.fs_hz * duration_s
    if expected and abs(len(capture.brightness) - expected) / expected > 0.01:
        print(
            f"{path}: sample count {len(capture.brightness)} vs FS_HZ*duration {expected:.1f}"
        )
    out = raw_path(cfg.out_dir, meta)
    write_npz(out, capture)
    append_index_row(
        cfg.out_dir / "index.csv",
        {
            "session_id": session_id,
            "speaker": meta.speaker,
            "condition": meta.condition,
            "label": meta.label,
            "source_file": meta.source_file,
            "sample_index": meta.sample_index,
            "raw_file": str(out),
            "sync_offset_us": offset_us,
            "fs_hz": capture.fs_hz,
            "adc_bits": cfg.adc_bits,
            "t_play_start_pc": result.t_play_start_pc,
            "t_play_end_pc": result.t_play_end_pc,
            "true_duration_s": result.true_duration_s,
            "measured_wall_s": result.measured_wall_s,
            "process_overhead_s": result.process_overhead_s,
            "n_samples": len(capture.brightness),
            "dropped": capture.dropped,
        },
    )


@dataclass
class SessionSummary:
    attempted: int
    succeeded: int
    aborted: int
    aborted_paths: list[Path]


def run_session(cfg: Config, board: Board | None = None, play_fn=play) -> SessionSummary:
    device = select_device(cfg)
    session_id = utc_session_id()
    close_board = False
    if board is None:
        board = open_board(cfg.port, cfg.fs_hz, cfg.adc_bits)
        close_board = True
    attempted = 0
    aborted_paths: list[Path] = []
    try:
        for path, meta in list_trials(cfg.audio_root):
            attempted += 1
            try:
                run_trial(path, meta, cfg, board, device, session_id, play_fn=play_fn)
            except Exception as exc:
                print(f"abort {path}: {exc}")
                aborted_paths.append(path)
    finally:
        if close_board:
            board.close()
    succeeded = attempted - len(aborted_paths)
    print(f"session {session_id}: {succeeded}/{attempted} succeeded, aborted={len(aborted_paths)}")
    return SessionSummary(
        attempted=attempted,
        succeeded=succeeded,
        aborted=len(aborted_paths),
        aborted_paths=aborted_paths,
    )
