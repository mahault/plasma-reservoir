# Plasma Reservoir Computing with Bayesian Network Readouts

Using plasma as a physical reservoir for computation, with a novel DAG-structured Bayesian readout layer.

## Background

Standard reservoir computing uses a single linear readout from the reservoir's high-dimensional state to a target. This project replaces that flat readout with a **Bayesian network** — a directed acyclic graph of Bayesian Ridge regressors where each node reads from the reservoir state and its parent nodes' outputs. This gives us:

- Structured conditional dependencies that encode domain knowledge (e.g. energy depends on intensity + frequency)
- Calibrated uncertainty at every node
- Formal model comparison via log Bayes factors (DAG vs flat)
- A dynamic Bayesian network mode for time-series tasks

The physical reservoir is a **neon bulb plasma**. Audio is converted to voltage, injected into the plasma, and three observables are read out via photodiode: **intensity** (brightness), **frequency** (flicker rate), and **oscillation**. Baseline subtraction isolates the plasma's nonlinear transformation of the input. Whether the plasma actually computes (rather than passing signal through) is an open question — see `PROTOCOL.md` for the recording protocol designed to answer it, and `data/README.md` for what the recordings received so far do and don't show.

## Project Structure

```
plasma_rc/
├── reservoir/
│   ├── interface.py            # Abstract reservoir interface (ABC)
│   ├── physical.py             # Physical plasma data loader + live hardware stub
│   └── digital_twin.py         # GP-based surrogate for large-scale experiments
├── characterization/
│   ├── memory_capacity.py      # How many past timesteps the reservoir retains
│   ├── separation.py           # Do distinct inputs produce distinct states?
│   └── dimensionality.py       # PCA-based effective dimensionality
├── benchmarks/
│   ├── narma.py                # NARMA-10 signal generator
│   └── mackey_glass.py         # Mackey-Glass chaotic time series generator
├── readout/
│   ├── linear.py               # Standard linear readout (Ridge / BayesianRidge)
│   └── bayesnet.py             # DAG-structured Bayesian readout (core contribution)
└── evaluation/
    └── metrics.py              # NMSE, CoD, calibration error

experiments/
├── bayesnet_readout.py         # Synthetic ESN demo: DAG vs flat readout
└── real_data_diagnostic.py     # Honest diagnostic of the real recordings

data/                           # Real plasma recordings (see data/README.md)

tests/
└── test_bayesnet.py            # 14 tests covering DAG construction, fit/predict,
                                # model comparison, observed parents, MC
                                # propagation, and temporal mode
```

## What's Implemented

**Fully working:**
- `BayesNetReadout` — DAG-structured readout with topological ordering, per-node BayesianRidge, ground-truth parent conditioning during training, and temporal (dynamic Bayesian network) mode
- `predict(observed=...)` — condition children on intermediate observables measured at test time (where the structured readout genuinely beats a flat one)
- `predict(n_samples=K)` — Monte Carlo uncertainty propagation through the DAG (per-path parent sampling, law of total variance)
- `model_comparison()` — fair same-data log Bayes factor: p(y | states, parents) vs p(y | states)
- `LinearReadout` — baseline for comparison (Ridge or BayesianRidge)
- Characterization metrics — memory capacity, separation matrix, Lyapunov estimation, effective dimensionality
- Benchmark signal generators — NARMA-10, Mackey-Glass
- Evaluation metrics — NMSE, CoD, expected calibration error
- Synthetic experiment — demonstrates the full pipeline on an echo state network

**Stubs (awaiting real hardware data):**
- `PlasmaDataLoader` — needs CSV recordings from the physical plasma setup
- `LivePlasmaReservoir` — needs serial/ADC interface to the neon bulb + photodiode
- `PlasmaDigitalTwin` — needs enough real trials to fit the GP surrogate

## Setup

```bash
conda create -n plasma-rc python=3.12 numpy scipy scikit-learn networkx matplotlib pytest -y
conda activate plasma-rc
pip install -e .
```

## Running

**Tests:**
```bash
pytest tests/ -v
```

**Synthetic experiment (DAG vs flat readout on echo state network):**
```bash
python experiments/bayesnet_readout.py
```

Example output:
```
=== word_class readout comparison (test set) ===
  flat linear              NMSE 0.2269  CoD 0.7731  ECE 0.0136
  DAG, plug-in parents     NMSE 0.2280  CoD 0.7720  ECE 0.0407
  DAG, MC propagation      NMSE 0.2282  CoD 0.7718  ECE 0.0076
  DAG, observed parents    NMSE 0.1802  CoD 0.8198  ECE 0.0207

  log BF p(y|states,parents) vs p(y|states), word_class: 91.12
```

Flat and DAG-with-predicted-parents tying on NMSE is expected — compositions of linear-Gaussian nodes are linear in the states, so the DAG collapses to the flat readout in that regime. The structured readout wins when intermediate observables are measured at test time (as the plasma channels are), and Monte Carlo propagation gives the best-calibrated uncertainty of all variants.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full plan. Summary:

| Step | What | Owner | Status |
|------|------|-------|--------|
| 1 | Characterize the plasma reservoir (memory, separation, dimensionality) | Majesty, Samiulhaq (Luca - support) | Not started |
| 2 | Run standard benchmarks (NARMA-10, Mackey-Glass) | Majesty, Samiulhaq (Luca - support) | Not started |
| 3 | Bayesian network readout | Mahault, Majesty | Implemented |
| 4 | Digital twin (GP surrogate of plasma) | Luca/Alejandro, Majesty | Stub ready |
| 5 | Comparison paper | All | Blocked on 1-4 |

## Next Steps for Step 3

- Structure learning — learn the DAG from data (BIC/BDeu scoring) instead of hand-specifying it
- Nonlinear node option (GP or polynomial features) — required for a DAG-beats-flat result when parents must be predicted
- Visualization of DAG with edge weights and per-node uncertainty
- Apply to real plasma data once CSV recordings are available
