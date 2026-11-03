# Minimal neon circuit: initial ngspice reference

`StudyConfig` specifies the ballast and total node parasitic capacitance in ohms and farads. `run_transient` applies a piecewise-linear source to that circuit and returns time, source voltage, bulb voltage and lamp current. The `open` and `resistor` options provide electrical controls. `NeonSwitch` is a deterministic instantaneous hysteretic switch with a linear conducting branch; its four parameters are required explicitly and are not measured defaults.

Each run creates a new directory containing the netlist, input/configuration, ngspice output log and raw trace; existing directories are never overwritten. The capacitance is a lumped hypothesis, not a measurement of the bulb alone. The source and measurement are ideal, and optical output, stochastic ignition, internal glow dynamics, sensing bandwidth and current protection are not modeled. It is not a physical build specification or a validated plasma model.

Example (illustrative numbers, not a hardware recommendation):

```python
from pathlib import Path
from plasma_rc.neon.config import StudyConfig
from plasma_rc.neon.spice import NeonSwitch, run_transient

config = StudyConfig(ballast_ohm=1e6, parasitic_capacitance_f=1e-9)
bulb = NeonSwitch(strike_v=75, extinction_v=52, intercept_v=50, on_resistance_ohm=100e3)
drive = [(0, 0), (0.0001, 90), (0.005, 90), (0.0051, 40), (0.01, 40)]
trace = run_transient(config, drive, 0.01, 1e-6, Path("/tmp/neon-example"), bulb=bulb)
```

Use a fresh output directory for each run. Additional provenance, separate parasitic components, optical readout and the remaining experimental study are not yet implemented.

## Fitting an electrical switch scenario

`python -m experiments.neon_calibrate trace.csv grid.json output/ --validation heldout.csv`
simulates explicitly listed `NeonSwitch` candidates and ranks them against a synchronized electrical trace. CSV columns are `time_s,drive_v,voltage_v`; `current_a` is optional. Time must start at zero and be strictly increasing. Use calibrated drive and bulb-voltage measurements; any current channel must be independently measured, synchronized, and in amperes. Do not infer lamp current from the ballast voltage drop without accounting for capacitive current.

The JSON grid must explicitly provide candidate lists for `strike_v`, `extinction_v`, `intercept_v`, `on_resistance_ohm`, and `parasitic_capacitance_f`, plus scalar `ballast_ohm` and `max_step_s`. There are no default NE-2H parameter ranges: the datasheet does not establish the unknown switch thresholds, conducting-branch slope, parasitic capacitance, or dynamics. Invalid parameter combinations are recorded. The score is a mean of per-channel RMSE normalized by observed standard deviation; provide a separate validation trace to check a candidate selected on calibration data.

This fits only the instantaneous hysteretic electrical model. It does not model optical output, statistical ignition delay, or internal glow dynamics. The lowest-scoring grid point is not necessarily uniquely identified; inspect neighboring candidates and repeat across measured conditions and bulbs. A low grid-fit score is not evidence that the physical bulb has been accurately modeled. Sweeping cannot substitute for measured data.
