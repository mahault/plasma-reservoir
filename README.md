# NE-2 plasma reservoir · simulation

Apply a known input to a circuit model and study the resulting memory, nonlinearity and task performance. The model produces synthetic samples/events that use the same trial analysis as hardware. It does not establish the behavior of an uncalibrated real bulb.

Read [architecture.md](docs/architecture.md) for the system and equations; [simulation.md](docs/simulation.md) for settings, experiments and outputs. Real acquisition lives on [hardware-pipeline](https://github.com/mahault/plasma-reservoir/tree/hardware-pipeline).

## Install and try

From this checkout, use Python 3.10+ in a dedicated environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

No board, corpus, ngspice or Arduino tools are needed for this short in-memory example:

```python
from plasma_rc.simulation.config import TEENSY41, SimulationSetup, circuit
from plasma_rc.stimuli import xorshift32_levels

setup = SimulationSetup(circuit(profile=TEENSY41), TEENSY41, seed=4)
cap = setup.run(xorshift32_levels(seed=7, n=20))
print(cap.source, cap.board, len(cap.values), len(cap.flash_tick))
```

The input seed and model-noise seed have different roles. Twenty steps are too few for the full capacity procedure.

## Run the study

```bash
python -m experiments.ne2.s2_sim_reservoir --help
python -m experiments.ne2.s2_sim_reservoir --board teensy41 --out results/study-01
python -m experiments.ne2.a1_ipc results/study-01/e4 --out results/study-01/ipc.csv
python -m experiments.ne2.a2_dynamics results/study-01/e6 --out results/study-01/dynamics.csv
python -m experiments.ne2.s6_sim_narma --session results/study-01/e4
```

Choose a **new** output directory. S2 is a lengthy sweep: it compares bulb-removed, switch, delay and delay-with-memory models. It saves `summary.json` and indexed `e4/`, `e6/`, `sweeps/`, `dt/` trials with input, timing, configuration and seeds. S6 writes `results/sim_narma.json` using a chronological held-out prediction segment.

| Further question | Module under `experiments.ne2` | Needs |
|---|---|---|
| Breakdown versus ramp/delay? | `s3_sim_breakdown` | Numerical installation. |
| Finite-time replica contraction? | `s4_sim_lyapunov` | Interpret using the documented diagnostic limits. |
| Speech classification? | `s5_sim_audio`, then `s5_audio_readout` | Compatible local corpus, `.[audio]`, ffmpeg for MP3. |
| Circuit/firmware comparison? | `s1_sim_evidence` | ngspice and/or Arduino/gcc/simavr for the selected checks. |

Run these as `python -m experiments.ne2.<module>`. Datasets are not downloaded. [The simulation guide](docs/simulation.md) gives formats, external-tool requirements and overwrite behavior.

## Check numerics

```bash
python -m pytest -q
python docs/figures/linear_response.py
```

![Analytical response and numerical error at two integration resolutions](docs/figures/linear_response.svg)

External-tool tests skip when unavailable. This figure checks a deterministic linear limit, not unknown discharge physics. Keep seeds, circuit/profile, resolution, features, controls and splits with results. Capacity cutoffs are not confidence intervals; finite-time contraction is not an asymptotic Lyapunov proof. The original `master` preserves the Alejandro/Mahault code.
