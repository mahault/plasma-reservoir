"""Load and validate acquisition capture config."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    board: str
    port: str | None
    fs_hz: int
    adc_bits: int
    pre_roll_s: float
    post_roll_s: float
    audio_device: int | None
    audio_root: Path
    out_dir: Path
    path: Path


_REQUIRED = (
    "board",
    "port",
    "fs_hz",
    "adc_bits",
    "pre_roll_s",
    "post_roll_s",
    "audio_device",
    "audio_root",
    "out_dir",
)


def load_config(path: str | Path | None = None) -> Config:
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError("config must be a mapping")
    missing = [key for key in _REQUIRED if key not in raw]
    if missing:
        raise ConfigError(f"missing keys: {', '.join(missing)}")
    return _validate(raw, cfg_path)


def persist_audio_device(cfg: Config, index: int) -> None:
    """Rewrite audio_device in the yaml file that was loaded."""
    text = cfg.path.read_text(encoding="utf-8")
    lines = []
    found = False
    for line in text.splitlines(keepends=True):
        if line.startswith("audio_device:"):
            nl = "\n" if line.endswith("\n") else ""
            lines.append(f"audio_device: {index}{nl}")
            found = True
        else:
            lines.append(line)
    if not found:
        raise ConfigError("audio_device key not found in config file")
    cfg.path.write_text("".join(lines), encoding="utf-8")
    cfg.audio_device = index


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ConfigError("port must be a string or null")


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError("audio_device must be an int or null")
    return value


def _as_positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{name} must be a positive int")
    return value


def _as_non_negative_float(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ConfigError(f"{name} must be >= 0")
    return float(value)


def _validate(raw: dict, cfg_path: Path) -> Config:
    adc_bits = _as_positive_int("adc_bits", raw["adc_bits"])
    if adc_bits != 12:
        raise ConfigError("adc_bits must be 12")
    cwd = Path.cwd()
    return Config(
        board=str(raw["board"]),
        port=_as_optional_str(raw["port"]),
        fs_hz=_as_positive_int("fs_hz", raw["fs_hz"]),
        adc_bits=adc_bits,
        pre_roll_s=_as_non_negative_float("pre_roll_s", raw["pre_roll_s"]),
        post_roll_s=_as_non_negative_float("post_roll_s", raw["post_roll_s"]),
        audio_device=_as_optional_int(raw["audio_device"]),
        audio_root=(cwd / str(raw["audio_root"])).resolve(),
        out_dir=(cwd / str(raw["out_dir"])).resolve(),
        path=cfg_path.resolve(),
    )
