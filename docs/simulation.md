# Simulation workflow

This branch contains numerical NE-2 studies and optional ngspice/AVR validation. The [hardware branch](https://github.com/mahault/plasma-reservoir/tree/hardware-pipeline) acquires real trials with the same analysis. Read [mathematics](mathematics.md), [architecture](architecture.md), [review limits](review.md) and [terminology](../GLOSSARY.md).

Install/run from the checkout root:

```bash
python -m pip install -e '.[dev]'
python -m experiments.ne2.s2_sim_reservoir --help
python -m experiments.ne2.s2_sim_reservoir --board teensy41 --out results/study-01
python -m experiments.ne2.s6_sim_narma --session results/study-01/e4
```

The full S2 sweep is lengthy. It uses five seeds per condition and two seeds for its historical dt check. Existing output directories are refused, not deleted. Every synthetic trial records its circuit/profile/seed/substeps. A1/A2 read recorded timing; they do not import current S2 defaults. Numerical core imports require NumPy/SciPy only and do not load serial, soundfile, sounddevice or YAML.

```python
import numpy as np
from plasma_rc.simulation.config import TEENSY41, SimulationSetup, circuit
setup = SimulationSetup(circuit(profile=TEENSY41), TEENSY41, seed=4)
cap = setup.run(np.zeros(20))
print(cap.source, cap.adc_bits, setup.metadata())
```

Profile values and illustrative model values live in `plasma_rc/simulation/config.py`. Changing a profile never mutates another study. Modifying device parameters is an assumed-model experiment, not a measured NE-2 result. The measured module-voltage field remains empty in simulated metadata; equivalent V_th is in the saved circuit setup.

| Module | Study |
|---|---|
| `experiments.ne2.s1_sim_evidence` | Optional ngspice and UNO/simavr checks; requires external tools. |
| `experiments.ne2.s2_sim_reservoir` | Common record-format E4/E6 studies and sweeps. |
| `experiments.ne2.s3_sim_breakdown` | Illustrative ramp and breakdown-delay study. |
| `experiments.ne2.s4_sim_lyapunov` | Finite-time replica contraction diagnostic; historical filename retained. |
| `experiments.ne2.s5_sim_audio` | Optional local speech corpus study. |
| `experiments.ne2.s5_audio_readout` | Speech feature evaluation; inputs are not bundled. |
| `experiments.ne2.s6_sim_narma` | NARMA readout using recorded trial timing. |

S3–S5 save study-specific aggregate outputs rather than claiming a measured trial schema. Setup/profile and seed policy accompany results. Audio input requires a separate local corpus in data/Data, and ffmpeg for MP3; `.[audio]` provides the audio-file dependencies. No corpus, raw results or pickle files are published. Inspect local pickle provenance before loading historical audio results.

Optional validation: install ngspice, arduino-cli with arduino:avr core, gcc and libsimavr development headers/library. Firmware replay uses the checked-out UNO sketch and harness; a wheel alone does not contain firmware sources. Teensy hardware timing is not validated by simavr.

```bash
python -m pytest -q
python docs/figures/linear_response.py
```

The standalone analytical figure includes fixed-seed dt-halving results for five seeds. It exercises a bulb-free limiting case, not the unresolved stochastic discharge law. Historical result charts used the old MC convention and timestamp alignment; they are not republished as corrected results. Re-run the intended study to obtain new scientific numbers. No claim of improved physical task performance is made by this refactor.
