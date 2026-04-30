"""Abstract reservoir interface.

Any physical or simulated reservoir must implement this interface
so that characterization, benchmarks, and readout layers are
interchangeable across substrates (plasma, echo state, Hopf, etc.).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

import numpy as np


@dataclass
class ReservoirState:
    """Single-timestep readout from the reservoir."""
    intensity: float
    frequency: float
    oscillation: float
    timestamp: float = 0.0

    def as_array(self) -> np.ndarray:
        return np.array([self.intensity, self.frequency, self.oscillation])


class Reservoir(abc.ABC):
    """Abstract base for any reservoir substrate."""

    @abc.abstractmethod
    def reset(self) -> None:
        """Reset reservoir to baseline / resting state."""

    @abc.abstractmethod
    def step(self, voltage_input: float) -> ReservoirState:
        """Inject one voltage sample, return the state readout."""

    @abc.abstractmethod
    def baseline(self) -> ReservoirState:
        """Return the current baseline (no-input) state."""

    def drive(self, signal: np.ndarray) -> np.ndarray:
        """Drive the reservoir with a full signal, return (T, 3) state matrix.

        Subtracts baseline automatically.
        """
        self.reset()
        base = self.baseline().as_array()
        states = []
        for v in signal:
            s = self.step(float(v)).as_array()
            states.append(s - base)
        return np.array(states)
