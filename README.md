# Neon reservoir

This branch unifies simulation and physical acquisition for a single neon bulb reservoir studied with NARMA-10.

## Simulation

The simulation pipeline uses ngspice to model candidate circuits. It generates NARMA-10, optical-proxy, correlation, truncated IPC and ballast-pulse results. It does not control hardware or establish real bulb performance.

```bash
pip install -e ".[dev]"
# install ngspice
python -m pytest -q
python -m experiments.neon results/experiment-001 --steps 900 --seeds 5
```

Read [simulation experiments](docs/sim_experiments.md), [circuit and mathematics](docs/system_guide.md), [decisions](docs/DECISIONS.md) and [research](docs/research/README.md). The light proxy, lamp parameters and LED model are hypotheses, not physical measurements or construction ratings.

For an explicitly hypothetical NE-2H-labeled NARMA-10 parameter search (validation NMSE selection, IPC, a bounded RC-branch contraction diagnostic, figures and a generated report), run `python -m experiments.neon_ne2h results/neon/experiment-YYYYMMDD-ne2h-narma`. It is not physical calibration or a hardware experiment.

To rank explicitly chosen electrical model parameters against a measured trace, see the [calibration instructions](plasma_rc/neon/README.md) and the [NE-2H evidence note](docs/research/ne2h_model_parameters.md). A grid fit is not physical validation; use a separate held-out measurement.

## Physical acquisition

The acquisition pipeline records and analyzes a single neon bulb or a separately driven LED for NARMA-10 using a Teensy 4.1 board. The code and firmware have not been verified with the physical driver, photodiode or bulb. Voltage and current limits recorded by software are metadata, not protection or interlocks. The LED must use its own suitable low-voltage supply and current limiter.

```bash
pip install -e ".[dev,acquisition]"
python -m pytest -q
python -m experiments.neon_acquire --help
python -m experiments.analyze data/trial.npz results/analysis-001
```

Read [experiment procedure](docs/experiments.md) and [circuit and mathematics](docs/system_guide.md) before using equipment. Do not use the acquisition command until the actual high-voltage driver and measurement electronics have been designed and verified.
