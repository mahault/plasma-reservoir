"""Per-step reservoir features from one capture (readout input x(k), technical.md §5)."""

from __future__ import annotations

import numpy as np

from plasma_rc.trials.capture import Capture


def step_features(cap: Capture, ticks_per_step: int, n_steps: int, analog=("1", "2", "3"),
                  tick_start: int = 0) -> np.ndarray:
    """(n_steps, len(analog) + 2): mean of each analog pin per step, flashes per step, and the
    last inter-flash interval [s] at the end of the step (0 until two flashes have occurred)."""
    cols = []
    for pin in analog:
        ticks, values = cap.channel(pin)
        step = (ticks - tick_start) // ticks_per_step
        ok = (step >= 0) & (step < n_steps)
        counts = np.bincount(step[ok], minlength=n_steps)
        if (counts == 0).any():
            raise ValueError(f"pin {pin}: some steps have no samples; use more ticks per step")
        cols.append(np.bincount(step[ok], weights=values[ok], minlength=n_steps) / counts)
    t = cap.flash_tick + cap.flash_sub / (cap.ocr1a + 1)  # flash times in ticks
    fstep = np.floor((t - tick_start) / ticks_per_step).astype(int)
    ok = (fstep >= 0) & (fstep < n_steps)
    cols.append(np.bincount(fstep[ok], minlength=n_steps).astype(float))
    intervals = np.diff(t, prepend=np.nan) / cap.tick_hz
    ends = tick_start + ticks_per_step * np.arange(1, n_steps + 1)
    last = np.searchsorted(t, ends, side="left") - 1  # index of the last flash before each step end
    has_two = last >= 1
    cols.append(np.where(has_two, intervals[np.where(has_two, last, 0)] if len(t) else 0.0, 0.0))
    return np.column_stack(cols)
