# NE-2 reservoir terminology

| Term | Meaning |
|---|---|
| Trial record | One capture, known stimulus, timing, settings, provenance and run metadata. |
| Capture | Ordered ADC samples and flash events, clock/timer information, integrity counters and calibration. |
| Acquisition profile | Board, clock, timer period, channel order, ADC bit depth and reference. |
| Simulation setup | Circuit, acquisition profile, random seed and integration resolution for one run. |
| V_s | Measured module supply voltage [V]. |
| V_th, R_th | Supply equivalent voltage [V] and resistance [ohm] after the divider load. |
| v, w | Node voltage and coupling-capacitor voltage [V]. |
| V_intercept | Intercept of the affine conducting-bulb model [V], distinct from maintaining voltage at a measured current. Historical simulator field: V_m. |
| Instantaneous linear capacity | Linear reconstruction of the current input u(k) from x(k). |
| Memory capacity (MC) | Sum of degree-one capacities for strictly positive input delays. |
| Total IPC | Sum of all retained capacities, including delay-zero and nonlinear terms. |
| Finite-time contraction diagnostic | Slope of log replica distance over a stated interval; does not establish an asymptotic Lyapunov exponent. |
| Consistency | Mean pairwise correlation of repeated responses to a common input; undefined for constant traces. |
| Control | Same measurement/analysis workflow without the nonlinear bulb, or with a resistor replacing it. |

Full equations, units and limitations: [system architecture](docs/architecture.md#1-system-overview).
