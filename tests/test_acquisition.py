from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

yaml = pytest.importorskip("yaml")

from plasma_rc.acquisition.audio_device import decode
from plasma_rc.acquisition.cli import main
from plasma_rc.acquisition.config import ConfigError, load_config, persist_audio_device
from plasma_rc.acquisition.serial_io import FRAME_N_SAMPLES, build_frame, crc16_ccitt, parse_frame
from plasma_rc.acquisition.session import (
    append_index_row,
    parse_audio_path,
    raw_path,
    write_npz,
)
from plasma_rc.acquisition.serial_io import RawCapture


DEFAULT_YAML = Path(__file__).resolve().parents[1] / "plasma_rc" / "acquisition" / "config.yaml"


def test_load_default_config():
    cfg = load_config(DEFAULT_YAML)
    assert cfg.fs_hz == 100000
    assert cfg.adc_bits == 12
    assert cfg.port is None
    assert cfg.audio_device is None
    assert cfg.pre_roll_s == 1.0
    assert cfg.post_roll_s == 1.0
    assert cfg.audio_root == (Path.cwd() / "data" / "Data").resolve()
    assert cfg.out_dir == (Path.cwd() / "data" / "out").resolve()


def test_reject_bad_adc_bits(tmp_path: Path):
    src = DEFAULT_YAML.read_text(encoding="utf-8").replace("adc_bits: 12", "adc_bits: 10")
    path = tmp_path / "config.yaml"
    path.write_text(src, encoding="utf-8")
    with pytest.raises(ConfigError, match="adc_bits"):
        load_config(path)


def test_reject_missing_key(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("board: teensy41\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="missing keys"):
        load_config(path)


def test_persist_audio_device(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(DEFAULT_YAML.read_text(encoding="utf-8"), encoding="utf-8")
    cfg = load_config(path)
    persist_audio_device(cfg, 3)
    assert cfg.audio_device == 3
    reloaded = load_config(path)
    assert reloaded.audio_device == 3


def test_crc16_ccitt_known_vector():
    assert crc16_ccitt(b"123456789") == 0x29B1


def _sample_frame(seq: int = 0, flip: bool = False) -> bytes:
    n = FRAME_N_SAMPLES
    bright = np.arange(n, dtype=np.uint16)
    audio = np.full(n, 2048, dtype=np.uint16)
    buf = bytearray(build_frame(seq, 1000, bright, audio))
    if flip:
        buf[-1] ^= 0xFF
    return bytes(buf)


def test_parse_frame_valid():
    frame = parse_frame(_sample_frame())
    assert frame is not None
    assert frame.block_seq == 0
    assert frame.n_samples == FRAME_N_SAMPLES
    assert frame.brightness[1] == 1
    assert frame.audio[0] == 2048


def test_parse_frame_bad_crc():
    assert parse_frame(_sample_frame(flip=True)) is None


def test_parse_same_word_path(tmp_path: Path):
    audio_root = tmp_path / "data" / "Data"
    path = audio_root / "same word" / "75" / "Majesty" / "a12.mp3"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    meta = parse_audio_path(path, audio_root)
    assert meta is not None
    assert meta.speaker == "majesty"
    assert meta.condition == "same_word"
    assert meta.label == "75"
    assert meta.sample_index == 12


def test_parse_different_word_path(tmp_path: Path):
    audio_root = tmp_path / "data" / "Data"
    path = audio_root / "different word" / "banana" / "Sami" / "b3.mp3"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    meta = parse_audio_path(path, audio_root)
    assert meta is not None
    assert meta.speaker == "sami"
    assert meta.condition == "different_word"
    assert meta.label == "banana"
    assert meta.sample_index == 3


def test_skip_bad_filename(tmp_path: Path):
    audio_root = tmp_path / "data" / "Data"
    path = audio_root / "same word" / "50" / "sami" / "notes.txt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    assert parse_audio_path(path, audio_root) is None


def test_write_npz_and_index(tmp_path: Path):
    audio_root = tmp_path / "data" / "Data"
    path = audio_root / "same word" / "100" / "sami" / "a1.mp3"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    meta = parse_audio_path(path, audio_root)
    assert meta is not None
    capture = RawCapture(
        t_us=np.array([0, 10], dtype=np.int64),
        audio_in=np.array([2048, 2049], dtype=np.uint16),
        brightness=np.array([800, 810], dtype=np.uint16),
        dropped=0,
        frames_sent=1,
        sync_offset_us=5,
        fs_hz=100000,
    )
    out = raw_path(tmp_path / "out", meta)
    write_npz(out, capture)
    loaded = np.load(out)
    np.testing.assert_array_equal(loaded["t_us"], capture.t_us)
    np.testing.assert_array_equal(loaded["audio_in"], capture.audio_in)
    np.testing.assert_array_equal(loaded["brightness"], capture.brightness)
    assert int(loaded["fs_hz"]) == 100000
    index = tmp_path / "out" / "index.csv"
    append_index_row(
        index,
        {
            "session_id": "20260816T000000Z",
            "speaker": meta.speaker,
            "condition": meta.condition,
            "label": meta.label,
            "source_file": meta.source_file,
            "sample_index": meta.sample_index,
            "raw_file": str(out),
            "sync_offset_us": 5,
            "fs_hz": 100000,
            "adc_bits": 12,
            "t_play_start_pc": 1.0,
            "t_play_end_pc": 1.1,
            "true_duration_s": 0.1,
            "measured_wall_s": 0.1,
            "process_overhead_s": 0.0,
            "n_samples": 2,
            "dropped": 0,
        },
    )
    text = index.read_text(encoding="utf-8")
    assert "sami" in text and "same_word" in text and "100" in text


def test_decode_wav_if_soundfile(tmp_path: Path):
    pytest.importorskip("soundfile")
    import soundfile as sf

    path = tmp_path / "tone.wav"
    sr = 8000
    samples = np.zeros(sr // 10, dtype=np.float32)
    sf.write(path, samples, sr)
    data, out_sr = decode(path)
    assert out_sr == sr
    assert data.shape[0] == samples.shape[0]


def test_cli_ping(monkeypatch, capsys):
    class _Board:
        fw_version = "0.0.1"
        fs_hz = 100000
        adc_bits = 12

        def close(self):
            return None

    monkeypatch.setattr("plasma_rc.acquisition.cli.open_board", lambda *a, **k: _Board())
    assert main(["ping"]) == 0
    assert "FS_HZ=100000" in capsys.readouterr().out


def test_cli_run(monkeypatch):
    called = {}

    def fake_run(cfg):
        called["ok"] = True
        assert cfg.fs_hz == 100000

    monkeypatch.setattr("plasma_rc.acquisition.cli.run_session", fake_run)
    assert main(["run"]) == 0
    assert called["ok"]
