"""Decision-rule statistics (VALID-01, research doc §7).

The unit of replication is a trial; trials are clustered by bulb (or bulb × session). Each trial contributes
one paired difference (control metric - lamp metric), so serial dependence inside a trace does not inflate n.
"""
import numpy as np


def holm(pvalues):
    """Holm–Bonferroni adjusted p-values, in input order."""
    p = np.asarray(pvalues, float)
    order = np.argsort(p)
    adj = np.maximum.accumulate((len(p) - np.arange(len(p))) * p[order])
    out = np.empty_like(p)
    out[order] = np.minimum(adj, 1.0)
    return out


def cluster_bootstrap(diffs, clusters, n_boot, seed, level=0.95):
    """Mean of per-cluster mean differences, with a percentile CI from resampling whole clusters."""
    diffs, clusters = np.asarray(diffs, float), np.asarray(clusters)
    means = np.array([diffs[clusters == c].mean() for c in np.unique(clusters)])
    rng = np.random.default_rng(seed)
    boot = means[rng.integers(0, len(means), (n_boot, len(means)))].mean(1)
    lo, hi = np.quantile(boot, [(1 - level) / 2, (1 + level) / 2])
    return {"mean": float(means.mean()), "lo": float(lo), "hi": float(hi), "n_clusters": len(means)}
