"""S5 readout: classify the simulated audio states (s5_sim_audio.py) and measure consistency.

Same linear readout for every feature set: standardise, then a ridge classifier whose penalty is
chosen by efficient leave-one-out CV on the training data only (sklearn RidgeClassifierCV).
Tasks: FSDD digits (official split: recordings 0-4 of each speaker/digit are the test set, FSDD
README), own words apple/banana/orange, the volume of one word (50/75/100), word vs noise vs
silence (5-fold stratified CV, fixed folds). Feature sets compare the bulb with the bulb-removed
circuit and with the input alone (linear: mean u; energy: mean u^2), the PROTOCOL §4 test.
Consistency: mean pairwise correlation of per-frame node voltage across 10 identical repeats
(Uchida et al. 2008), per noise seed. Accuracy: mean ± std over the 5 noise seeds.
"""

from __future__ import annotations

import json

import numpy as np
from experiments.ne2.common import RESULTS
from sklearn.linear_model import RidgeClassifierCV
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from plasma_rc.characterization.consistency import pairwise_consistency

DIR = RESULTS / "sim_audio"
SETS = {  # name: (circuit file, feature keys)
    "bulb: light + v + flashes": ("bulb", ("light", "v", "flash")),
    "bulb: v only": ("bulb", ("v",)),
    "bulb: flashes only": ("bulb", ("flash",)),
    "bulb removed (linear RC)": ("linear", ("light", "v", "flash")),
    "input only, linear (mean u)": ("input", ("u",)),
    "input only, energy (mean u^2)": ("input", ("u2",)),
    "bulb as designed (C 10 nF)": ("bulb_design", ("light", "v", "flash")),
    "bulb, dt halved": ("bulb_dt", ("light", "v", "flash")),
}
ENCODINGS = ("raw", "envelope", "masked")


def load(cond: str, enc: str, circ: str) -> dict | None:
    path = DIR / f"{cond}_{enc}_{circ}.npz"
    if not path.exists():
        return None
    with np.load(path, allow_pickle=True) as d:
        return {k: d[k] for k in d.files}


def features(d: dict, keys) -> np.ndarray:
    return np.concatenate([d[k].reshape(len(d[k]), -1) for k in keys], axis=1)


def readout():
    return make_pipeline(
        StandardScaler(), RidgeClassifierCV(alphas=np.logspace(-3, 3, 13))
    )


def accuracy(x, y, test=None) -> float:
    """Test accuracy on a fixed split, or the mean over fixed 5 stratified folds."""
    if test is not None:
        return float(readout().fit(x[~test], y[~test]).score(x[test], y[test]))
    folds = StratifiedKFold(5, shuffle=True, random_state=0).split(x, y)
    return float(
        np.mean([readout().fit(x[a], y[a]).score(x[b], y[b]) for a, b in folds])
    )


def task_data(task: str, enc: str, circ: str, keys):
    """Per seed: (x, y, test mask or None)."""
    if task == "wns":
        parts = [load(c, enc, circ) for c in ("silence", "noise", "different_word")]
        if None in parts:
            return []
        w = parts[2]
        pick = (w["speaker"] == "sami") & (
            w["sample_index"] <= 5
        )  # 5 per word: 15, as silence and noise
        parts[2] = {
            k: (v[pick] if np.ndim(v) and len(v) == len(pick) else v)
            for k, v in w.items()
        }
        parts[2]["label"] = np.full(pick.sum(), "word")
    else:
        d = load(
            {"fsdd": "fsdd", "words": "different_word", "volume": "same_word"}[task],
            enc,
            circ,
        )
        if d is None:
            return []
        parts = [d]
    out = []
    for s in np.unique(parts[0]["seed"]):
        sel = [p["seed"] == s for p in parts]
        x = np.concatenate(
            [features({k: p[k][m] for k in keys}, keys) for p, m in zip(parts, sel)]
        )
        y = np.concatenate([p["label"][m] for p, m in zip(parts, sel)])
        test = (parts[0]["sample_index"][sel[0]] <= 4) if task == "fsdd" else None
        out.append((x, y, test))
    return out


def consistency(enc: str, circ: str) -> dict:
    d = load("consistency", enc, circ)
    if d is None:
        return {}
    out = {}
    for label in np.unique(d["label"]):
        per_seed = []
        for s in np.unique(d["seed"]):
            m = (d["label"] == label) & (d["seed"] == s)
            traces = np.stack([np.asarray(t, float).ravel() for t in d["frames_v"][m]])
            per_seed.append(pairwise_consistency(traces))
        out[str(label)] = [float(np.mean(per_seed)), float(np.std(per_seed))]
    return out


def main() -> None:
    out = {"accuracy": {}, "chance": {}, "consistency_v": {}, "flashes_per_s": {}}
    for task in ("fsdd", "words", "volume", "wns"):
        for enc in ENCODINGS:
            for name, (circ, keys) in SETS.items():
                rows = task_data(task, enc, circ, keys)
                if not rows:
                    continue
                acc = [accuracy(*r) for r in rows]
                out["accuracy"][f"{task} | {enc} | {name}"] = [
                    float(np.mean(acc)),
                    float(np.std(acc)),
                ]
                out["chance"][task] = 1 / len(np.unique(rows[0][1]))
                print(
                    task,
                    enc,
                    name,
                    f"{np.mean(acc):.3f} ± {np.std(acc):.3f}",
                    flush=True,
                )
    for enc in ENCODINGS:
        for circ in ("bulb", "linear", "bulb_design"):
            out["consistency_v"][f"{enc} | {circ}"] = consistency(enc, circ)
            for cond in ("fsdd", "same_word", "different_word", "noise", "silence"):
                d = load(cond, enc, circ)
                if (
                    d is not None
                ):  # flash features: mean flashes per 10 ms frame in each bin
                    n = 100 * d["flash"].mean(axis=(1, 2))
                    out["flashes_per_s"][f"{cond} | {enc} | {circ}"] = [
                        float(n.mean()),
                        float(n.std()),
                    ]
                    if cond == "same_word":
                        for vol in ("50", "75", "100"):
                            m = d["label"] == vol
                            out["flashes_per_s"][
                                f"same_word {vol} | {enc} | {circ}"
                            ] = float(n[m].mean())
    (RESULTS / "sim_audio_readout.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
