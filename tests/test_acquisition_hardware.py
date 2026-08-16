from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest

from plasma_rc.acquisition.audio_device import PlayResult
from plasma_rc.acquisition.config import load_config
from plasma_rc.acquisition.serial_io import (
    FRAME_N_SAMPLES,
    TrialAbort,
    build_frame,
    open_board,
)
from plasma_rc.acquisition.session import parse_audio_path, run_session, run_trial

USE_REAL_HARDWARE = False  # set True when a Teensy is attached; remove this flag later

DEFAULT_YAML = Path(__file__).resolve().parents[1] / "plasma_rc" / "acquisition" / "config.yaml"


class FakeSerial:
    def __init__(
        self,
        fs_hz: int = 100000,
        n_frames: int = 4,
        bad_crc: bool = False,
        gap: bool = False,
    ):
        self._buf = bytearray()
        self._lock = threading.Lock()
        self.writes: list[str] = []
        self.fs_hz = fs_hz
        self.n_frames = n_frames
        self.bad_crc = bad_crc
        self.gap = gap
        self.closed = False

    @property
    def in_waiting(self) -> int:
        with self._lock:
            return len(self._buf)

    def write(self, data: bytes) -> None:
        text = data.decode("ascii")
        self.writes.append(text)
        if text == "PING\n":
            self._push(f"PONG,0.0.1,{self.fs_hz},12,2\n".encode())
        elif text == "START\n":
            self._push(b"SYNC,1000\n")
            self._push_frames()
        elif text == "STOP\n":
            self._push(f"STOPPED,5000,{self.n_frames},0\n".encode())

    def readline(self) -> bytes:
        return self._take_until(b"\n", timeout=2.0)

    def read(self, n: int) -> bytes:
        deadline = time.perf_counter() + 0.05
        while time.perf_counter() < deadline:
            with self._lock:
                if self._buf:
                    take = bytes(self._buf[:n])
                    del self._buf[:n]
                    return take
            time.sleep(0.001)
        return b""

    def close(self) -> None:
        self.closed = True

    def _push(self, data: bytes) -> None:
        with self._lock:
            self._buf.extend(data)

    def _take_until(self, sep: bytes, timeout: float) -> bytes:
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            with self._lock:
                idx = bytes(self._buf).find(sep)
                if idx >= 0:
                    take = bytes(self._buf[: idx + len(sep)])
                    del self._buf[: idx + len(sep)]
                    return take
            time.sleep(0.001)
        return b""

    def _push_frames(self) -> None:
        n = FRAME_N_SAMPLES
        for i in range(self.n_frames):
            seq = i + 1 if (self.gap and i >= 2) else i
            t0 = 1000 + i * n * 10
            bright = np.full(n, 800, dtype=np.uint16)
            audio = np.full(n, 2048, dtype=np.uint16)
            frame = bytearray(build_frame(seq, t0, bright, audio))
            if self.bad_crc and i == 1:
                frame[-1] ^= 0xFF
            self._push(bytes(frame))


def _board(fake: FakeSerial):
    return open_board(None, 100000, 12, ser=fake)


def test_ping_requires_100khz():
    board = _board(FakeSerial())
    assert board.fs_hz == 100000
    assert board.adc_bits == 12
    board.close()


def test_ping_mismatch_aborts():
    with pytest.raises(TrialAbort, match="FS_HZ"):
        open_board(None, 100000, 12, ser=FakeSerial(fs_hz=20000))


def test_sync_offset_finite():
    board = _board(FakeSerial())
    offset = board.sync()
    capture = board.stop()
    assert isinstance(offset, int)
    assert capture.sync_offset_us == offset
    board.close()


def test_stream_length_and_t_us():
    n_frames = 4
    board = _board(FakeSerial(n_frames=n_frames))
    board.sync()
    capture = board.stop()
    assert len(capture.brightness) == n_frames * FRAME_N_SAMPLES
    assert len(capture.audio_in) == len(capture.brightness)
    assert len(capture.t_us) == len(capture.brightness)
    assert capture.t_us[1] - capture.t_us[0] == 10
    board.close()


def test_bad_crc_aborts_trial():
    board = _board(FakeSerial(bad_crc=True))
    board.sync()
    with pytest.raises(TrialAbort, match="CRC"):
        board.stop()
    board.close()


def test_block_seq_gap_aborts_trial():
    board = _board(FakeSerial(gap=True))
    board.sync()
    with pytest.raises(TrialAbort, match="block_seq"):
        board.stop()
    board.close()


def test_trial_loop_writes_npz(tmp_path: Path):
    cfg = load_config(DEFAULT_YAML)
    cfg.pre_roll_s = 0.0
    cfg.post_roll_s = 0.0
    cfg.out_dir = tmp_path / "out"
    cfg.audio_device = 0
    audio_root = tmp_path / "data" / "Data"
    path = audio_root / "same word" / "50" / "sami" / "a1.mp3"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    meta = parse_audio_path(path, audio_root)
    assert meta is not None
    board = _board(FakeSerial(n_frames=2))

    def fake_play(_path, _device):
        return PlayResult(1.0, 1.05, 0.05, 0.05, 0.0)

    run_trial(path, meta, cfg, board, 0, "20260816T000000Z", play_fn=fake_play)
    npz = list((cfg.out_dir / "raw").rglob("*.npz"))
    assert len(npz) == 1
    index = (cfg.out_dir / "index.csv").read_text(encoding="utf-8")
    assert "sami" in index and "a1" in index
    board.close()


def test_play_failure_still_sends_stop(tmp_path: Path):
    cfg = load_config(DEFAULT_YAML)
    cfg.pre_roll_s = 0.0
    cfg.post_roll_s = 0.0
    cfg.out_dir = tmp_path / "out"
    cfg.audio_device = 0
    audio_root = tmp_path / "data" / "Data"
    path = audio_root / "same word" / "50" / "sami" / "a1.mp3"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    meta = parse_audio_path(path, audio_root)
    assert meta is not None
    fake = FakeSerial(n_frames=2)
    board = _board(fake)

    def boom(_path, _device):
        raise RuntimeError("decode failed")

    with pytest.raises(RuntimeError, match="decode failed"):
        run_trial(path, meta, cfg, board, 0, "20260816T000000Z", play_fn=boom)

    assert "START\n" in fake.writes
    assert "STOP\n" in fake.writes
    assert board._reader is not None
    assert not board._reader.is_alive()
    assert list((cfg.out_dir / "raw").rglob("*.npz")) == []
    assert not (cfg.out_dir / "index.csv").exists()
    board.close()


def test_aborted_trial_writes_nothing(tmp_path: Path):
    cfg = load_config(DEFAULT_YAML)
    cfg.pre_roll_s = 0.0
    cfg.post_roll_s = 0.0
    cfg.out_dir = tmp_path / "out"
    cfg.audio_device = 0
    audio_root = tmp_path / "data" / "Data"
    path = audio_root / "different word" / "apple" / "sami" / "a1.mp3"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    cfg.audio_root = audio_root
    board = _board(FakeSerial(bad_crc=True))

    def fake_play(_path, _device):
        return PlayResult(1.0, 1.05, 0.05, 0.05, 0.0)

    run_session(cfg, board=board, play_fn=fake_play)
    assert list((cfg.out_dir / "raw").rglob("*.npz")) == []
    assert not (cfg.out_dir / "index.csv").exists()
    board.close()


@pytest.mark.skipif(not USE_REAL_HARDWARE, reason="no Teensy attached")
def test_real_hardware_ping():
    cfg = load_config(DEFAULT_YAML)
    board = open_board(cfg.port, cfg.fs_hz, cfg.adc_bits)
    try:
        assert board.fs_hz == cfg.fs_hz
        board.sync()
        capture = board.stop()
        assert capture.fs_hz == cfg.fs_hz
    finally:
        board.close()
