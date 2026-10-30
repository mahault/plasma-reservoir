"""UNO frame codec: layout shared with firmware/ne2_uno/ne2_uno.ino."""

import numpy as np
import pytest

from plasma_rc.acquisition.protocol import (
    EVENT,
    HEADER_SIZE,
    SAMPLE,
    crc16_ccitt,
    flash_times_s,
    frame_length,
    pack_frame,
    parse_frame,
    parse_pong,
)


def test_crc16_ccitt_false_check_value():
    # CRC-16/CCITT-FALSE reference check value for "123456789"
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_sample_frame_round_trip():
    values = np.array([0, 1023, 512, 7], dtype=np.uint16)
    buf = pack_frame(SAMPLE, seq=3, tick0=70000, values=values)
    assert buf[:2] == b"\xaa\x55"
    assert len(buf) == HEADER_SIZE + 2 * len(values) + 2 == frame_length(buf)
    fr = parse_frame(buf)
    assert (fr.kind, fr.seq, fr.tick0) == (SAMPLE, 3, 70000)
    np.testing.assert_array_equal(fr.values, values)


def test_event_frame_round_trip():
    triples = np.array([5, 1, 100, 6, 0, 0], dtype=np.uint16)  # (lo, hi, sub) x2
    fr = parse_frame(pack_frame(EVENT, seq=0, tick0=0, values=triples))
    assert fr.kind == EVENT
    np.testing.assert_array_equal(fr.values, triples)


def test_bad_crc_and_bad_magic_rejected():
    buf = bytearray(pack_frame(SAMPLE, 0, 0, np.array([1, 2], dtype=np.uint16)))
    buf[-1] ^= 0xFF
    assert parse_frame(bytes(buf)) is None
    buf2 = bytearray(pack_frame(SAMPLE, 0, 0, np.array([1], dtype=np.uint16)))
    buf2[0] = 0
    assert parse_frame(bytes(buf2)) is None


def test_frame_length_needs_full_header():
    assert frame_length(b"\xaa\x55\x01") is None


def test_flash_times_exact():
    # tick_hz = 16e6 / (OCR1A + 1); sub counts CPU cycles inside the tick
    t = flash_times_s(np.array([0, 1, 2]), np.array([0, 0, 800]), ocr1a=1599)
    np.testing.assert_allclose(t, [0.0, 1600 / 16e6, (3200 + 800) / 16e6])


def test_parse_pong():
    assert parse_pong("PONG,ne2-uno-1,10\n") == ("ne2-uno-1", 10, 16e6)  # UNO: no clock field
    assert parse_pong("PONG,ne2-teensy41-1,12,600000000\n") == ("ne2-teensy41-1", 12, 600e6)
    with pytest.raises(ValueError):
        parse_pong("HELLO")
