"""Storage must preserve evidence and never silently replace an existing trial."""

import csv
import shutil
import numpy as np
import pytest
from plasma_rc.trials.capture import Capture
from plasma_rc.trials.metadata import RunMeta
from plasma_rc.trials.storage import write_trial, load_trial


def capture():
    return Capture(
        np.arange(4),
        np.arange(4, dtype=np.uint16),
        "12",
        np.array([1]),
        np.array([3]),
        1999,
        7,
    )


def meta():
    return RunMeta("B1", "near-breakdown", "none", 22.0, 1.0, 70.0, "test", 0)


def test_drop_evidence_survives_roundtrip(tmp_path):
    p = write_trial(tmp_path, "one", capture(), meta(), {})
    assert load_trial(p).dropped == 7


def test_duplicate_trial_keeps_original(tmp_path):
    p = write_trial(tmp_path, "one", capture(), meta(), {})
    before = p.read_bytes()
    with pytest.raises(FileExistsError):
        write_trial(tmp_path, "one", capture(), meta(), {})
    assert p.read_bytes() == before
    assert len(list(csv.DictReader((tmp_path / "index.csv").open()))) == 1


@pytest.mark.parametrize("name", ["../escape", "/absolute", "sub/name", ""])
def test_trial_name_stays_in_session(tmp_path, name):
    with pytest.raises(ValueError):
        write_trial(tmp_path, name, capture(), meta(), {})


def test_reserved_extra_cannot_replace_metadata(tmp_path):
    with pytest.raises(ValueError):
        write_trial(tmp_path, "one", capture(), meta(), {"clock_hz": 1})


def test_session_paths_are_relative(tmp_path):
    write_trial(tmp_path / "original", "one", capture(), meta(), {})
    shutil.move(tmp_path / "original", tmp_path / "moved")
    row = next(csv.DictReader((tmp_path / "moved/index.csv").open()))
    assert row["raw_file"] == "raw/one.npz"
    assert load_trial(tmp_path / "moved" / row["raw_file"]).dropped == 7


def test_legacy_drop_status_is_unknown(tmp_path):
    p = tmp_path / "old.npz"
    np.savez(
        p,
        ticks=np.arange(4),
        values=np.arange(4),
        channels="12",
        flash_tick=np.array([], dtype=int),
        flash_sub=np.array([], dtype=int),
        ocr1a=1999,
    )
    assert load_trial(p).dropped is None


def test_index_failure_preserves_prior_trial(tmp_path, monkeypatch):
    import plasma_rc.trials.storage as storage

    p = write_trial(tmp_path, "one", capture(), meta(), {})
    before = p.read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(OSError, match="disk full"):
        write_trial(tmp_path, "two", capture(), meta(), {})
    assert p.read_bytes() == before
    assert not (tmp_path / "raw/two.npz").exists()
    assert len(list(csv.DictReader((tmp_path / "index.csv").open()))) == 1


def test_calibration_and_origin_survive_roundtrip(tmp_path):
    import dataclasses

    cap = dataclasses.replace(
        capture(), adc_bits=12, v_ref=3.29, board="teensy41", source="physical"
    )
    out = load_trial(write_trial(tmp_path, "one", cap, meta(), {}))
    assert (out.adc_bits, out.v_ref, out.board, out.source) == (
        12,
        3.29,
        "teensy41",
        "physical",
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"channels": "11"},
        {"clock_hz": 0},
        {"v_ref": -1},
        {"values": np.array([0, 1, 2, 65536])},
        {"flash_sub": np.array([2000])},
    ],
)
def test_invalid_capture_rejected(kwargs):
    import dataclasses

    with pytest.raises(ValueError):
        dataclasses.replace(capture(), **kwargs)
