from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from plasma_rc.reservoir.physical import (
    LivePlasmaReservoir,
    PlasmaDataLoader,
    PlasmaSample,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "plasma"


class FakeTransport:
    def __init__(self, samples: list[PlasmaSample]):
        self.samples = list(samples)
        self.writes: list[float] = []
        self.reset_called = False

    def reset(self) -> None:
        self.reset_called = True

    def write_voltage(self, voltage_input: float) -> None:
        self.writes.append(voltage_input)

    def read_sample(self) -> PlasmaSample:
        if not self.samples:
            raise RuntimeError("no sample")
        return self.samples.pop(0)


def test_list_trials_parses_expected_files():
    loader = PlasmaDataLoader(FIXTURE_DIR)
    trials = loader.list_trials()
    parsed = [t for t in trials if t["word"] == "hello" and t["volume_pct"] == 70 and t["trial_id"] == 0]
    assert len(parsed) == 1


def test_load_trial_returns_baseline_subtracted_states():
    loader = PlasmaDataLoader(FIXTURE_DIR)
    signal, states = loader.load_trial("hello", 70, 0)
    np.testing.assert_allclose(signal[:3], np.array([0.1, 0.2, 0.3]))
    assert states.shape == (len(signal), 3)
    np.testing.assert_allclose(states[0], np.array([0.0, 0.0, 0.0]))


def test_load_trial_missing_file_raises():
    loader = PlasmaDataLoader(FIXTURE_DIR)
    with pytest.raises(FileNotFoundError):
        loader.load_trial("missing", 1, 0)


def test_load_trial_missing_column_raises(tmp_path: Path):
    src = FIXTURE_DIR / "bad_missing_column.csv"
    dst = tmp_path / "broken_80_0.csv"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    loader = PlasmaDataLoader(tmp_path)
    with pytest.raises(ValueError, match="Missing required column"):
        loader.load_trial("broken", 80, 0)


def test_live_reservoir_uses_baseline_subtraction():
    transport = FakeTransport(
        [
            PlasmaSample(1.0, 2.0, 3.0, 0.0),  # baseline
            PlasmaSample(1.5, 2.3, 3.7, 0.1),  # post-step
        ]
    )
    reservoir = LivePlasmaReservoir(transport=transport)
    reservoir.reset()
    state = reservoir.step(0.42)
    assert transport.reset_called is True
    assert transport.writes == [0.42]
    np.testing.assert_allclose(
        state.as_array(), np.array([0.5, 0.3, 0.7]), rtol=1e-7, atol=1e-7
    )
