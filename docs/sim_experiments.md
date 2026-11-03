# Simulation experiments and figures

The study applies paired random held inputs to two neon biases, an open circuit, a resistor and a separately driven LED. It saves inputs, netlists, traces, settings, metrics and per-seed results. Parameters and optical response are illustrative, not measured.

`figures/traces.png` shows drive and bulb voltages. `figures/correlation.png` shows training-set correlations between brightness proxy, event rate, variation and voltage; blank means undefined. `figures/narma.png` compares test NMSE; error bars are seed standard deviations, not confidence intervals. Pulse results show first ignition time and whether the model remains lit at each ballast setting. Their delay is circuit charging, not modeled intrinsic plasma delay.

`figures/prediction.png` compares the first seed's near-neon prediction and held-out target. `figures/ipc.png` shows linear reconstruction score versus input delay; the full degree-2 estimate is in the JSON. `figures/pulse.png` compares the two ballast pulse responses. The existing pilot's expanded set is under `results/neon/experiment-20261031/figures-expanded/`.

`study/analysis.json` records delay-resolved scores and truncated IPC with shuffled nulls. They are not complete theoretical capacities. Repeat with half the maximum timestep and report changes. A general hybrid or physical Lyapunov exponent is not established by these simulations.

An illustrative five-seed pilot at 5 µs maximum timestep produced combined-feature test NMSE of 0.883 ± 0.055 for the near neon switch, 0.781 ± 0.068 for the active switch, 0.798 ± 0.064 for the hypothetical LED and 0.753 ± 0.050 for the open-circuit voltage control. This is exploratory and does not show an improvement over that control. LED drive and output light were not calibrated to match the neon; the numerical comparison is not a matched physical LED result.

With an assumed 1 nF capacitance, the illustrative 0.5 MΩ and 2 MΩ pulse cases produced first ignition delays of about 0.149 ms and 0.581 ms. The first model remained lit at the end of the test and the second did not. These are ngspice results for an instantaneous switch: they are dominated by electrical charging and are not measurements or claims of intrinsic plasma ignition delay. Results, netlists and plots from the pilot are local under `results/neon/experiment-20261031/` and are excluded from Git.

Scientific-review process: Kassis et al. (2026), Scientific Agent Skills, [preprint](https://doi.org/10.48550/arXiv.2609.00065); this is methodology, not evidence about neon lamps.
