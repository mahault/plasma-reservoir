"""Optional AVR firmware validation; only this adapter needs Arduino and simavr."""

import io
import os
import shutil
import subprocess
from pathlib import Path
import numpy as np
from plasma_rc.acquisition.protocol import parse_pong
from plasma_rc.acquisition.serial_io import Board

ROOT = Path(__file__).resolve().parents[2]

# ---- firmware on simavr (firmware/sim/ne2_sim.c) ----
TICK = 2000  # CONF,1999 -> OCR1A + 1 cycles per tick; the harness assumes the same
STEPS = (7, 20, 11, 30, 4)  # seed_p, n_p, seed_c, n_c, ticks_per_step
RUN_TICKS = 800
INCLUDE = Path(os.environ.get("SIMAVR_INCLUDE", "/usr/include"))
LIB = Path("/usr/lib/x86_64-linux-gnu/libsimavr.so.2")


class ReplaySerial(io.BytesIO):
    """The simulated UART output played back to Board; commands were already fed to simavr."""

    def write(self, data):
        return len(data)

    @property
    def in_waiting(self):
        return len(self.getbuffer()) - self.tell()


def arduino_cli() -> str | None:
    cli = shutil.which("arduino-cli") or str(Path.home() / ".local/bin/arduino-cli")
    return cli if Path(cli).exists() else None


def firmware_tools_present() -> bool:
    return bool(
        (ROOT / "firmware/ne2_uno").exists()
        and arduino_cli()
        and shutil.which("gcc")
        and LIB.exists()
        and (INCLUDE / "simavr/sim_avr.h").exists()
    )


def firmware_sim(out: Path) -> dict:
    """Compile the firmware and the harness, run one STEPS trial, decode it with the host Board."""
    subprocess.run(
        [
            arduino_cli(),
            "compile",
            "-b",
            "arduino:avr:uno",
            "--output-dir",
            out,
            ROOT / "firmware/ne2_uno",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "gcc",
            "-O2",
            f"-I{INCLUDE}",
            f"-I{INCLUDE / 'simavr'}",
            ROOT / "firmware/sim/ne2_sim.c",
            LIB,
            "-o",
            out / "ne2_sim",
        ],
        check=True,
        capture_output=True,
    )
    stim = "STEPS," + ",".join(map(str, STEPS))
    subprocess.run(
        [
            out / "ne2_sim",
            out / "ne2_uno.ino.elf",
            out,
            f"PING\nCONF,1999,0123\nSTART,{stim}\n",
            str(RUN_TICKS),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    ser = ReplaySerial((out / "uart.bin").read_bytes())
    fw, bits, _ = parse_pong(ser.readline().decode())
    board = Board(ser)
    board.configure(1999, "0123")
    board.start(stim)
    meta = np.loadtxt(out / "meta.txt", dtype=np.int64)
    return {
        "fw": fw,
        "bits": bits,
        "cap": board.stop(),
        "start": meta[0],
        "pulses": meta[1:],
        "dac": np.loadtxt(out / "dac.txt", dtype=np.int64),
    }
