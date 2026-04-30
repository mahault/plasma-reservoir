"""Digital twin of the plasma reservoir.

Fits a nonlinear model to real experimental data so we can run
large-scale benchmarks without needing the physical bulb.

TODO (Luca / Samuel):
    - Collect enough real trials to fit the GP
    - Validate twin against held-out real data
    - Optionally replace GP with a learned ODE (Neural ODE)
"""
from __future__ import annotations

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel

from .interface import Reservoir, ReservoirState


class PlasmaDigitalTwin(Reservoir):
    """GP-based surrogate of the plasma reservoir.

    Trained on real (voltage_input, state) pairs from the physical system.
    Once fitted, can generate unlimited synthetic reservoir data
    for benchmarking and Bayesian readout training.
    """

    def __init__(self, noise_scale: float = 0.01):
        self.noise_scale = noise_scale
        self._gp: GaussianProcessRegressor | None = None
        self._baseline_state = np.zeros(3)
        self._history: list[float] = []
        self._memory_len = 5  # how many past inputs to condition on

    def fit(self, inputs: np.ndarray, states: np.ndarray) -> None:
        """Fit the digital twin to real experimental data.

        Parameters
        ----------
        inputs : (N,) or (N, memory_len) voltage inputs
        states : (N, 3) baseline-subtracted reservoir states
        """
        kernel = RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)
        self._gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=5)

        # If inputs are 1D, create memory-augmented features
        if inputs.ndim == 1:
            inputs = self._build_memory_features(inputs)
            states = states[self._memory_len:]

        self._gp.fit(inputs, states)

    def reset(self) -> None:
        self._history = []

    def step(self, voltage_input: float) -> ReservoirState:
        if self._gp is None:
            raise RuntimeError("Call fit() with real data before using the twin.")
        self._history.append(voltage_input)
        if len(self._history) < self._memory_len:
            return ReservoirState(0.0, 0.0, 0.0)
        x = np.array(self._history[-self._memory_len:]).reshape(1, -1)
        mean, std = self._gp.predict(x, return_std=True)
        state = mean[0] + np.random.randn(3) * std[0] * self.noise_scale
        return ReservoirState(
            intensity=state[0], frequency=state[1], oscillation=state[2]
        )

    def baseline(self) -> ReservoirState:
        return ReservoirState(0.0, 0.0, 0.0)

    def _build_memory_features(self, signal: np.ndarray) -> np.ndarray:
        n = len(signal) - self._memory_len
        features = np.zeros((n, self._memory_len))
        for i in range(n):
            features[i] = signal[i : i + self._memory_len]
        return features
