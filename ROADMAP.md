# Plasma Reservoir Computing — Roadmap

## Ownership

| Step | Owner | Status |
|------|-------|--------|
| 1. Reservoir characterization | Majesti, Samuel, Luca | Not started |
| 2. Standard benchmarks | Samuel, Luca | Not started |
| 3. Bayesian network readout | Mahault | **Scaffolded** |
| 4. Digital twin | Luca | Stub ready |
| 5. Comparison & paper | All | Blocked on 1-4 |

---

## Step 1 — Reservoir Characterization (Majesti, Samuel, Luca)

**Goal**: Prove the plasma is actually computing — not just passing signal through.

### Tasks
- [ ] Collect multi-trial data: same word, same volume, 10+ repeats → determinism
- [ ] Collect multi-class data: 3+ distinct words at same volume → separation
- [ ] Collect multi-volume data: same word at 50/75/100% → amplitude sensitivity
- [ ] Standardize CSV format: `timestamp, voltage_in, intensity, frequency, oscillation`
- [ ] Implement `PlasmaDataLoader.load_trial()` in `reservoir/physical.py`
- [ ] Run `memory_capacity()` — target: MC > 5 (at minimum)
- [ ] Run `separation_matrix()` — target: inter > 2× intra class distance
- [ ] Run `effective_dimensionality()` — report how many of 3 dims are exploited
- [ ] Estimate Lyapunov exponent from repeated trials of same input

### Key questions
- Is the neon bulb deterministic enough? (Same input → same trajectory within noise)
- How fast does memory decay? (MC curve shape)
- Are 3 readout dimensions (intensity, freq, osc) sufficient or do we need more?

---

## Step 2 — Standard Benchmarks (Samuel, Luca)

**Goal**: Place the plasma reservoir on the RC benchmark landscape.

### Tasks
- [ ] NARMA-10: inject u(t) as voltage, train readout to predict y(t)
- [ ] Mackey-Glass: inject x(t), predict x(t+1)
- [ ] Report NMSE for both, compare against published ESN / Hopf baselines
- [ ] If memory is too short for NARMA-10, try NARMA-5

### Baselines to beat
- Echo State Network (software): NMSE ~0.01 on NARMA-10
- Hopf oscillator (Shougat 2023): 93% audio classification accuracy

---

## Step 3 — Bayesian Network Readout (Mahault) ← YOUR PART

**Goal**: Novel contribution — structured probabilistic readout from reservoir states.

### Done
- [x] `BayesNetReadout` class with DAG validation, topological sort
- [x] Per-node `BayesianRidge` with uncertainty propagation
- [x] Ground-truth parent conditioning during training (avoids error cascade)
- [x] Dynamic Bayesian network mode (temporal=True) for time-series
- [x] `model_comparison()` — log Bayes factor: DAG vs flat readout
- [x] Synthetic ESN experiment script
- [x] Unit tests

### TODO
- [ ] Run synthetic experiment, verify DAG wins when structure matches data
- [ ] Structure learning: learn the DAG from data (score-based, e.g. BIC/BDeu)
- [ ] Uncertainty propagation: Monte Carlo forward pass through DAG (sample from parent posteriors)
- [ ] Visualization: DAG graph with edge weights, per-node uncertainty
- [ ] Apply to real plasma data once Step 1 delivers CSV files
- [ ] Paper figures: DAG vs flat NMSE, calibration plots, log BF across tasks

### Publication angle
Nobody has done probabilistic graphical model readouts on a physical reservoir.
Most RC papers use flat linear regression. Structured readout + calibrated
uncertainty + Bayesian model comparison is novel.

---

## Step 4 — Digital Twin (Luca)

**Goal**: GP surrogate of the plasma so we can run thousands of benchmark trials.

### Tasks
- [ ] Collect sufficient real trials to fit GP (100+ input/output pairs)
- [ ] Fit `PlasmaDigitalTwin` and validate against held-out real data
- [ ] Quantify twin fidelity: NMSE between twin and real plasma on test set
- [ ] Use twin for large-scale NARMA/MG benchmarks
- [ ] Optionally: Neural ODE twin for better extrapolation

---

## Step 5 — Comparison & Paper (All)

**Goal**: Publishable result.

### Experiments
- [ ] Plasma RC vs ESN vs Hopf oscillator on NARMA-10, Mackey-Glass
- [ ] BayesNet readout vs flat readout on each reservoir (log Bayes factor)
- [ ] Calibration analysis: are Bayesian uncertainty estimates reliable?
- [ ] Digital twin fidelity: does the twin reproduce real plasma RC performance?

### Paper structure (draft)
1. Introduction: physical RC, plasma as novel substrate
2. Methods: plasma setup, reservoir characterization, BayesNet readout
3. Results: benchmarks, DAG vs flat, calibration, twin validation
4. Discussion: plasma advantages/limitations, when does structure help?

### Target venues
- Scientific Reports (like the Hopf paper)
- Neuromorphic Computing and Engineering
- ALIFE 2026 (if timeline permits)
