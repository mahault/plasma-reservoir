# Project context

The research question is whether a single physical neon bulb adds useful nonlinear memory for NARMA-10. This branch simulates candidate circuits; physical conclusions require measured devices and controls. The physical pipeline is on `hardware-pipeline`. Do not change `master` without instruction.

Use readable code, meaningful test-first changes and recorded experiment settings. Preserve raw data. Separate simulation, measurements and hypotheses; keep input and train/validation/test boundaries explicit, never tune on test data, and report negative results. Record scientific decisions in `docs/DECISIONS.md` and evidence in `docs/research/`.

V_D is drive voltage, R_B ballast resistance, V_L lamp voltage and I_L lamp current. Before hardware operation identify actual device ratings, current limiting and instrument protection. Simulation values are not construction recommendations. LED operation requires its own rated low-voltage drive.
