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
