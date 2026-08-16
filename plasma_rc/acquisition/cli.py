"""CLI: ping the Teensy or run a capture session."""

from __future__ import annotations

import argparse
import sys

from .config import load_config
from .serial_io import open_board
from .session import run_session


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plasma_rc.acquisition")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    parser.add_argument("--port", default=None, help="serial port (overrides config)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping", help="PING/PONG handshake and exit")
    sub.add_parser("run", help="play the audio tree and record raw captures")
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    if args.port is not None:
        cfg.port = args.port
    if args.cmd == "ping":
        board = open_board(cfg.port, cfg.fs_hz, cfg.adc_bits)
        try:
            print(
                f"PONG fw={board.fw_version} FS_HZ={board.fs_hz} "
                f"adc_bits={board.adc_bits} channels=2"
            )
        finally:
            board.close()
        return 0
    run_session(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
