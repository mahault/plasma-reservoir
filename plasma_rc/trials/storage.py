"""Versioned NPZ/CSV storage. Single writer; each file publishes atomically."""

import csv
import json
import os
import re
import tempfile
from dataclasses import asdict
from pathlib import Path
import numpy as np
from .capture import Capture
from .metadata import RunMeta

SCHEMA_VERSION = 1
FIELDS = tuple(Capture.__dataclass_fields__)
RESERVED = (
    set(FIELDS)
    | set(RunMeta.__dataclass_fields__)
    | {"schema_version", "name", "raw_file", "n_samples", "n_flashes", "tick_hz"}
)


def _temp(directory):
    return tempfile.NamedTemporaryFile(dir=directory, prefix=".trial-", delete=False)


def write_trial(session, name, cap, meta, extra):
    session = Path(session)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.=,+-]*", name):
        raise ValueError("invalid trial name")
    if RESERVED.intersection(extra):
        raise ValueError("extra contains reserved metadata keys")
    cap.__post_init__()
    raw = session / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    path, index = raw / f"{name}.npz", session / "index.csv"
    with (
        index.open(newline="") if index.exists() else __import__("io").StringIO() as fh
    ):
        rows = list(csv.DictReader(fh))
    if path.exists() or any(r["name"] == name for r in rows):
        raise FileExistsError(f"duplicate trial: {name}")
    payload = {
        k: getattr(cap, k) if getattr(cap, k) is not None else "" for k in FIELDS
    }
    payload.update(schema_version=SCHEMA_VERSION)
    payload.update(
        {k: json.dumps(v) if isinstance(v, dict) else v for k, v in extra.items()}
    )
    if any(np.asarray(v).dtype.hasobject for v in payload.values()):
        raise ValueError("trial data cannot contain pickled objects")
    row = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "raw_file": f"raw/{name}.npz",
        **asdict(meta),
        "tick_hz": cap.tick_hz,
        "n_samples": len(cap.values),
        "n_flashes": len(cap.flash_tick),
        **{
            k: getattr(cap, k)
            for k in ("dropped", "adc_bits", "v_ref", "board", "source")
        },
        **{
            k: json.dumps(v) if isinstance(v, dict) else v
            for k, v in extra.items()
            if not isinstance(v, np.ndarray)
        },
    }
    fields = list(dict.fromkeys([*(rows[0] if rows else []), *row]))
    a, b = _temp(raw), _temp(session)
    published = False
    try:
        with a:
            np.savez(a, **payload)
        with open(b.name, "w", newline="", encoding="utf8") as fh:
            writer = csv.DictWriter(fh, fields)
            writer.writeheader()
            writer.writerows([*rows, row])
        b.close()
        os.link(a.name, path)  # exclusive publication; a duplicate never replaces data
        published = True
        os.replace(b.name, index)
    except BaseException:
        if published:
            path.unlink(missing_ok=True)
        raise
    finally:
        a.close()
        b.close()
        Path(a.name).unlink(missing_ok=True)
        Path(b.name).unlink(missing_ok=True)
    return path


def load_trial(path):
    with np.load(path, allow_pickle=False) as d:
        version = int(d["schema_version"]) if "schema_version" in d else 0
        if version not in (0, SCHEMA_VERSION):
            raise ValueError(f"unsupported trial schema {version}")
        required = FIELDS if version else FIELDS[:6]
        if set(required) - set(d.files):
            raise ValueError("incomplete trial record")

        def optional(k, cast, default=None):
            return cast(d[k].item()) if k in d and str(d[k].item()) != "" else default

        return Capture(
            ticks=d["ticks"],
            values=d["values"],
            channels=str(d["channels"]),
            flash_tick=d["flash_tick"],
            flash_sub=d["flash_sub"],
            ocr1a=int(d["ocr1a"]),
            dropped=optional("dropped", int),
            clock_hz=optional("clock_hz", float, 16e6),
            adc_bits=optional("adc_bits", int),
            v_ref=optional("v_ref", float),
            board=optional("board", str, "unknown"),
            source=optional("source", str, "unknown"),
        )


def trials(sessions, kind):
    rows = []
    for session in map(Path, sessions):
        with (session / "index.csv").open(newline="") as fh:
            all_rows = list(csv.DictReader(fh))
        seen = set()
        for r in all_rows:
            if r["name"] in seen:
                raise ValueError("duplicate trial in session index")
            seen.add(r["name"])
            raw = Path(r["raw_file"])
            if not r.get("schema_version"):
                raw = session / "raw" / raw.name
            elif not raw.is_absolute():
                raw = session / raw
            if not raw.exists():
                raise ValueError(f"missing raw trial: {raw}")
            if r.get("kind") == kind:
                rows.append({**r, "raw_file": str(raw.resolve())})
        indexed = {Path(r["raw_file"]).name for r in all_rows}
        if {f.name for f in (session / "raw").glob("*.npz")} - indexed:
            raise ValueError("unindexed raw trial in session")
    return rows
