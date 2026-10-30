"""Published commands must use the real loader contract and known input data."""

import numpy as np
import pytest


def test_legacy_summary_does_not_invent_input_signal(tmp_path):
    from experiments.run_benchmarks import maybe_physical_summary

    (tmp_path / "old.csv").write_text(
        "Timestamp_Seconds,Brightness,Frequency_Hz,Settle_Micros\n0,1,2,3\n1,2,3,4\n"
    )
    assert maybe_physical_summary(str(tmp_path)) == {"recordings": 1, "samples": 2}


def test_twin_validation_requires_logged_inputs(tmp_path):
    from experiments.validate_digital_twin import run_validation

    for name in ("a", "b"):
        (tmp_path / f"{name}.csv").write_text(
            "Timestamp_Seconds,Brightness,Frequency_Hz,Settle_Micros\n0,1,2,3\n1,2,3,4\n"
        )
    with pytest.raises(ValueError, match="logged inputs"):
        run_validation(str(tmp_path), 0.3, 1.2)
