"""Per-step features from a capture: channel means, flash count, last inter-flash interval."""

import numpy as np

from plasma_rc.trials.capture import Capture
from plasma_rc.characterization.features import step_features


def test_step_features_known_values():
    ticks = np.arange(16)
    values = np.tile(np.array([0, 10, 20, 30], dtype=np.uint16), 4)  # channels "0123"
    values[8:] += 1  # second half of the run
    cap = Capture(ticks=ticks, values=values, channels="0123",
                  flash_tick=np.array([1, 3, 10]), flash_sub=np.array([0, 0, 0]),
                  ocr1a=1999, dropped=0)
    x = step_features(cap, ticks_per_step=8, n_steps=2, analog=("1", "2", "3"))
    np.testing.assert_allclose(x[:, :3], [[10, 20, 30], [11, 21, 31]])
    np.testing.assert_allclose(x[:, 3], [2, 1])                       # flashes per step
    np.testing.assert_allclose(x[:, 4], [2 / cap.tick_hz, 7 / cap.tick_hz])  # last interval


def test_no_flashes_gives_zero_counts_and_intervals():
    cap = Capture(ticks=np.arange(8), values=np.full(8, 100, dtype=np.uint16), channels="0123",
                  flash_tick=np.array([], dtype=np.int64), flash_sub=np.array([], dtype=np.int64),
                  ocr1a=1999, dropped=0)
    x = step_features(cap, ticks_per_step=4, n_steps=2)
    np.testing.assert_array_equal(x[:, 3:], 0.0)
