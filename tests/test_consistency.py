from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from plasma_rc.acquisition.serial_io import RawCapture
from plasma_rc.acquisition.session import write_npz
from plasma_rc.characterization.consistency import load_repeat_traces, pairwise_consistency


def test_pairwise_consistency_two_identical_traces_is_one():
    trace = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    traces = np.stack([trace, trace])
    assert pairwise_consistency(traces) == pytest.approx(1.0)


def test_pairwise_consistency_three_trials_averages_pairs():
    # a = [1,2,3]; b = 2*a (affine positive slope -> corr(a,b) = +1);
    # c = 4-a (affine negative slope -> corr(a,c) = corr(b,c) = -1).
    # These are well-known algebraic facts about Pearson correlation under
    # affine transforms, computed independently of pairwise_consistency's
    # own implementation. Expected mean of the three pairs: (1 - 1 - 1)/3.
    a = np.array([1.0, 2.0, 3.0])
    b = 2 * a
    c = 4 - a
    traces = np.stack([a, b, c])
    assert pairwise_consistency(traces) == pytest.approx(-1.0 / 3.0)


def test_pairwise_consistency_independent_noise_is_near_zero():
    # For large N, independent Gaussian samples have sample correlation
    # concentrated near 0 (a standard statistical fact, not derived from
    # pairwise_consistency's own implementation).
    rng = np.random.default_rng(0)
    traces = rng.standard_normal((5, 20000))
    assert abs(pairwise_consistency(traces)) < 0.05


def _write_fake_capture(path: Path, brightness: np.ndarray, audio_in: np.ndarray, fs_hz: int) -> None:
    capture = RawCapture(
        t_us=np.arange(len(brightness), dtype=np.int64) * (1_000_000 // fs_hz),
        audio_in=audio_in.astype(np.uint16),
        brightness=brightness.astype(np.uint16),
        dropped=0,
        frames_sent=1,
        sync_offset_us=0,
        fs_hz=fs_hz,
    )
    write_npz(path, capture)


def test_load_repeat_traces_discards_transient_and_aligns_length(tmp_path: Path):
    fs_hz = 100
    # 10 samples total; discard_s=0.05 at fs=100 -> discard first 5 samples.
    p1 = tmp_path / "r1.npz"
    p2 = tmp_path / "r2.npz"
    _write_fake_capture(p1, np.arange(10, 20), np.zeros(10), fs_hz)
    _write_fake_capture(p2, np.arange(20, 28), np.zeros(8), fs_hz)  # one shorter trial

    traces = load_repeat_traces([p1, p2], channel="brightness", discard_s=0.05, fs_hz=fs_hz)
    assert traces.shape == (2, 3)  # 8 - 5 = 3 samples is the shortest post-discard length
    np.testing.assert_array_equal(traces[0], [15, 16, 17])
    np.testing.assert_array_equal(traces[1], [25, 26, 27])
