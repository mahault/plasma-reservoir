"""Parse the recorded-audio tree (data/Data): words, FSDD, silence, noise, consistency repeats."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_NAME_RE = re.compile(r"^[abo]?(\d+)\.mp3$", re.IGNORECASE)
_VOLUME = {"50", "75", "100"}
_WORDS = {"apple", "banana", "orange"}
_SILENCE_RE = re.compile(r"^s(\d+)\.wav$", re.IGNORECASE)
_NOISE_RE = re.compile(r"^n(\d+)\.wav$", re.IGNORECASE)
_FSDD_RE = re.compile(r"^([0-9])_([A-Za-z]+)_(\d+)\.wav$")
_CONSISTENCY_RE = re.compile(r"^r(\d+)\.wav$", re.IGNORECASE)


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


def _parse_consistency(parts: tuple[str, ...]) -> tuple[str, str, str, int] | None:
    if len(parts) != 3:
        return None
    _, stimulus_name, name = parts
    match = _CONSISTENCY_RE.match(name)
    if match is None:
        return None
    return "na", "consistency", stimulus_name, int(match.group(1))


_DATASET_PARSERS = {
    "same word": _parse_same_word,
    "different word": _parse_different_word,
    "silence": _parse_silence,
    "noise": _parse_noise,
    "fsdd": _parse_fsdd,
    "consistency": _parse_consistency,
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


def list_trials(audio_root: Path, datasets: tuple[str, ...] | None = None) -> list[tuple[Path, TrialMeta]]:
    """Every parsable audio file under audio_root, optionally only the given top-level datasets."""
    trials = []
    paths = sorted(p for ext in _AUDIO_EXTENSIONS for p in audio_root.rglob(ext))
    for path in paths:
        meta = parse_audio_path(path, audio_root)
        if meta is None:
            print(f"skip {path}")
            continue
        if datasets is None or path.relative_to(audio_root).parts[0] in datasets:
            trials.append((path, meta))
    return trials
