# Minimal neon-lamp reservoir (NE-2H class)

Tests whether a single neon glow lamp has *intrinsic* nonlinear fading memory, so that it can act as a physical
reservoir, using the smallest circuit that can show it. This branch holds the hardware pipeline: firmware, acquisition
and analysis.

```
V_D = V_bias + G·x ──Z_o──R_B──┬── lamp ── R_S ── return
  (HV linear driver)           └ C_s (stray only, measured; no capacitor is added)
readouts: drive monitor (diagnostic) · node voltage v · lamp current v_S/R_S · photodiode light
```

**Status:** no hardware has been run. Every physical value in `configs/ne2h.json` is `unknown` until measured,
except the datasheet design current (CML-IT C2A, 1.9 mA, not a pulse rating).

## Install and test

```bash
pip install -e ".[dev]"          # add .[acquisition] for pyserial
pytest -q                         # circuit closed forms, analysis ground truth, link, recordings
arduino-cli compile --fqbn teensy:avr:teensy41 firmware/ne2h
```

Technical description: `docs/technical.md`.

## Layout

| Path | Contents |
|---|---|
| `plasma_rc/circuit.py` | Parameter file (each value tagged measured / datasheet / assumed / unknown), Thévenin, load-line regimes R0 dark / R1 flashing / R2 lit / latch, safety bounds |
| `plasma_rc/sim.py` | Circuit model used only for the N-A surrogate: driver pole, node equation, hysteretic lamp with i.i.d. strike delay |
| `plasma_rc/stimuli.py` | Waveforms as `[DAC level, ticks]` segments: random held input, binary input, rank sequence sets, ramp, pulse pairs with sham trials |
| `plasma_rc/states.py` | State readout: sub-window means (READ-01), strike latency (READ-02); the surrogate uses the same readout |
| `plasma_rc/surrogate.py` | The N-A surrogate: mean state over several history-independent delay realizations |
| `plasma_rc/analysis.py` | Ridge readout, positive-delay capacities with shuffle null, consistency, surrogate attribution, strike-delay memory |
| `plasma_rc/benchmarks.py` | Benchmark battery: NARMA-2/5/10 with N-B baselines, capacities, delayed XOR/parity, kernel vs generalization rank |
| `plasma_rc/stats.py` | Cluster bootstrap over bulbs, Holm correction |
| `plasma_rc/hw/` | Teensy frame protocol, board link with waveform upload, capture records, recordings |
| `firmware/ne2h/` | Teensy 4.1 waveform player, round-robin ADC sampler, comparator flash timestamps |
| `experiments/` | `acquire.py` (play a stage on the board and record), `analyze.py` (stage analysis) |
| `configs/` | `ne2h.json` (to be filled from measurements); `sim_illustrative.json` is a test fixture only |

## Experiment stages

| Stage | Purpose | Command |
|---|---|---|
| E0 | Driver, filter, divider, sensor and ADC step residuals on dummy loads | `acquire … e0`, `analyze e0` |
| E1 | Per-bulb static characterization: V_b bracket, lit-branch fit (V_m, r_on), I_x bound | `acquire … e1`, `analyze e1` (V_b needs a separate pre-strike waveform) |
| E2 | Pulse pairs, "different past, same present", with sham conditioning and a settling check | `acquire … e2`, `analyze e2` |
| E4 | Benchmark battery per `--stimulus` (held, binary, rank, prefix): capacities, NARMA-2/5/10 vs baselines, XOR, rank, consistency, attribution vs the surrogate, strike timing | `acquire … e4 --stimulus S`, `analyze e4` |
| E5 | Frozen confirmatory run on fresh bulbs and sessions | as E4, with every setting fixed beforehand |


## Safety

Neon lamps run at high voltage. The acquisition script refuses lamp stages unless the derived continuous-current
bound holds and the operator passes `--confirm-safety`. These checks are not interlocks: verify the driver current
limit, resistor voltage and power ratings, ADC clamps (Teensy pins are 3.3 V, not 5 V tolerant), probe ratings and
the discharge path before energizing. The ballast limits the source current only; stray-capacitance discharge
through the lamp at each strike is bounded separately and the lamp datasheet gives no pulse rating.
