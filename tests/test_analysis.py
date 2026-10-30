"""Same stored records have the same analysis, independent of producer and location."""

import dataclasses
import shutil
import numpy as np
import pytest
from plasma_rc.trials.capture import Capture
from plasma_rc.trials.metadata import RunMeta
from plasma_rc.trials.storage import write_trial, trials


def record(session, source="physical"):
    u = np.random.default_rng(0).uniform(-1, 1, 500)
    levels = np.rint((u + 1) * 127.5).astype(np.uint8)
    ticks = np.arange(500 * 6)
    values = np.rint(512 + 200 * u[ticks // 6]).astype(np.uint16)
    cap = Capture(
        ticks,
        values,
        "123",
        np.array([], dtype=int),
        np.array([], dtype=int),
        1999,
        0,
        source=source,
    )
    meta = RunMeta("B1", "near-breakdown", "none", 22, 1, 70, "test", 0)
    write_trial(
        session,
        "one",
        cap,
        meta,
        {"kind": "ipc", "ticks_per_step": 6, "levels": levels, "n_steps": 500},
    )


def test_identical_producers_and_relocated_records(tmp_path):
    from plasma_rc.analysis.ipc import analyse

    record(tmp_path / "hardware")
    record(tmp_path / "synthetic", "simulation")
    a = analyse(trials([tmp_path / "hardware"], "ipc")[0], 3, 1)
    b = analyse(trials([tmp_path / "synthetic"], "ipc")[0], 3, 1)
    shutil.move(tmp_path / "synthetic", tmp_path / "moved")
    c = analyse(trials([tmp_path / "moved"], "ipc")[0], 3, 1)
    assert a == b == c
    assert a["instantaneous_linear"] > 0.95 and a["mc"] < 0.05


def test_replica_analysis_rejects_insufficient_repeats():
    from plasma_rc.analysis.dynamics import analyse

    with pytest.raises(ValueError, match="at least two"):
        analyse([], [], None)


def test_legacy_requires_explicit_opt_in(tmp_path):
    from plasma_rc.analysis.ipc import analyse

    record(tmp_path)
    row = trials([tmp_path], "ipc")[0]
    path = row["raw_file"]
    with np.load(path) as d:
        payload = {
            k: d[k]
            for k in d.files
            if k
            not in ("schema_version", "dropped", "adc_bits", "v_ref", "source", "board")
        }
    np.savez(path, **payload)
    with pytest.raises(ValueError, match="legacy"):
        analyse(row, 3, 1)
    assert analyse(row, 3, 1, allow_legacy=True)["instantaneous_linear"] > 0.95


def test_unindexed_file_is_detected(tmp_path):
    record(tmp_path)
    (tmp_path / "raw/orphan.npz").write_bytes(b"partial")
    with pytest.raises(ValueError, match="unindexed"):
        trials([tmp_path], "ipc")


@pytest.mark.parametrize("change", ["stimulus", "control", "source"])
def test_replicas_reject_incompatible_drive_or_provenance(tmp_path, change):
    from plasma_rc.analysis.dynamics import analyse

    record(tmp_path / "a")
    record(tmp_path / "b")
    a = {**trials([tmp_path / "a"], "ipc")[0], "n_prefix": "0"}
    b = {**trials([tmp_path / "b"], "ipc")[0], "n_prefix": "0"}
    if change == "control":
        b["control"] = "resistor"
    else:
        with np.load(b["raw_file"]) as d:
            payload = {k: d[k] for k in d.files}
        if change == "stimulus":
            payload["levels"] = np.roll(payload["levels"], 1)
        else:
            payload["source"] = "simulation"
        np.savez(b["raw_file"], **payload)
    with pytest.raises(ValueError, match="drive|condition|provenance"):
        analyse([a, b], [a, a], None)
