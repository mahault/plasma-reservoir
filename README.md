# Minimal neon-lamp reservoir (NE-2H class)

Tests whether a single neon glow lamp has *intrinsic* nonlinear fading memory, so that it can act as a physical
reservoir, using the smallest circuit that can show it. This branch holds the simulation pipeline: an event-driven
model of the circuit, the analysis, and the method-validation study.

```
V_D = V_bias + G·x ──Z_o──R_B──┬── lamp ── R_S ── return
  (HV linear driver)           └ C_s (stray only, measured; no capacitor is added)
readouts: drive monitor (diagnostic) · node voltage v · lamp current v_S/R_S · photodiode light
```

**Status:** simulation results check the circuit and the analysis; they are not evidence about the lamp
(SIM-01). `configs/sim_illustrative.json` holds round assumed numbers, not NE-2H values.

## Install and test

```bash
pip install -e ".[dev]"
pytest -q                         # circuit closed forms, solver, readout, analysis ground truth
```

## Layout

| Path | Contents |
|---|---|
| `plasma_rc/circuit.py` | Parameter file (each value tagged measured / datasheet / assumed / unknown), Thévenin, load-line regimes R0 dark / R1 flashing / R2 lit / latch, safety bounds |
| `plasma_rc/sim.py` | Event-driven simulation: driver pole, node equation, hysteretic lamp with i.i.d. strike delay (the no-afterglow surrogate) |
| `plasma_rc/stimuli.py` | Waveforms as `[DAC level, ticks]` segments: random held input, binary input, rank sequence sets, ramp, pulse pairs with sham trials |
| `plasma_rc/states.py` | State readout: sub-window means (READ-01), strike latency (READ-02) |
| `plasma_rc/surrogate.py` | The N-A surrogate: mean state over several history-independent delay realizations |
| `plasma_rc/analysis.py` | Ridge readout, positive-delay capacities with shuffle null, consistency, surrogate attribution, strike-delay memory |
| `plasma_rc/benchmarks.py` | Benchmark battery: NARMA-2/5/10 with N-B baselines, capacities, delayed XOR/parity, kernel vs generalization rank |
| `plasma_rc/stats.py` | Cluster bootstrap over bulbs, Holm correction |
| `experiments/` | `simulate.py` (regimes, E2), `study.py` + `study_figures.py` (method-validation study) |
| `configs/` | `sim_illustrative.json` (round assumed numbers, not NE-2H values) |

## Run

Simulation: `python -m experiments.simulate configs/sim_illustrative.json OUT {regimes,e2}`; the E4 battery in simulation: `python -m experiments.study OUT`.

Reports: `docs/technical.md` (circuit and analysis mathematics), `docs/study_2026-11-04.md` (study results).
