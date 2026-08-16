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
from .serial_io import Board, RawCapture, TrialAbort, open_board

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


@dataclass
class TrialMeta:
    speaker: str
    condition: str
    label: str
    sample_index: int
    source_file: str
    stem: str


def parse_audio_path(path: Path, audio_root: Path) -> TrialMeta | None:
    try:
        rel = path.resolve().relative_to(audio_root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) != 4:
        return None
    top, mid, speaker_dir, name = parts
    match = _NAME_RE.match(name)
    if match is None:
        return None
    sample_index = int(match.group(1))
    speaker = speaker_dir.lower()
    if top == "same word":
        if mid not in _VOLUME:
            return None
        condition, label = "same_word", mid
    elif top == "different word":
        word = mid.lower()
        if word not in _WORDS:
            return None
        condition, label = "different_word", word
    else:
        return None
    return TrialMeta(
        speaker=speaker,
        condition=condition,
        label=label,
        sample_index=sample_index,
        source_file=str(path),
        stem=path.stem,
    )


def list_trials(audio_root: Path) -> list[tuple[Path, TrialMeta]]:
    trials = []
    for path in sorted(audio_root.rglob("*.mp3")):
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
    time.sleep(cfg.pre_roll_s)
    result: PlayResult = play_fn(path, device)
    time.sleep(cfg.post_roll_s)
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


def run_session(cfg: Config, board: Board | None = None, play_fn=play) -> None:
    device = select_device(cfg)
    session_id = utc_session_id()
    close_board = False
    if board is None:
        board = open_board(cfg.port, cfg.fs_hz, cfg.adc_bits)
        close_board = True
    try:
        for path, meta in list_trials(cfg.audio_root):
            try:
                run_trial(path, meta, cfg, board, device, session_id, play_fn=play_fn)
            except TrialAbort as exc:
                print(f"abort {path}: {exc}")
    finally:
        if close_board:
            board.close()
