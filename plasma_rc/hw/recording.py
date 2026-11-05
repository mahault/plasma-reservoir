"""Physical recordings: raw capture + the exact parameter file, waveform segments and run metadata.

Channel convention (CIRC-03, firmware/ne2h/ne2h.ino): pin 0 drive monitor, 1 node voltage v, 2 sense v_S,
3 light. Physical value = gain · ADC volts (light: gain · (ADC volts - dark_light)); gains come from the
"sensors" section of the parameter file and are measured in E0.
Segment i occupies ticks [S_i, S_i+1) with S_0 = 0 and S_i the cumulative tick count (firmware switches
level at the start of tick S_i, before that tick's conversion).
"""
import json
import os
import tempfile
from pathlib import Path

import numpy as np

from plasma_rc.circuit import Config
from plasma_rc.hw.records import Capture
from plasma_rc.states import window_means

CHANNELS = {"drive": "0", "v": "1", "v_s": "2", "light": "3"}
_FIELDS = ("ticks", "values", "channels", "flash_tick", "flash_sub", "ocr1a", "dropped", "clock_hz",
           "adc_bits", "v_ref", "board", "source")


def save(path, capture, cfg_raw, segments, meta):
    """Atomically write a new recording; never overwrite, never keep a capture with dropped data."""
    capture.require_integrity()
    if capture.adc_bits is None or capture.v_ref is None:
        raise ValueError("ADC calibration is required")
    Config(cfg_raw)  # validate tags before saving
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".rec-", suffix=".npz", delete=False) as tmp:
        np.savez(tmp, **{f: getattr(capture, f) for f in _FIELDS}, config=json.dumps(cfg_raw),
                 segments=np.asarray(segments, np.int64), meta=json.dumps(meta))
    try:
        os.link(tmp.name, path)  # fails if path appeared meanwhile
    finally:
        os.unlink(tmp.name)


def load(path):
    with np.load(path, allow_pickle=False) as d:
        cap = Capture(**{f: (d[f].item() if d[f].ndim == 0 else d[f]) for f in _FIELDS})
        cap.require_integrity()
        return cap, Config(json.loads(str(d["config"]))), d["segments"].copy(), json.loads(str(d["meta"]))


def segment_states(capture, segments, cfg_raw, samples):
    """Hardware adapter of plasma_rc.states: (n_segments, samples, channels) sub-window means of each recorded
    channel, in physical units (READ-01)."""
    cfg = Config(cfg_raw) if isinstance(cfg_raw, dict) else cfg_raw
    starts = np.concatenate([[0], np.cumsum(np.asarray(segments)[:, 1])])
    names = [n for n, pin in CHANNELS.items() if pin in capture.channels]
    out = np.full((len(segments), samples, len(names)), np.nan)
    volts_per_code = capture.v_ref / 2 ** capture.adc_bits
    for c, name in enumerate(names):
        ticks, codes = capture.channel(CHANNELS[name])
        volts = codes * volts_per_code
        if name == "light":
            volts = volts - cfg.get("sensors", "dark_light")
        volts = volts * cfg.get("sensors", "gain_" + {"v_s": "vs"}.get(name, name))
        out[:, :, c] = window_means(ticks, volts, starts, samples)
    return out, names
