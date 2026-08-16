from __future__ import annotations

from plasma_rc.benchmarks.mackey_glass import mackey_glass
from plasma_rc.benchmarks.narma import narma10


def test_narma10_shapes():
    u, y = narma10(200, seed=1)
    assert u.shape == (200,)
    assert y.shape == (200,)


def test_mackey_glass_shape():
    x = mackey_glass(250)
    assert x.shape == (250,)
