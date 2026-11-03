"""Arduino UNO link: CONF / START / STOP commands and a background frame reader.

Commands (host -> UNO, one line each):
  PING                       -> PONG,<fw>,<adc_bits>[,<clock_hz>]   (UNO 10 bit, 16 MHz; Teensy 4.1 12 bit, 600 MHz)
  CONF,<ocr1a>,<channels>    -> OK | ERR,<reason>      (tick_hz = clock_hz / (ocr1a + 1))
  START,<stim>               -> SYNC,<micros>, then binary frames
  STOP                       -> ... STOPPED,<dropped_samples>,<dropped_events>
<stim> is NONE, STEPS,<seed_p>,<n_p>,<seed_c>,<n_c>,<ticks_per_step> or SINE,<phase_inc>,<amp>
(32-bit DDS increment per tick = f * 2**32 / tick_hz; amp 1..127 PWM levels).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np

from .protocol import (
    CPU_HZ,
    EVENT,
    MAGIC,
    SAMPLE,
    flash_times_s,
    frame_length,
    parse_frame,
    parse_pong,
)

BAUD = 1_000_000
TIMEOUT_S = 2.0
RESET_WAIT_S = (
    2.0  # opening the port resets the UNO; its bootloader runs first (Inferred)
)


class TrialAbort(RuntimeError):
    pass


from plasma_rc.neon.records import Capture


class Board:
    def __init__(
        self, ser, clock_hz: float = CPU_HZ, adc_bits=None, board="unknown", v_ref=None
    ):
        self._ser = ser
        self.clock_hz = clock_hz
        self.adc_bits, self.board, self.v_ref = adc_bits, board, v_ref
        self._ocr1a: int | None = None
        self._channels = ""
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()

    def _command(self, line: str, expect: str) -> str:
        self._ser.write(f"{line}\n".encode())
        reply = self._ser.readline().decode("ascii", errors="replace").strip()
        if not reply.startswith(expect):
            raise TrialAbort(f"{line}: {reply or 'no reply'}")
        return reply

    def configure(self, ocr1a: int, channels: str) -> None:
        self._command(f"CONF,{ocr1a},{channels}", "OK")
        self._ocr1a, self._channels = ocr1a, channels

    def start(self, stim: str = "NONE") -> None:
        if self._ocr1a is None:
            raise TrialAbort("configure() before start()")
        self._frames, self._stopped, self._error = [], None, None
        self._stop.clear()
        self._command(f"START,{stim}", "SYNC,")
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def stop(self) -> Capture:
        self._ser.write(b"STOP\n")
        self._stop.set()
        self._reader.join(timeout=2 * TIMEOUT_S)
        if self._error:
            raise TrialAbort(self._error)
        if self._stopped is None:
            raise TrialAbort("missing STOPPED")
        return self._assemble()

    def close(self) -> None:
        self._ser.close()

    def _read_loop(self) -> None:
        buf, deadline = bytearray(), None
        try:
            while self._stopped is None:
                chunk = self._ser.read(self._ser.in_waiting or 64)
                buf = self._consume(buf + chunk)
                if self._stop.is_set():
                    deadline = deadline or time.perf_counter() + TIMEOUT_S
                    if time.perf_counter() > deadline:
                        return
                if not chunk:
                    time.sleep(0.001)
        except TrialAbort as exc:
            self._error = str(exc)

    def _consume(self, data: bytearray) -> bytearray:
        while data:
            stop_at, magic_at = data.find(b"STOPPED,"), data.find(MAGIC)
            if stop_at >= 0 and (magic_at < 0 or stop_at < magic_at):
                nl = data.find(b"\n", stop_at)
                if nl < 0:
                    return data
                self._stopped = [
                    int(p) for p in data[stop_at:nl].decode().split(",")[1:]
                ]
                return data[nl + 1 :]
            if magic_at < 0:
                return data[-8:]  # keep a split "STOPPED," or magic for the next read
            n = frame_length(data, magic_at)
            if n is None or len(data) - magic_at < n:
                return data[magic_at:]
            frame = parse_frame(bytes(data[magic_at : magic_at + n]))
            if frame is None:
                raise TrialAbort(f"bad CRC in frame after seq {len(self._frames) - 1}")
            if not self._frames and frame.seq != 0:
                raise TrialAbort("missing initial frame")
            if self._frames and frame.seq != (self._frames[-1].seq + 1) & 0xFFFF:
                raise TrialAbort(f"seq gap: {self._frames[-1].seq} -> {frame.seq}")
            self._frames.append(frame)
            data = data[magic_at + n :]
        return data

    def _assemble(self) -> Capture:
        samples = [f for f in self._frames if f.kind == SAMPLE]
        if samples and samples[0].tick0 not in (0, 1):
            raise TrialAbort("missing first ADC samples")
        ev = np.concatenate(
            [f.values for f in self._frames if f.kind == EVENT]
            or [np.empty(0, np.uint16)]
        )
        ev = ev.reshape(-1, 3).astype(np.int64)
        ticks = [f.tick0 + np.arange(len(f.values), dtype=np.int64) for f in samples]
        return Capture(
            ticks=np.concatenate(ticks or [np.empty(0, np.int64)]),
            values=np.concatenate(
                [f.values for f in samples] or [np.empty(0, np.uint16)]
            ),
            channels=self._channels,
            flash_tick=ev[:, 0] | (ev[:, 1] << 16),
            flash_sub=ev[:, 2],
            ocr1a=self._ocr1a,
            dropped=sum(self._stopped),
            clock_hz=self.clock_hz,
            adc_bits=self.adc_bits,
            board=self.board,
            v_ref=self.v_ref,
            source="physical",
        )


def open_board(port: str) -> Board:
    try:
        import serial
    except ImportError as exc:
        raise TrialAbort(
            "pyserial is required: pip install -e '.[acquisition]'"
        ) from exc
    ser = serial.Serial(port, BAUD, timeout=TIMEOUT_S)
    time.sleep(RESET_WAIT_S)
    ser.reset_input_buffer()
    ser.write(b"PING\n")
    fw, adc_bits, clock_hz = parse_pong(
        ser.readline().decode("ascii", errors="replace")
    )
    if adc_bits not in (10, 12):
        ser.close()
        raise TrialAbort(
            f"expected a 10-bit UNO or 12-bit Teensy 4.1 ADC, board reports {adc_bits}"
        )
    return Board(ser, clock_hz, adc_bits, fw)
