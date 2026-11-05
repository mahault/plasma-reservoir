import copy
from types import SimpleNamespace

import numpy as np
import pytest

from experiments.acquire import check_safety, waveform
from experiments.analyze import e0
from plasma_rc.circuit import Config
from plasma_rc.hw.records import Capture
from tests.test_circuit import RAW


def test_e0_residual_is_exp_minus_t_over_tau_for_one_pole():
    # one channel, 1000 -> 3000 codes at tick 200 with tau = 10 ticks; residual sampled at tick 200 + 29
    ticks = np.arange(1, 400)
    codes = np.where(ticks < 200, 1000, 3000 - 2000 * np.exp(-(ticks - 200) / 10)).round().astype(np.uint16)
    cap = Capture(ticks=ticks, values=codes, channels="0", flash_tick=np.array([], int),
                  flash_sub=np.array([], int), ocr1a=5999, dropped=0, clock_hz=600e6, adc_bits=12,
                  v_ref=3.3, source="physical")
    out = e0(cap, None, np.array([[0, 200], [255, 200]]), {}, SimpleNamespace(step_ticks=30))
    assert out["drive"]["epsilon_max"] == pytest.approx(np.exp(-2.9), rel=0.02)


def test_waveforms_per_stage():
    e4 = dict(stage="e4", steps=100, seed=1, lo=200, hi=255, step_ticks=50, base=0, settle_ticks=500,
              prefix_steps=30, prefix_seed=9, n_seq=4, seq_len=5)
    seg, rec = waveform(SimpleNamespace(**e4, stimulus="held"))
    assert seg.shape == (100, 2) and seg[:, 0].min() >= 200 and len(rec["u"]) == 100
    seg, rec = waveform(SimpleNamespace(**e4, stimulus="prefix"))
    assert seg.shape == (130, 2) and rec["prefix_steps"] == 30 and len(rec["u"]) == 100
    seg, rec = waveform(SimpleNamespace(**e4, stimulus="binary"))
    assert set(seg[:, 0]) <= {205, 250} and len(rec["bits"]) == 100
    seg, rec = waveform(SimpleNamespace(**e4, stimulus="rank"))
    starts = rec["rank"]["starts"]                 # every sequence follows a settle at the base level
    assert len(starts) == 8 and all(seg[s - 1, 0] == 0 and seg[s - 1, 1] == 500 for s in starts)
    a = SimpleNamespace(stage="e1", lo=0, hi=10, hold=7)
    assert waveform(a)[0].shape == (21, 2)


def test_safety_gate_refuses_lamp_stages_without_bounds():
    raw = copy.deepcopy(RAW)                       # continuous bound fails: 101 kΩ < 105.3 kΩ
    with pytest.raises(SystemExit, match="continuous-current"):
        check_safety(Config(raw), "e1")
    check_safety(Config(raw), "e0")                # dummy loads only
    raw["circuit"]["R_B"]["value"] = 200e3         # now 211 kΩ >= 105.3 kΩ
    raw["lamp"]["V_b"] = {"value": None, "unit": "V", "source": "unknown"}
    check_safety(Config(raw), "e1")                # E1 measures the lamp
    with pytest.raises(ValueError, match="V_b"):
        check_safety(Config(raw), "e2")            # E2 needs E1 results first


def test_rank_waveform_rejects_sequence_shorter_than_readout():
    args = SimpleNamespace(stimulus="rank", lo=200, hi=255, n_seq=4, seq_len=2,
                           seed=0, base=0, settle_ticks=500, step_ticks=50)
    from experiments.acquire import e4_waveform
    with pytest.raises(ValueError, match="at least 3"):
        e4_waveform(args)


def test_e1_no_strike_does_not_invent_breakdown(monkeypatch):
    from experiments import analyze
    x = np.zeros((4, 1, 2))
    x[:, 0, 0] = [10, 20, 30, 20]
    monkeypatch.setattr(analyze, "segment_states", lambda *a, **k: (x, ["v", "v_s"]))
    cap = SimpleNamespace(tick_hz=1, flash_times_s=lambda: np.array([]))
    result = analyze.e1(cap, Config(RAW), np.array([[0, 10], [1, 10], [2, 10], [1, 10]]),
                        {}, SimpleNamespace(lit_current=1e-5))
    assert result["V_b_bracket_v"] is None


def test_repeat_requires_same_clock_and_channels():
    from experiments.analyze import check_repeat
    seg = np.array([[1, 20], [2, 20]])
    cap = SimpleNamespace(tick_hz=1000, channels="123")
    for other in (SimpleNamespace(tick_hz=2000, channels="123"),
                  SimpleNamespace(tick_hz=1000, channels="12")):
        with pytest.raises(ValueError):
            check_repeat(cap, seg, other, seg)
    check_repeat(cap, seg, cap, seg)


def test_e1_post_strike_mean_is_not_breakdown_bracket(monkeypatch):
    from experiments import analyze
    x = np.zeros((3, 1, 2))
    x[:, 0, 0] = [70, 50, 50]  # node collapses after strike: cannot serve as upper bound
    x[1:, 0, 1] = 1
    monkeypatch.setattr(analyze, "segment_states", lambda *a, **k: (x, ["v", "v_s"]))
    cap = SimpleNamespace(tick_hz=1, flash_times_s=lambda: np.array([11]))
    result = analyze.e1(cap, Config(RAW), np.array([[0, 10], [1, 10], [0, 10]]),
                        {}, SimpleNamespace(lit_current=1e-5))
    assert result["first_discharge_segment"] == 1
    assert result["V_b_bracket_v"] is None
    assert result["breakdown_status"] == "requires_pre_strike_waveform"
