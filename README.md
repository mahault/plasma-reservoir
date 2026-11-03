# Neon reservoir: simulation

This branch studies one neon bulb and a separately driven LED with ngspice. It generates NARMA-10, optical-proxy, correlation, truncated IPC and ballast-pulse results. It does not control hardware or establish real bulb performance.

Install with `pip install -e ".[dev]"`, install ngspice, then run `python -m pytest -q`. Run `python -m experiments.neon results/experiment-001 --steps 900 --seeds 5`. The output directory must be new.

Read [simulation experiments](docs/sim_experiments.md), [circuit and mathematics](docs/system_guide.md), [decisions](docs/DECISIONS.md) and [research](docs/research/README.md). The light proxy, lamp parameters and LED model are hypotheses, not physical measurements or construction ratings.
