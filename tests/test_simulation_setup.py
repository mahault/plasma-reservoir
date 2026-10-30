"""Profile isolation and time-label correctness for the numerical adapter."""

import dataclasses
import math
import numpy as np
import pytest
from plasma_rc.bulb_model import simulate


def test_profiles_do_not_share_mutable_study_defaults():
    from plasma_rc.simulation.config import TEENSY41, UNO, circuit, SimulationSetup

    a = circuit(profile=UNO)
    b = circuit(profile=TEENSY41)
    assert (a.adc_bits, b.adc_bits, a.v_ref, b.v_ref) == (10, 12, 5.0, 3.3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        TEENSY41.ocr1a = 1
    run = SimulationSetup(b, TEENSY41, seed=4)
    c = run.run(np.zeros(3), ticks_per_step=8)
    assert c.source == "simulation" and c.adc_bits == 12 and c.board == "teensy41"
    assert run.metadata()["seed"] == 4


def test_first_adc_label_matches_first_tick_integration():
    from plasma_rc.simulation.config import circuit

    p = dataclasses.replace(
        circuit(),
        bulb=False,
        V_th=60.0,
        R_th=1e4,
        C=1e-8,
        Re=1e15,
        tau_aa=1e-12,
        noise_counts=0.0,
        k_v=0.04,
        adc_bits=10,
        v_ref=5.0,
    )
    cap = simulate(
        p, np.zeros(3), 4, 2665, np.random.default_rng(0), channels="3", dv0=30.0
    )
    tick_s = 2666 / 16e6
    expected = round((60.0 + 30.0 * math.exp(-tick_s / 1e-4)) * 0.04 / 5.0 * 1024)
    assert cap.ticks[0] == 1
    assert cap.values[0] == pytest.approx(expected, abs=1)
