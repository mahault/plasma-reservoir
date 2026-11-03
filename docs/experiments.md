# Physical experiments

**Status:** acquisition software and firmware compile, but the source driver, sensor front end and physical system are not yet validated. No physical results are included. Before energizing, identify actual device part and ratings, calculate and verify worst-case current and resistor power, and verify rated probes, isolation, ADC limits and the LED's separate low-voltage current-limited drive. Software limits are recorded metadata and cannot enforce electrical safety.

First characterize each bulb: strike/extinction distributions, current–voltage response, pulse timing and recovery under controlled light and temperature. Then run paired seeded NARMA input sequences for near-breakdown neon, continuously active neon, a separately driven LED and open/resistor controls. Repeat across bulbs and input seeds; log temperature, warm-up, actual applied drive, ADC and light calibration, and circuit values. Change one setting at a time. Use resistor sweeps to measure delay rather than assuming a particular resistor produces a given effect.

The CLI records the commanded quantized input and ADC channels. Configure distinct channel pins for drive, photodiode and bulb voltage, plus measured gain and dark baseline. It saves raw samples, flash events, metadata and checks for drops. Validate the comparator before interpreting frequency. Brightness is sensor voltage after dark subtraction, not calibrated optical power. The analyzer produces training-set correlations, per-feature and combined NARMA NMSE, and shuffled-cutoff truncated IPC. Choose settings on validation data and reserve new test sequences for confirmation.

Use `python -m experiments.compare pairs.json neon-analysis.json led-analysis.json` to list neon–LED comparisons with identical commanded input and split boundaries. The output keeps individual pairs rather than treating repeated pairings as independent samples. Matching input alone does not establish matched optical range, drive conditions or acquisition bandwidth; inspect those separately.

Compare LED and neon with the same input sequence and acquisition protocol; match optical range and bandwidth where feasible, record differences and never apply neon voltage to an LED. A resistor has no optical emission. Physical repeatability and local divergence must not be labeled a Lyapunov exponent without a validated method.

Scientific-review process: Kassis et al. (2026), Scientific Agent Skills, [preprint](https://doi.org/10.48550/arXiv.2609.00065); process guidance, not evidence about neon.
