from __future__ import annotations

import numpy as np

from plasma_rc.reservoir.digital_twin import PlasmaDigitalTwin


def test_digital_twin_fit_and_step():
    rng = np.random.RandomState(7)
    inputs = rng.randn(200)
    states = np.column_stack(
        [
            0.5 * inputs + 0.1 * rng.randn(200),
            -0.3 * inputs + 0.1 * rng.randn(200),
            np.sin(inputs) + 0.05 * rng.randn(200),
        ]
    )
    twin = PlasmaDigitalTwin(noise_scale=0.0)
    twin.fit(inputs, states)
    twin.reset()
    for i in range(6):
        out = twin.step(float(inputs[i]))
    assert out.as_array().shape == (3,)


def test_seeded_predictions_are_reproducible():
    u = np.random.default_rng(8).normal(size=30)
    y = np.column_stack([u,u**2,np.sin(u)])
    a,b = PlasmaDigitalTwin(seed=4),PlasmaDigitalTwin(seed=4)
    a.fit(u,y)
    b.fit(u,y)
    np.testing.assert_array_equal(a.drive(u),b.drive(u))
