"""The N-A surrogate (NULL-01): what the measured circuit would read with a no-afterglow hysteretic lamp.

Expected surrogate state = mean over k independent i.i.d. strike-delay realizations, read out exactly like the
lamp (plasma_rc.states). A single realization is noisy enough to fake an attribution gain (Δ = 0.35 for a
1 nF control in the study); averaging reduces Monte Carlo noise but does not calibrate attribution or eliminate model mismatch. Sensor poles from E0 are not yet included (before E5).
"""
import numpy as np

from plasma_rc.sim import iid_delay, simulate
from plasma_rc.states import FINE, sim_states


def surrogate_states(cfg, x, t_step, m, seed, k=6, t_f=None, t_s=None):
    """Mean N-A states (n_steps, 2m) for drive x[k] in [0, 1] held for t_step; realization i uses seed + i.
    t_f, t_s default to the config's lamp values."""
    delay = iid_delay(cfg.get("lamp", "t_f") if t_f is None else t_f, cfg.get("lamp", "t_s") if t_s is None else t_s)
    return np.mean([sim_states(simulate(cfg, x, t_step, m * FINE, delay, seed + i), m) for i in range(k)], axis=0)
