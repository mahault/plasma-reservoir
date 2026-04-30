"""Physical plasma reservoir — data loader for real experimental recordings.

TODO (Majesti / Samuel):
    - Implement load_trial() to parse photodiode CSV recordings
    - Implement the Reservoir interface to wrap live hardware
    - Define the voltage encoding for audio→plasma injection
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .interface import Reservoir, ReservoirState


class PlasmaDataLoader:
    """Load pre-recorded plasma trials from disk.

    Expected CSV format per trial:
        timestamp, voltage_in, intensity, frequency, oscillation

    One file per trial.  Files are named: {word}_{volume_pct}_{trial_id}.csv
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load_trial(self, word: str, volume_pct: int, trial_id: int = 0) -> tuple[np.ndarray, np.ndarray]:
        """Return (input_signal, reservoir_states) for one trial.

        Returns
        -------
        signal : (T,) voltage input
        states : (T, 3) baseline-subtracted [intensity, freq, osc]
        """
        raise NotImplementedError(
            "Implement this to parse your photodiode CSV recordings. "
            "See docstring for expected format."
        )

    def list_trials(self) -> list[dict]:
        """List all available trials as [{word, volume_pct, trial_id, path}]."""
        raise NotImplementedError


class LivePlasmaReservoir(Reservoir):
    """Wrap live hardware (audio breakout board + photodiode).

    TODO (Majesti):
        - Serial / ADC interface to read photodiode
        - DAC or audio output to inject voltage into plasma
    """

    def reset(self) -> None:
        raise NotImplementedError

    def step(self, voltage_input: float) -> ReservoirState:
        raise NotImplementedError

    def baseline(self) -> ReservoirState:
        raise NotImplementedError
