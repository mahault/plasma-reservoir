from __future__ import annotations

import numpy as np

from plasma_rc.benchmarks.mackey_glass import mackey_glass
from plasma_rc.benchmarks.narma import narma10


def test_narma10_shapes():
    u, y = narma10(200, seed=1)
    assert u.shape == (200,)
    assert y.shape == (200,)


def test_mackey_glass_shape():
    x = mackey_glass(250)
    assert x.shape == (250,)


def test_narma10_target_from_given_input_matches_generator():
    """The target for a supplied input u (e.g. the drive a reservoir received) is the generator's y."""
    from plasma_rc.benchmarks.narma import narma10_target
    u, y = narma10(300, seed=3)
    np.testing.assert_allclose(narma10_target(u), y)
