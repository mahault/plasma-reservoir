# Project context

The research question is whether a single physical neon bulb adds useful nonlinear memory for NARMA-10. This repository contains both the simulation pipeline (ngspice candidate circuits) and the physical acquisition pipeline (Teensy 4.1 board). Physical conclusions require measured devices and controls; simulation values are not construction recommendations.

Use readable code, meaningful test-first changes and recorded experiment settings. Preserve raw data and `master`. Separate simulation, measurements and hypotheses; keep input and train/validation/test boundaries explicit, never tune on test data, and report negative results. Record scientific decisions in `docs/DECISIONS.md` and evidence in `docs/research/`.

V_D is drive voltage, R_B is ballast resistance, V_L is lamp voltage and I_L is lamp current. Device strike, extinction, response time and light transfer vary and must be measured. The LED is a distinct control with its own low-voltage source and current limit; it has no neon breakdown regime.

Before hardware use identify the actual device ratings, ballast, driver limits, sensor calibration, comparator settings and safe probe connections. Software settings are not safety interlocks. Record device ID, temperature, warm-up, drive conditions, calibration and any dropped data.
