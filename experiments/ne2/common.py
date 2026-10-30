"""Shared pieces of the circuit-A experiment scripts (see experiments/README.md)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from plasma_rc.trials.metadata import CONTROLS, REGIMES, RunMeta

RESULTS = Path(__file__).resolve().parents[2] / "results"


def parser(doc: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=doc, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--bench",
        default="bench.yaml",
        help="measured values (copy of bench.example.yaml)",
    )
    p.add_argument(
        "--config",
        default=None,
        help="software settings (default: package config.yaml)",
    )
    return p


def add_run_args(p: argparse.ArgumentParser) -> None:
    """Metadata the operator must give for every run; nothing is defaulted."""
    p.add_argument(
        "--bulb", required=True, help="label of the bulb in the socket, e.g. B1"
    )
    p.add_argument("--regime", required=True, choices=REGIMES)
    p.add_argument("--control", required=True, choices=CONTROLS)
    p.add_argument(
        "--temp", required=True, type=float, help="ambient temperature [degC]"
    )
    p.add_argument(
        "--warmup", required=True, type=float, help="minutes the bulb has been powered"
    )
    p.add_argument(
        "--vs", required=True, type=float, help="module output V_s measured now [V]"
    )
    p.add_argument("--jumpers", required=True, help='e.g. "J_C in, Rs_A"')


def run_meta(args, repeat: int) -> RunMeta:
    return RunMeta(
        args.bulb,
        args.regime,
        args.control,
        args.temp,
        args.warmup,
        args.vs,
        args.jumpers,
        repeat,
    )


def opt(bench: dict, key: str):
    """A bench value that is allowed to be still pending (None)."""
    from plasma_rc.acquisition.bench import BenchError, need

    try:
        return need(bench, key)[0]
    except BenchError:
        return None


def connect(args, ocr1a: int | None = None, channels: str | None = None):
    """Open and configure the UNO. Returns (board, bench, cfg, tick_hz)."""
    from plasma_rc.acquisition.bench import load_bench, need
    from plasma_rc.acquisition.config import load_config
    from plasma_rc.acquisition.serial_io import open_board

    bench, cfg = load_bench(args.bench), load_config(args.config)
    if cfg.port is None:
        raise SystemExit("set port in config.yaml (e.g. /dev/ttyACM0)")
    ocr1a = ocr1a if ocr1a is not None else need(bench, "acquisition.ocr1a")[0]
    channels = channels or need(bench, "acquisition.channels")[0]
    board = open_board(cfg.port)
    board.v_ref = opt(bench, "acquisition.adc_vref")
    board.configure(ocr1a, channels)
    return board, bench, cfg, board.clock_hz / (ocr1a + 1)


def sine_stim(freq_hz: float, tick_hz: float, amp: int) -> tuple[str, float]:
    """START argument for the UNO's DDS sine and the frequency it will actually produce."""
    inc = round(freq_hz * 2**32 / tick_hz)
    return f"SINE,{inc},{amp}", inc * tick_hz / 2**32


def lockin(
    ticks: np.ndarray, values: np.ndarray, freq_hz: float, tick_hz: float
) -> float:
    """Amplitude of the component of a sampled signal at freq_hz (in the signal's units)."""
    t = ticks / tick_hz
    x = values - values.mean()
    return float(
        2
        * np.hypot(
            np.mean(x * np.cos(2 * np.pi * freq_hz * t)),
            np.mean(x * np.sin(2 * np.pi * freq_hz * t)),
        )
    )
