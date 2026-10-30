"""The real ne2_uno firmware on a simulated ATmega328P (simavr), decoded by the host Board code.

Needs arduino-cli (core arduino:avr), gcc, and simavr headers + library (libsimavr-dev);
SIMAVR_INCLUDE overrides the header root (default /usr/include). Skipped when any is missing.
What simavr cannot show: analog front-end, comparator noise canceller timing, real UART jitter.
"""

import numpy as np
import pytest

from plasma_rc.stimuli import replica_levels
from plasma_rc.sim import RUN_TICKS, STEPS, TICK, firmware_sim, firmware_tools_present

VOLTS = np.array([1.0, 2.0, 3.0, 4.0])  # harness inputs on A0..A3


@pytest.fixture(scope="module")
def sim(tmp_path_factory):
    if not firmware_tools_present():
        pytest.skip("needs arduino-cli, gcc and libsimavr-dev")
    return firmware_sim(tmp_path_factory.mktemp("sim"))


def test_handshake(sim):
    assert (sim["fw"], sim["bits"]) == ("ne2-uno-1", 10)


def test_samples_contiguous_and_scaled(sim):
    cap = sim["cap"]
    assert cap.dropped == 0
    assert abs(len(cap.ticks) - RUN_TICKS) <= 2
    # one conversion per tick, none lost; the first compare B is at the first wrap (cycle TICK), so tick 1
    assert np.array_equal(cap.ticks, np.arange(1, len(cap.ticks) + 1))
    for pin, v in zip("0123", VOLTS):
        _, counts = cap.channel(pin)
        # datasheet: Vin * 1024 / Vref (AVcc = 5 V); simavr scales by 1023, so allow 2 counts
        assert np.all(np.abs(counts.astype(int) - v / 5.0 * 1024) <= 2), pin


def test_flash_times_match_injected_pulses(sim):
    cap = sim["cap"]
    true_cycles = sim["pulses"] - sim["start"]
    measured_cycles = cap.flash_times_s() * 16e6
    assert len(measured_cycles) == len(true_cycles)  # includes pulses on both sides of a Timer1 wrap
    err = measured_cycles - true_cycles
    assert np.ptp(err) <= 1 and abs(err.mean()) <= 4, err  # constant sub-µs latency only


def test_dac_plays_host_replica(sim):
    seed_p, n_p, seed_c, n_c, tps = STEPS
    cycles, levels = sim["dac"].T
    want = np.append(replica_levels(seed_p, n_p, seed_c, n_c), 128)  # then mid-scale
    at = sim["start"] + (np.arange(len(want)) * tps + tps // 2) * TICK  # middle of each held step
    got = levels[np.searchsorted(cycles, at, side="right") - 1]
    assert np.array_equal(got, want)
