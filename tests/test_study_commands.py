"""Study output survives a fresh checkout; real task serialization must work."""

import json
import pickle
import pytest


class SerializedEmptyPool:
    """Replace expensive workers while retaining their real serialization requirement."""

    def __init__(self, *args):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def map(self, fn, items):
        for item in items:
            pickle.dumps((fn, item))
        return []


@pytest.mark.parametrize(
    "module,filename",
    [
        ("s3_sim_breakdown", "sim_breakdown.json"),
        ("s4_sim_lyapunov", "sim_lyapunov.json"),
    ],
)
def test_study_publishes_serializable_jobs_to_fresh_directory(
    tmp_path, monkeypatch, module, filename
):
    from importlib import import_module

    study = import_module("experiments.ne2." + module)
    out = tmp_path / "new" / "results"
    monkeypatch.setattr(study, "RESULTS", out)
    monkeypatch.setattr(study, "Pool", SerializedEmptyPool)
    study.main()
    result = json.loads((out / filename).read_text())
    assert result["setup"]["acquisition"]["board"] == "teensy41"
