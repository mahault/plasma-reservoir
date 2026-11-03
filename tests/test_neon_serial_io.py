"""Board I/O against a fake serial port that replays UNO frames."""

import numpy as np
import pytest

from plasma_rc.neon.protocol import EVENT, SAMPLE, pack_frame
from plasma_rc.neon.serial_io import Board, TrialAbort


class FakeSerial:
    def __init__(self, lines, stream):
        self.lines = list(lines)
        self.stream = bytearray(stream)
        self.written = []

    def write(self, data):
        self.written.append(data.decode())

    def readline(self):
        return self.lines.pop(0).encode() if self.lines else b""

    def read(self, n):
        chunk, self.stream = bytes(self.stream[:n]), self.stream[n:]
        return chunk

    @property
    def in_waiting(self):
        return len(self.stream)

    def close(self):
        pass


def _stream(frames, stopped="STOPPED,0,0\n"):
    return b"".join(frames) + stopped.encode()


def test_capture_demuxes_channels_and_flashes():
    samples = np.arange(8, dtype=np.uint16)  # ticks 0..7 over channels "0123"
    events = np.array([5, 0, 100], dtype=np.uint16)  # flash at tick 5, sub 100
    ser = FakeSerial(
        ["OK\n", "SYNC,1000\n"],
        _stream([pack_frame(SAMPLE, 0, 0, samples), pack_frame(EVENT, 1, 0, events)]),
    )
    board = Board(ser)
    board.configure(ocr1a=1999, channels="0123")
    board.start("NONE")
    cap = board.stop()
    assert ser.written[:2] == ["CONF,1999,0123\n", "START,NONE\n"]
    ticks, values = cap.channel("2")
    np.testing.assert_array_equal(ticks, [2, 6])
    np.testing.assert_array_equal(values, [2, 6])
    np.testing.assert_allclose(cap.flash_times_s(), [(5 * 2000 + 100) / 16e6])
    assert cap.tick_hz == 16e6 / 2000


def test_seq_gap_aborts():
    s = np.zeros(4, dtype=np.uint16)
    ser = FakeSerial(
        ["OK\n", "SYNC,0\n"],
        _stream([pack_frame(SAMPLE, 0, 0, s), pack_frame(SAMPLE, 2, 4, s)]),
    )
    board = Board(ser)
    board.configure(1999, "0123")
    board.start("NONE")
    with pytest.raises(TrialAbort, match="seq gap"):
        board.stop()


def test_bad_crc_aborts():
    bad = bytearray(pack_frame(SAMPLE, 0, 0, np.zeros(4, dtype=np.uint16)))
    bad[-1] ^= 0xFF
    ser = FakeSerial(["OK\n", "SYNC,0\n"], _stream([bytes(bad)]))
    board = Board(ser)
    board.configure(1999, "0123")
    board.start("NONE")
    with pytest.raises(TrialAbort, match="bad CRC"):
        board.stop()


def test_configure_rejects_board_error():
    board = Board(FakeSerial(["ERR,ocr1a too small\n"], b""))
    with pytest.raises(TrialAbort, match="ocr1a too small"):
        board.configure(10, "0123")


@pytest.mark.parametrize("seq,tick0", [(1, 33), (0, 33)])
def test_initial_loss_aborts_before_demultiplexing(seq, tick0):
    ser = FakeSerial(
        ["OK\n", "SYNC,0\n"],
        _stream([pack_frame(SAMPLE, seq, tick0, np.arange(32, dtype=np.uint16))]),
    )
    board = Board(ser)
    board.configure(1999, "123")
    board.start()
    with pytest.raises(TrialAbort, match="initial|first"):
        board.stop()
