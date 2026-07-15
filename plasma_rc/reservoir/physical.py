"""Physical plasma reservoir — data loader for real experimental recordings.

TODO (Majesti / Samuel):
    - Implement the Reservoir interface to wrap live hardware
    - Define the voltage encoding for audio→plasma injection
    - Recordings currently have no logged input signal (no voltage_in
      column) and no same-session baseline, so memory_capacity() and
      baseline subtraction can't be run yet — see ROADMAP Step 1.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .interface import Reservoir, ReservoirState


class PlasmaDataLoader:
    """Load pre-recorded plasma trials from disk.

    Actual CSV format (as delivered):
        Timestamp_Seconds, Brightness, Frequency_Hz, Settle_Micros

    One file per recording, e.g. plasma_data_apple_m.csv.  There is no
    voltage_in column and no word/volume_pct/trial_id encoded in the
    filename — each file is a single continuous session, not a
    discrete labeled trial.
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load_trial(self, filename: str) -> tuple[np.ndarray, np.ndarray]:
        """Return (timestamps, states) for one recording.

        Returns
        -------
        timestamps : (T,) seconds
        states : (T, 3) raw [brightness, frequency_hz, settle_micros],
            NOT baseline-subtracted (no same-session baseline exists
            for this dataset yet).
        """
        path = self.data_dir / filename
        data = np.genfromtxt(path, delimiter=",", names=True)
        timestamps = data["Timestamp_Seconds"]
        states = np.column_stack(
            [data["Brightness"], data["Frequency_Hz"], data["Settle_Micros"]]
        )
        return timestamps, states

    def list_trials(self) -> list[dict]:
        """List all available recordings as [{name, path}]."""
        return [
            {"name": p.stem, "path": p}
            for p in sorted(self.data_dir.glob("*.csv"))
        ]


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
