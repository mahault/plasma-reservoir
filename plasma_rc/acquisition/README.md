# Acquisition pipeline

PC-side capture for the Teensy 4.1 plasma setup. Records only `(t_us, audio_in, brightness)` at **100 kHz** (one sample every 10 µs). Frequency and settle are computed later, not here.

## Install

```bash
pip install -e ".[acquisition]"
```

`pydub` needs `ffmpeg` on PATH if `soundfile` cannot decode mp3.

## Config

[`config.yaml`](config.yaml) next to this package. Paths (`audio_root`, `out_dir`) are resolved from the process working directory.

- `fs_hz: 100000` — record clock. Handshake fails if the board reports a different rate.
- `audio_root: ./data/Data`
- `out_dir: ./data/out`
- `audio_device: null` — first `run` prompts and writes the index back into this file. Do not commit a machine-specific index.

## Commands

```bash
python -m plasma_rc.acquisition ping
python -m plasma_rc.acquisition run
python -m plasma_rc.acquisition --config /path/to/config.yaml --port /dev/ttyACM0 ping
```

`ping` only checks PING/PONG. `run` plays every `*.mp3` under `audio_root` (pre-roll, file, post-roll) while the Teensy streams, then writes:

- `out_dir/raw/<speaker>/<condition>/<label>/<stem>.npz` — arrays `t_us`, `audio_in`, `brightness` and scalar `fs_hz`
- `out_dir/index.csv` — one row per successful trial

A trial with a bad CRC or `block_seq` gap is aborted: nothing is written for that file, then the next mp3 runs.

## Hardware

Teensy 4.1 analog pins are **3.3 V max, not 5 V tolerant**. Scale and clamp the breakout tap and photodiode load before connecting. Firmware is not in this package; it must sample at 100 kHz to match `fs_hz`. 1 MHz is a later experiment, not the default.

## Tests without a board

[`tests/test_acquisition_hardware.py`](../../tests/test_acquisition_hardware.py) uses a FakeSerial. Set `USE_REAL_HARDWARE = True` only for a short real ping/stream; CRC-injection tests stay fake.
