"""Teensy USB protocol: CRC, binary frames, handshake, and capture stream."""

from __future__ import annotations

import struct
import threading
import time

import numpy as np

FRAME_N_SAMPLES = 64
HEADER_STRUCT = struct.Struct("<HIIH")  # magic, block_seq, t_start_us, n_samples
MAGIC = 0xAA55
MAGIC_BYTES = b"\x55\xaa"
HANDSHAKE_TIMEOUT_S = 2.0
_SAMPLE_STRUCT = struct.Struct("<HH")


class TrialAbort(Exception):
    pass


class Frame:
    __slots__ = ("block_seq", "t_start_us", "n_samples", "brightness", "audio")

    def __init__(self, block_seq, t_start_us, n_samples, brightness, audio):
        self.block_seq = block_seq
        self.t_start_us = t_start_us
        self.n_samples = n_samples
        self.brightness = brightness
        self.audio = audio


class RawCapture:
    __slots__ = (
        "t_us",
        "audio_in",
        "brightness",
        "dropped",
        "frames_sent",
        "sync_offset_us",
        "fs_hz",
    )

    def __init__(self, t_us, audio_in, brightness, dropped, frames_sent, sync_offset_us, fs_hz):
        self.t_us = t_us
        self.audio_in = audio_in
        self.brightness = brightness
        self.dropped = dropped
        self.frames_sent = frames_sent
        self.sync_offset_us = sync_offset_us
        self.fs_hz = fs_hz


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, xorout 0x0000, not reflected."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def build_frame(
    block_seq: int,
    t_start_us: int,
    brightness: np.ndarray,
    audio: np.ndarray,
) -> bytes:
    n_samples = int(len(brightness))
    header = HEADER_STRUCT.pack(MAGIC, block_seq, t_start_us, n_samples)
    samples = b"".join(
        _SAMPLE_STRUCT.pack(int(b), int(a)) for b, a in zip(brightness, audio)
    )
    body = header + samples
    return body + struct.pack("<H", crc16_ccitt(body))


def parse_frame(buf: bytes) -> Frame | None:
    if len(buf) < HEADER_STRUCT.size + 2:
        return None
    magic, block_seq, t_start_us, n_samples = HEADER_STRUCT.unpack_from(buf, 0)
    if magic != MAGIC:
        return None
    expected = HEADER_STRUCT.size + 4 * n_samples + 2
    if len(buf) != expected:
        return None
    body = buf[:-2]
    crc_recv = struct.unpack_from("<H", buf, len(buf) - 2)[0]
    if crc16_ccitt(body) != crc_recv:
        return None
    brightness = np.empty(n_samples, dtype=np.uint16)
    audio = np.empty(n_samples, dtype=np.uint16)
    offset = HEADER_STRUCT.size
    for i in range(n_samples):
        brightness[i], audio[i] = _SAMPLE_STRUCT.unpack_from(buf, offset)
        offset += 4
    return Frame(block_seq, t_start_us, n_samples, brightness, audio)


def _parse_pong(line: str) -> tuple[str, int, int]:
    line = line.strip()
    parts = line.split(",")
    if len(parts) != 5 or parts[0] != "PONG":
        raise TrialAbort(f"bad PONG: {line!r}")
    fw = parts[1]
    fs_hz = int(parts[2])
    adc_bits = int(parts[3])
    channels = int(parts[4].split("=", 1)[-1])
    if channels != 2:
        raise TrialAbort(f"expected 2 channels, got {channels}")
    return fw, fs_hz, adc_bits


class Board:
    def __init__(self, ser, fs_hz: int, adc_bits: int, fw_version: str):
        self._ser = ser
        self.fs_hz = fs_hz
        self.adc_bits = adc_bits
        self.fw_version = fw_version
        self._sync_offset_us = 0
        self._frames: list[Frame] = []
        self._abort: str | None = None
        self._stopped: tuple[int, int, int] | None = None
        self._reader: threading.Thread | None = None
        self._stop_event = threading.Event()

    def sync(self) -> int:
        self._frames.clear()
        self._abort = None
        self._stopped = None
        self._stop_event.clear()
        self._ser.write(b"START\n")
        line = self._ser.readline().decode("ascii", errors="replace").strip()
        if not line.startswith("SYNC,"):
            raise TrialAbort(f"expected SYNC, got {line!r}")
        board_us = int(line.split(",", 1)[1])
        self._sync_offset_us = int(round(time.perf_counter() * 1e6 - board_us))
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        return self._sync_offset_us

    def stop(self) -> RawCapture:
        self._ser.write(b"STOP\n")
        self._stop_event.set()
        if self._reader is not None:
            self._reader.join(timeout=HANDSHAKE_TIMEOUT_S + 1.0)
        if self._abort:
            raise TrialAbort(self._abort)
        if self._stopped is None:
            raise TrialAbort("missing STOPPED")
        _, frames_sent, dropped = self._stopped
        return self._assemble(dropped, frames_sent)

    def close(self) -> None:
        close = getattr(self._ser, "close", None)
        if close is not None:
            close()

    def _read_loop(self) -> None:
        try:
            self._drain()
        except TrialAbort as exc:
            self._abort = str(exc)
        except Exception as exc:  # noqa: BLE001
            self._abort = f"reader error: {exc}"

    def _drain(self) -> None:
        buf = bytearray()
        deadline = None
        while self._stopped is None:
            waiting = getattr(self._ser, "in_waiting", 0) or 270
            chunk = self._ser.read(waiting)
            if chunk:
                buf.extend(chunk)
                buf = bytearray(self._consume(bytes(buf)))
            if self._stop_event.is_set():
                if deadline is None:
                    deadline = time.perf_counter() + HANDSHAKE_TIMEOUT_S
                if self._stopped is not None:
                    return
                if time.perf_counter() > deadline:
                    raise TrialAbort("missing STOPPED")
            if not chunk:
                time.sleep(0.001)

    def _consume(self, data: bytes) -> bytes:
        pos = 0
        n = len(data)
        while pos < n:
            stopped_at = data.find(b"STOPPED,", pos)
            magic_at = data.find(MAGIC_BYTES, pos)
            if stopped_at >= 0 and (magic_at < 0 or stopped_at <= magic_at):
                nl = data.find(b"\n", stopped_at)
                if nl < 0:
                    return data[stopped_at:]
                line = data[stopped_at:nl].decode("ascii", errors="replace")
                parts = line.split(",")
                if len(parts) != 4:
                    raise TrialAbort(f"bad STOPPED: {line!r}")
                self._stopped = (int(parts[1]), int(parts[2]), int(parts[3]))
                return data[nl + 1 :]
            if magic_at < 0:
                return data[max(pos, n - 8) :]
            pos = magic_at
            if n - pos < HEADER_STRUCT.size:
                return data[pos:]
            n_samples = HEADER_STRUCT.unpack_from(data, pos)[3]
            frame_len = HEADER_STRUCT.size + 4 * n_samples + 2
            if n - pos < frame_len:
                return data[pos:]
            frame = parse_frame(data[pos : pos + frame_len])
            if frame is None:
                raise TrialAbort("bad CRC")
            if self._frames and frame.block_seq != self._frames[-1].block_seq + 1:
                raise TrialAbort(
                    f"block_seq gap: expected {self._frames[-1].block_seq + 1}, got {frame.block_seq}"
                )
            self._frames.append(frame)
            pos += frame_len
        return b""

    def _assemble(self, dropped: int, frames_sent: int) -> RawCapture:
        if not self._frames:
            empty_t = np.array([], dtype=np.int64)
            empty_u = np.array([], dtype=np.uint16)
            return RawCapture(
                empty_t, empty_u, empty_u, dropped, frames_sent, self._sync_offset_us, self.fs_hz
            )
        t_parts = []
        b_parts = []
        a_parts = []
        period = 1e6 / self.fs_hz
        for fr in self._frames:
            idx = np.arange(fr.n_samples, dtype=np.int64)
            t_parts.append(fr.t_start_us + np.rint(idx * period).astype(np.int64))
            b_parts.append(fr.brightness)
            a_parts.append(fr.audio)
        return RawCapture(
            t_us=np.concatenate(t_parts),
            audio_in=np.concatenate(a_parts),
            brightness=np.concatenate(b_parts),
            dropped=dropped,
            frames_sent=frames_sent,
            sync_offset_us=self._sync_offset_us,
            fs_hz=self.fs_hz,
        )


def open_board(port: str | None, expected_fs: int, expected_adc_bits: int, ser=None) -> Board:
    if ser is None:
        serial = _import_serial()
        if port is None:
            ser = _autodetect(serial, expected_fs, expected_adc_bits)
            fw, fs_hz, adc_bits = _last_pong
            return Board(ser, fs_hz, adc_bits, fw)
        ser = serial.Serial(port, timeout=HANDSHAKE_TIMEOUT_S)
        try:
            fw, fs_hz, adc_bits = _handshake(ser, expected_fs, expected_adc_bits)
        except Exception:
            ser.close()
            raise
        return Board(ser, fs_hz, adc_bits, fw)
    fw, fs_hz, adc_bits = _handshake(ser, expected_fs, expected_adc_bits)
    return Board(ser, fs_hz, adc_bits, fw)


_last_pong: tuple[str, int, int] = ("", 0, 0)


def _import_serial():
    try:
        import serial
        import serial.tools.list_ports  # noqa: F401
    except ImportError as exc:
        raise TrialAbort("pyserial is required: pip install -e '.[acquisition]'") from exc
    return serial


def _do_ping(ser) -> str:
    ser.write(b"PING\n")
    raw = ser.readline()
    if not raw:
        raise TrialAbort("PING timed out")
    return raw.decode("ascii", errors="replace")


def _handshake(ser, expected_fs: int, expected_adc_bits: int) -> tuple[str, int, int]:
    fw, fs_hz, adc_bits = _parse_pong(_do_ping(ser))
    if fs_hz != expected_fs or adc_bits != expected_adc_bits:
        raise TrialAbort(
            f"board FS_HZ={fs_hz} adc_bits={adc_bits} != expected {expected_fs}/{expected_adc_bits}"
        )
    return fw, fs_hz, adc_bits


def _autodetect(serial, expected_fs: int, expected_adc_bits: int):
    global _last_pong
    last_err: Exception | None = None
    for info in serial.tools.list_ports.comports():
        try:
            ser = serial.Serial(info.device, timeout=HANDSHAKE_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
        try:
            _last_pong = _handshake(ser, expected_fs, expected_adc_bits)
            return ser
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            ser.close()
    raise TrialAbort(f"no Teensy answered PING ({last_err})")
