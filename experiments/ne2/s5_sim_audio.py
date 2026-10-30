"""S5: words, spoken digits, noise and silence through the simulated circuit (E5 in simulation).

Every file under data/Data (audio_tree: FSDD, own words at 3 volumes, 3 different words, silence,
noise, consistency repeats) is encoded three ways (plasma_rc.encoding: raw, envelope, masked),
played into circuit A by the Teensy 4.1 PWM-DAC (±1.65 V) and recorded as on the bench. Per utterance
the readout state is averaged in K_BINS equal time bins: light (A1) and node voltage (A3) per frame
(masked: per virtual node) and flashes per frame. Circuits: "bulb" = S2 base model in the audio
configuration (J_C out: C = 100 pF, bulb + wiring, Unknown; rest 0.25 V below V_b), "linear" (same,
bulb removed: the resistor/RC control), "input" (the same binning applied to the drive itself: mean u
and mean u^2, the transducer control of PROTOCOL §4); on the own recordings only, "bulb_design"
(S2 circuit as designed, C = 10 nF: a 16 Hz node that speech cannot fire) and "bulb_dt" (dt halved).
5 noise seeds. Scaling: one constant
per corpus and encoding (FSDD; own recordings), so relative volume is kept.
Output: results/sim_audio/<condition>_<encoding>_<circuit>.npz, read by s5_audio_readout.py.
"""

from __future__ import annotations

import pickle
import time
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from experiments.ne2.common import RESULTS
from plasma_rc.simulation.config import PROFILES, CONDITIONS, circuit

from plasma_rc.acquisition.audio_tree import list_trials
from plasma_rc.bulb_model import simulate
from plasma_rc.characterization.features import step_features
from plasma_rc.encoding import (
    band_rms,
    binary_mask,
    frame_rms,
    load_audio,
    masked_drive,
    to_ticks,
)

AUDIO_ROOT = Path("data/Data")
B = PROFILES["teensy41"]
TICK_HZ = B.clock_hz / (B.ocr1a + 1)
FRAME = round(0.01 * TICK_HZ)  # 10 ms frame = 240 ticks
N_VIRTUAL, N_BANDS, K_BINS, SEEDS = (
    8,
    8,
    8,
    5,
)  # masked: theta = 1.25 ms < node time constant ~10 ms
PRE_S, POST_S = 0.05, 0.1
ENCODINGS = {
    "raw": 1,
    "envelope": FRAME,
    "masked": FRAME // N_VIRTUAL,
}  # ticks per drive value
AUDIO = dict(C=0.1e-9, margin=0.25)
CIRCUITS = {  # name: (circuit overrides, oversample, corpora)
    "bulb": ({**CONDITIONS["delay+memory"], **AUDIO}, B.oversample, ("fsdd", "own")),
    "linear": ({**CONDITIONS["linear"], **AUDIO}, B.oversample, ("fsdd", "own")),
    "bulb_design": (CONDITIONS["delay+memory"], B.oversample, ("own",)),
    "bulb_dt": ({**CONDITIONS["delay+memory"], **AUDIO}, 2 * B.oversample, ("own",)),
}
MASK = binary_mask(N_VIRTUAL, N_BANDS, seed=0)


def corpus(meta) -> str:
    return "fsdd" if meta.condition == "fsdd" else "own"


def unscaled(path, encoding: str) -> np.ndarray:
    """Drive values before the per-corpus scale."""
    x, fs = load_audio(path)
    if encoding == "raw":
        return to_ticks(x, fs, TICK_HZ)
    if encoding == "envelope":
        return frame_rms(x, fs, FRAME / TICK_HZ)
    return masked_drive(band_rms(x, fs, FRAME / TICK_HZ, N_BANDS), MASK)


def peak(args) -> tuple:
    path, meta, enc = args
    return corpus(meta), enc, float(np.abs(unscaled(path, enc)).max())


def binned(a: np.ndarray) -> np.ndarray:
    return np.stack([b.mean(0) for b in np.array_split(a, K_BINS)])


def job(args) -> tuple:
    """One utterance through one circuit: binned features (+ per-frame traces for consistency)."""
    idx, path, meta, enc, scale, circ, seed = args
    tps = ENCODINGS[enc]
    pad = lambda s: np.zeros(round(s * TICK_HZ / tps))  # noqa: E731  silence = DAC mid-scale
    u = np.concatenate([pad(PRE_S), unscaled(path, enc) / scale, pad(POST_S)])
    n_frames = len(u) * tps // FRAME
    sub = N_VIRTUAL if enc == "masked" else 1
    if circ == "input":
        per = (
            np.repeat(u, tps)[: n_frames * FRAME]
            .reshape(n_frames, sub, FRAME // sub)
            .mean(2)
        )
        sq = (
            (np.repeat(u, tps)[: n_frames * FRAME] ** 2)
            .reshape(n_frames, sub, FRAME // sub)
            .mean(2)
        )
        feats = {"u": per, "u2": sq}
    else:
        over, oversample, _ = CIRCUITS[circ]
        cap = simulate(
            circuit(profile=B, **over),
            u,
            tps,
            B.ocr1a,
            np.random.default_rng([seed, idx]),
            oversample,
            clock_hz=B.clock_hz,
        )
        x = step_features(cap, FRAME // sub, n_frames * sub, analog=("1", "3"))[
            :, :2
        ].reshape(n_frames, sub, 2)
        flash = step_features(cap, FRAME, n_frames, analog=("3",))[:, 1:2]
        feats = {"light": x[:, :, 0], "v": x[:, :, 1], "flash": flash}
    out = {k: binned(v) for k, v in feats.items()}
    if meta.condition == "consistency":
        out.update({f"frames_{k}": v for k, v in feats.items()})
    return (meta.condition, enc, circ), seed, meta, out


def main() -> None:
    trials = list_trials(AUDIO_ROOT)
    t0 = time.time()
    with Pool(20) as pool:
        scale = {}
        for c, enc, pk in pool.imap_unordered(
            peak, [(p, m, e) for p, m in trials for e in ENCODINGS], chunksize=50
        ):
            scale[c, enc] = max(scale.get((c, enc), 0.0), pk)
        print("scales", scale, f"{time.time() - t0:.0f} s", flush=True)
        runs = [(c, SEEDS, cor) for c, (_, _, cor) in CIRCUITS.items()] + [
            ("input", 1, ("fsdd", "own"))
        ]
        jobs = [
            (i, p, m, e, scale[corpus(m), e], c, s)
            for i, (p, m) in enumerate(trials)
            for e in ENCODINGS
            for c, seeds, cor in runs
            if corpus(m) in cor
            for s in range(seeds)
        ]
        groups = defaultdict(list)
        for n, (key, seed, meta, feats) in enumerate(
            pool.imap_unordered(job, jobs, chunksize=8)
        ):
            groups[key].append((seed, meta, feats))
            if n % 5000 == 0:
                print(f"{n}/{len(jobs)} {time.time() - t0:.0f} s", flush=True)
    out = RESULTS / "sim_audio"
    out.mkdir(parents=True, exist_ok=True)
    (out / "groups.pkl").write_bytes(
        pickle.dumps((dict(groups), scale))
    )  # raw results, before any reshaping
    write(groups, scale, out, t0)


def stack(arrays: list) -> np.ndarray:
    """Binned features stack; per-frame traces (consistency) differ in length and stay a list."""
    if len({a.shape for a in arrays}) == 1:
        return np.stack(arrays)
    obj = np.empty(len(arrays), dtype=object)
    obj[:] = arrays
    return obj


def write(groups, scale, out, t0) -> None:
    for (cond, enc, circ), rows in groups.items():
        rows.sort(key=lambda r: (r[0], r[1].source_file))
        arrays = {k: stack([r[2][k] for r in rows]) for k in rows[0][2]}
        meta = {
            f: np.array([getattr(r[1], f) for r in rows])
            for f in ("label", "speaker", "sample_index", "stem")
        }
        np.savez(
            out / f"{cond}_{enc}_{circ}.npz",
            seed=np.array([r[0] for r in rows]),
            **meta,
            **arrays,
            scale=scale["fsdd" if cond == "fsdd" else "own", enc],
            tick_hz=TICK_HZ,
            frame_ticks=FRAME,
            n_virtual=N_VIRTUAL,
            k_bins=K_BINS,
            provenance=__import__("json").dumps(
                {
                    "acquisition": __import__("dataclasses").asdict(B),
                    "circuits": {
                        n: __import__("dataclasses").asdict(circuit(profile=B, **o))
                        for n, (o, _, _) in CIRCUITS.items()
                    },
                    "seed_policy": "default_rng([seed, trial_index]); five seeds",
                    "integration_substeps": {
                        n: os for n, (_, os, _) in CIRCUITS.items()
                    },
                }
            ),
        )
    print(f"wrote {len(groups)} files to {out} in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
