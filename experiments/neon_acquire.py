"""Record a neon or LED experiment using a configured acquisition board."""
import argparse
import math
from pathlib import Path

from plasma_rc.neon.capture import RunConditions
from plasma_rc.neon.experiment import record_trial
from plasma_rc.neon.serial_io import open_board


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--port", required=True)
    parser.add_argument("--device", required=True, choices=("neon", "led"))
    parser.add_argument("--regime", required=True, choices=("near-breakdown", "always-on", "led"))
    parser.add_argument("--device-id", required=True)
    for name in ("ballast", "voltage-limit", "current-limit", "adc-ref", "temperature", "warmup"):
        parser.add_argument(f"--{name}", type=float, required=True)
    for name in ("timer", "ticks-per-step", "steps", "seed"):
        parser.add_argument(f"--{name}", type=int, required=True)
    parser.add_argument("--channels", required=True)
    for name in ("drive-pin", "light-pin", "voltage-pin"):
        parser.add_argument(f"--{name}", required=True)
    for name in ("drive-gain", "divider-gain", "dark-voltage"):
        parser.add_argument(f"--{name}", type=float, required=True)
    args = parser.parse_args(argv)
    conditions = RunConditions(args.device, args.regime, args.ballast, args.voltage_limit,
                               args.current_limit, args.device_id, args.temperature, args.warmup,
                               args.drive_pin, args.light_pin, args.voltage_pin, args.drive_gain,
                               args.divider_gain, args.dark_voltage)
    if (args.output.exists() or args.output.suffix != ".npz" or not math.isfinite(args.adc_ref) or args.adc_ref <= 0
            or args.steps <= 0 or args.ticks_per_step <= 0 or not 0 < args.seed < 2**32
            or not 0 <= args.timer <= 65535 or len(set(args.channels)) != len(args.channels)
            or len(args.channels) < 3 or set(args.channels) - set("01234") or
            not {args.drive_pin, args.light_pin, args.voltage_pin}.issubset(args.channels) or
            args.ticks_per_step < 2 * len(args.channels) + 1):
        parser.error("invalid output, ADC, timing, seed or channels")
    print("Limits are recorded metadata; this software does not limit the external driver.")
    board = open_board(args.port)
    try:
        board.v_ref = args.adc_ref
        board.configure(args.timer, args.channels)
        record_trial(board, args.output, conditions, args.seed, args.steps,
                     args.ticks_per_step, board.clock_hz / (args.timer + 1))
    finally:
        board.close()


if __name__ == "__main__":
    main()
