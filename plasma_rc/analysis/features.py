"""Time-multiplexed features derived from a trial's recorded step timing."""

import numpy as np
from plasma_rc.characterization.features import step_features


def virtual_node_features(cap, ticks_per_step, n_steps, k=4):
    if k < 1 or ticks_per_step % k:
        raise ValueError("virtual nodes must divide ticks_per_step")
    x = step_features(cap, ticks_per_step // k, n_steps * k, analog=("1", "3"))[:, :2]
    return np.column_stack(
        [x.reshape(n_steps, 2 * k), step_features(cap, ticks_per_step, n_steps)[:, 3]]
    )
