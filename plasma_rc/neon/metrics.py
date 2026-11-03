"""Error metric for benchmark evaluation."""
import numpy as np


def nmse(y_true, y_pred):
    """Mean squared prediction error divided by the target variance."""
    variance = np.var(y_true)
    return float(np.mean((y_true - y_pred) ** 2) / variance) if variance > 0 else float("inf")
