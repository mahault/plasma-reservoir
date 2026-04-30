"""Standard linear readout — baseline for comparison with BayesNet readout."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import Ridge, BayesianRidge


@dataclass
class ReadoutResult:
    mean: np.ndarray          # (N,) point predictions
    std: np.ndarray | None    # (N,) uncertainty (None for plain Ridge)
    weights: np.ndarray       # (D,) learned weights


class LinearReadout:
    """Standard single-layer linear readout (RC baseline)."""

    def __init__(self, bayesian: bool = False, alpha: float = 1e-6):
        self.bayesian = bayesian
        self._alpha = alpha
        self._model: Ridge | BayesianRidge | None = None

    def fit(self, states: np.ndarray, targets: np.ndarray) -> None:
        if self.bayesian:
            self._model = BayesianRidge()
        else:
            self._model = Ridge(alpha=self._alpha)
        self._model.fit(states, targets)

    def predict(self, states: np.ndarray) -> ReadoutResult:
        if self._model is None:
            raise RuntimeError("Call fit() first.")
        if self.bayesian:
            mean, std = self._model.predict(states, return_std=True)
        else:
            mean = self._model.predict(states)
            std = None
        return ReadoutResult(
            mean=mean, std=std, weights=self._model.coef_
        )
