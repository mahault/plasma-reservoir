import copy

import numpy as np
import pytest

from plasma_rc.hw.records import Capture
from plasma_rc.hw.recording import load, save, segment_states
from tests.test_circuit import RAW


def raw_cfg():
    raw = copy.deepcopy(RAW)
    raw["sensors"] = {k: {"value": g, "unit": "-", "source": "assumed"}
                      for k, g in (("gain_drive", 100.0), ("gain_v", 50.0), ("gain_vs", 1.0),
                                   ("gain_light", 2.0), ("dark_light", 0.1))}
    return raw


def capture(dropped=0):
    # channels "0123" round robin from tick 1; ADC code = tick; 12 bit, 3.3 V reference
    ticks = np.arange(1, 41)
    return Capture(ticks=ticks, values=ticks.astype(np.uint16), channels="0123",
                   flash_tick=np.array([7]), flash_sub=np.array([3]), ocr1a=5999, dropped=dropped,
                   clock_hz=600e6, adc_bits=12, v_ref=3.3, board="ne2h-teensy41-1", source="physical")


def test_segment_states_follow_firmware_tick_boundaries():
    seg = np.array([[0, 20], [255, 20]])       # segment 0: ticks [0, 20), segment 1: [20, 40)
    x, names = segment_states(capture(), seg, raw_cfg(), samples=1)
    assert names == ["drive", "v", "v_s", "light"]
    volt = 3.3 / 4096
    # pin 0 is sampled at ticks 1, 5, ..., 17 in segment 0 (mean code 9) and 21, ..., 37 in segment 1 (29)
    np.testing.assert_allclose(x[:, 0, 0], [9 * volt * 100, 29 * volt * 100])
    # pin 3 at ticks 4, 8, 12, 16 in segment 0 (tick 20 starts segment 1): mean code 10
    np.testing.assert_allclose(x[0, 0, 3], 2.0 * (10 * volt - 0.1))


def test_save_load_round_trip_and_refusals(tmp_path):
    seg = np.array([[0, 20], [255, 20]])
    meta = {"stage": "E0", "bulb_id": "dummy-R", "session": "s1"}
    path = tmp_path / "r.npz"
    save(path, capture(), raw_cfg(), seg, meta)
    cap, cfg, seg2, meta2 = load(path)
    np.testing.assert_array_equal(cap.values, capture().values)
    np.testing.assert_array_equal(seg2, seg)
    assert meta2 == meta and cfg.get("sensors", "gain_v") == 50.0
    with pytest.raises(FileExistsError):
        save(path, capture(), raw_cfg(), seg, meta)
    with pytest.raises(ValueError, match="dropped"):
        save(tmp_path / "d.npz", capture(dropped=3), raw_cfg(), seg, meta)
