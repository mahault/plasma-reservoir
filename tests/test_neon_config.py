"""Basic constraints for the proposed minimal neon circuit."""

import pytest

from plasma_rc.neon.config import StudyConfig


def test_rejects_nonpositive_parasitic_capacitance():
    with pytest.raises(ValueError, match="capacitance"):
        StudyConfig(ballast_ohm=1e6, parasitic_capacitance_f=0)


def test_rejects_nonpositive_ballast_resistance():
    with pytest.raises(ValueError, match="ballast"):
        StudyConfig(ballast_ohm=-1, parasitic_capacitance_f=10e-12)
