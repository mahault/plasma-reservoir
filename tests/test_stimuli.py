import numpy as np

from plasma_rc.stimuli import held_input, pulse_pairs, ramp, steps


def test_held_input_is_exactly_quantized_and_reproducible():
    levels, u = held_input(500, seed=7, n_levels=256)
    assert levels.min() >= 0 and levels.max() <= 255
    np.testing.assert_array_equal(u, 0.5 * levels / 255)       # NARMA range [0, 0.5]
    np.testing.assert_array_equal(held_input(500, seed=7)[0], levels)


def test_steps_and_ramp_segments():
    seg = steps(np.array([3, 4]), 10)
    np.testing.assert_array_equal(seg, [[3, 10], [4, 10]])
    r = ramp(0, 3, 5)
    np.testing.assert_array_equal(r[:, 0], [0, 1, 2, 3, 2, 1, 0])
    assert (r[:, 1] == 5).all()


def test_pulse_pairs_identical_present_different_past():
    rests = [10, 100, 1000]
    seg, trials = pulse_pairs(rests, cond=200, test=180, base=0, sham=60,
                              pulse_ticks=20, settle_ticks=500, repeats=2, seed=1)
    assert len(trials) == 2 * len(rests) * 2                   # rests x {real, sham} x repeats
    assert sorted(t["rest_ticks"] for t in trials) == sorted(rests * 4)
    starts = np.concatenate([[0], np.cumsum(seg[:, 1])])
    for t in trials:
        i = t["test_segment"]
        assert seg[i, 0] == 180 and seg[i, 1] == 20 and starts[i] == t["test_onset_tick"]
        assert seg[i - 1, 0] == 0 and seg[i - 1, 1] == t["rest_ticks"]
        assert seg[i - 2, 0] == (60 if t["sham"] else 200)
    assert [t["rest_ticks"] for t in trials] != rests * 4      # order randomized
