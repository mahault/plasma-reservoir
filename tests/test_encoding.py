"""plasma_rc.encoding: audio -> drive u(t) at the tick rate."""

import numpy as np
import pytest
from scipy.io import wavfile

from plasma_rc.encoding import band_rms, binary_mask, frame_rms, load_audio, masked_drive, to_ticks

FS, TICK_HZ = 8000, 24000


def test_load_wav_full_scale(tmp_path):
    x = (np.sin(np.linspace(0, 20, 800)) * 16384).astype(np.int16)
    wavfile.write(tmp_path / "a.wav", FS, x)
    y, fs = load_audio(tmp_path / "a.wav")
    assert fs == FS and y.max() == pytest.approx(0.5, abs=1e-3)


def test_to_ticks_keeps_length_and_amplitude():
    t = np.arange(FS // 2) / FS
    y = to_ticks(0.5 * np.sin(2 * np.pi * 300 * t), FS, TICK_HZ)
    assert len(y) == pytest.approx(TICK_HZ // 2, abs=2) and np.abs(y).max() == pytest.approx(0.5, rel=0.02)


def test_frame_rms_of_sine_and_silence():
    t = np.arange(FS) / FS
    r = frame_rms(np.concatenate([np.sin(2 * np.pi * 400 * t), np.zeros(FS)]), FS, 0.01)
    assert len(r) == 200 and r[:100] == pytest.approx(np.full(100, 1 / np.sqrt(2)), rel=0.01) and not r[100:].any()


def test_band_rms_puts_a_tone_in_its_band():
    t = np.arange(FS) / FS
    b = band_rms(np.sin(2 * np.pi * 1000 * t), FS, 0.01, n_bands=8)
    assert b.shape == (100, 8) and np.argmax(b[50:].mean(0)) == np.argmax(b.mean(0))
    assert b[50:].mean(0).max() > 5 * np.median(b[50:].mean(0))


def test_masked_drive_holds_each_virtual_node_and_is_silent_on_silence():
    m = binary_mask(4, 8, seed=0)
    assert set(np.unique(m)) == {-1.0, 1.0} and np.array_equal(m, binary_mask(4, 8, seed=0))
    bands = np.vstack([np.zeros((3, 8)), np.ones((2, 8))])
    d = masked_drive(bands, m)
    assert d.shape == (5 * 4,) and not d[:12].any() and np.array_equal(d[12:16], m.sum(1))
