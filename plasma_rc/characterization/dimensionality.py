"""Effective dimensionality analysis.

TODO (Luca):
    - PCA on reservoir states to measure exploited dimensions
    - Compare intrinsic dimensionality (plasma) vs engineered (Hopf virtual nodes)
"""
from __future__ import annotations

import numpy as np
from sklearn.decomposition import PCA


def effective_dimensionality(
    reservoir_states: np.ndarray, threshold: float = 0.95
) -> tuple[int, np.ndarray]:
    """Number of PCA components explaining `threshold` fraction of variance.

    Parameters
    ----------
    reservoir_states : (T, D) state matrix
    threshold : cumulative variance threshold

    Returns
    -------
    n_dims : effective dimensionality
    explained : cumulative explained variance ratio
    """
    pca = PCA()
    pca.fit(reservoir_states)
    cumvar = np.cumsum(pca.explained_variance_ratio_)
    n_dims = int(np.searchsorted(cumvar, threshold)) + 1
    return n_dims, cumvar
