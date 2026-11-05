"""Teensy 4.1 <-> host frame codec. Layout must match firmware/ne2h/ne2h.ino.

Frame (little-endian): AA 55 | kind u8 | seq u16 | tick0 u32 | n u8 | n x u16 | crc u16.
The CRC covers kind..values. SAMPLE values are ADC readings in tick order (channel =
channel order[(tick0 + i) % n_channels]); EVENT values are (tick_lo, tick_hi, sub) triples,
one per comparator edge (flash), sub = CPU cycles into the tick.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np

SAMPLE = 1
EVENT = 2
MAGIC = b"\xaa\x55"
_HEAD = struct.Struct("<BHIB")  # kind, seq, tick0, n
HEADER_SIZE = len(MAGIC) + _HEAD.size


@dataclass(slots=True)
class Frame:
    kind: int
    seq: int
    tick0: int
    values: np.ndarray


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, not reflected."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def pack_frame(kind: int, seq: int, tick0: int, values: np.ndarray) -> bytes:
    body = _HEAD.pack(kind, seq & 0xFFFF, tick0 & 0xFFFFFFFF, len(values))
    body += np.asarray(values, dtype="<u2").tobytes()
    return MAGIC + body + struct.pack("<H", crc16_ccitt(body))


def frame_length(buf: bytes, pos: int = 0) -> int | None:
    """Total length of the frame starting at pos, or None if the header is incomplete."""
    if len(buf) - pos < HEADER_SIZE:
        return None
    n = buf[pos + HEADER_SIZE - 1]
    return HEADER_SIZE + 2 * n + 2


def parse_frame(buf: bytes) -> Frame | None:
    """Decode one complete frame; None on bad magic, length or CRC."""
    if buf[:2] != MAGIC or frame_length(buf) != len(buf):
        return None
    body = bytes(buf[2:-2])
    if crc16_ccitt(body) != struct.unpack_from("<H", buf, len(buf) - 2)[0]:
        return None
    kind, seq, tick0, n = _HEAD.unpack_from(body)
    values = np.frombuffer(body, dtype="<u2", count=n, offset=_HEAD.size).astype(np.uint16)
    return Frame(kind, seq, tick0, values)


def parse_pong(line: str) -> tuple[str, int, float]:
    """PONG,<fw>,<adc_bits>,<clock_hz>: firmware id, ADC bits and the CPU cycle-counter clock."""
    parts = line.strip().split(",")
    if len(parts) != 4 or parts[0] != "PONG":
        raise ValueError(f"bad PONG: {line!r}")
    return parts[1], int(parts[2]), float(parts[3])
