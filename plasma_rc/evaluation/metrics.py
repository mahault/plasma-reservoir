"""Evaluation metrics for reservoir computing benchmarks."""
from __future__ import annotations

import numpy as np


def nmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Normalized mean squared error: MSE / Var(y_true)."""
    mse = np.mean((y_true - y_pred) ** 2)
    var = np.var(y_true)
    return float(mse / var) if var > 0 else float("inf")


def cod(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Coefficient of determination: 1 - NMSE."""
    return 1.0 - nmse(y_true, y_pred)


def classification_accuracy(
    y_true: np.ndarray, y_pred: np.ndarray
) -> float:
    """Fraction of correct classifications."""
    return float(np.mean(y_true == y_pred))


def calibration_error(
    y_true: np.ndarray,
    y_mean: np.ndarray,
    y_std: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Expected calibration error for Bayesian predictions.

    For each confidence bin, checks whether the observed frequency
    of y_true falling within the predicted interval matches the
    nominal coverage.
    """
    coverages = np.linspace(0.1, 0.99, n_bins)
    errors = []
    for p in coverages:
        from scipy.stats import norm
        z = norm.ppf(0.5 + p / 2)
        lo = y_mean - z * y_std
        hi = y_mean + z * y_std
        observed = np.mean((y_true >= lo) & (y_true <= hi))
        errors.append(abs(observed - p))
    return float(np.mean(errors))
