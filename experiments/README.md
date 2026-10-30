# Experiment commands

Start with the [system walkthrough](../docs/architecture.md) for inputs, the physical circuit, recording, features and evaluation. The [simulation guide](../docs/simulation.md) describes numerical settings and studies. The root [README](../README.md) gives this branch's installation and entry points.

Run experiment commands as modules from the checkout root: `python -m experiments.ne2.<name>`. E0–E6 are physical commands on hardware-pipeline; S1–S6 are numerical studies on simulation; A1–A3 analyse saved trials. Reusable analysis is in `plasma_rc.analysis`, and trial storage is in `plasma_rc.trials`.
