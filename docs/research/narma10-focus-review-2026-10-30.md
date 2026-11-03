# NARMA-10 focus: initial review

2026-10-30. Status: research/design note, not an approved implementation or a construction specification.

## Confirmed user direction

Discard audio from the active workflows and focus on NARMA-10. Adapt the experiments, documents and circuit design together. The user confirms Circuit A has not been built, so the input stage can be redesigned. Continue protecting original master and using neutral new Git metadata. Coordinate with the supervisor-progress side thread; its original untracked S6 plotting script is preserved.

## Current implementation findings

**Observed:** The physical branch already generates seeded held steps through the Teensy's PWM output. Its software configuration/session module still contains audio fields, playback functions and optional audio dependencies. E4 records IPC trials; there is no common physical/simulation NARMA evaluation command. S6 imports simulation condition names, reads IPC trials and fixes washout/split/penalty choices inside a simulation study script.

**Observed:** Bench configuration still names a laptop source and audio tap. Remove those meanings from the new design. A0 can instead measure the actual filtered electrical drive for diagnostics and calibration; do not silently include that input measurement as a reservoir feature. Preserve protected separation between low-voltage electronics and the high-voltage node. A coupling capacitor can retain an electrical protection role after audio is removed.

**Derived:** For the illustrative bulb-free circuit in simulation/config.py, R_th=2.21 Mohm || 10 Mohm, R_e=2.2 Mohm, C=10 nF and C_c=1 microF, the implemented off-state matrix has eigenvalues approximately -100.909 and -0.248869 per second. Time constants are 9.910 ms and 4.018 s. At a 20 ms input step these are approximately 0.495 and 200.909 steps. These are model settings, not measured NE-2 memory, and do not establish that either mode is sufficiently excited/observable for NARMA-10. Obtain a delay-resolved memory curve and held-out benchmark rather than choosing a component value from this ratio alone.

**Observed historical evidence:** Old results/sim_narma.json reports mean test NMSE: bulb-free five features 0.7221; ten-tap linear input reference 0.3524; delay-line plus products 0.2673; delay+memory bulb five features 1.0258. These predate the recent timestamp/convention corrections and are simulated historical results. Do not reuse their plots as results of the redesigned system. They show why changing the project narrative alone cannot demonstrate a successful reservoir.

## Proposed scientific question

**Proposed hypothesis:** With the same known input sequence and a linear readout fitted only on training data, measured bulb states improve held-out NARMA-10 prediction relative to matched linear-circuit controls. Keep a stronger input-history nonlinear reference as an additional measure of practical value; it is not the same question as the bulb's contribution over its surrounding circuit.

A score alone is insufficient. Quantify paired differences under the same input seeds/settings; keep between-bulb variation separate from repeat noise; choose the claimed practical improvement before the final test. There is no universal NARMA-10 NMSE threshold that proves useful physical computation.

The independent variable for a paired comparison is bulb/nonlinear element present versus the appropriate control, holding acquisition, drive, input sequence and readout procedure fixed. A resistor replacement and an open/bulb-free network answer different questions and should retain different labels.

## Input and target definition

NARMA input u_k is random in [0,0.5]. The software target is

    y_(k+1) = 0.3*y_k + 0.05*y_k*sum(y_(k-i), i=0..9)
              + 1.5*u_(k-9)*u_k + 0.1.

Only the input is driven into the circuit; targets and target histories never enter primary readout features or hardware feedback. State x_k after input step k predicts y_(k+1).

**Derived quantization mapping:** If the Teensy uses 8-bit levels L_k in 0..255, define the actual benchmark input as u_k=L_k/510, and normalized bipolar command r_k=4*u_k-1. Build the target from that exact applied sequence, and disclose that this is a quantized uniform benchmark variant. Do not generate continuous targets and silently drive a different quantized sequence.

## Two approaches to choose between

1. **Recommended: characterize the single bulb's native dynamics first.** Clocked PWM/filtered steps, protected injection, selectable bias/R/C settings, synchronized light/current/node readouts and flash events. Use within-step samples as possible virtual nodes, without claiming that more samples create independent memory. Keep explicit input delays/feedback out of this first architecture. Tune on validation data and report failure if the physical bulb adds no useful computation.
2. **Add an explicit delay/feedback reservoir from the start.** A delay or feedback loop can provide memory lacking in a single bulb. This requires defining the full augmented system, its controller/latency/noise and corresponding controls; an improved score cannot be attributed solely to the bulb's intrinsic memory. Prefer this as a separately labeled second architecture if the first lacks useful memory.

The recommendation is an engineering/scientific inference, not a demonstrated NE-2 result. Final component values, current limits and isolation/protection ratings require actual parts, datasheets and measurements.

## Proposed experiment and document changes after design approval

- Remove audio playback/encoding, speech experiments, datasets, laptop/audio calibration, volume settings and audio-specific dependencies from both active branches. Historical master/history and local raw files remain preserved.
- Make one shared NARMA evaluator consume physical or simulated trial records with the same alignment, feature rules, train/validation/test split and report fields.
- Establish a diagnostic sequence: component/drive verification, input-path and sampling check, step response and repeatability, delay-resolved memory, then NARMA-10 against controls. IPC remains a supporting diagnostic, not a competing primary task.
- Use a fixed linear ridge readout as the primary task readout. Fit scaling on training data, choose circuit/step duration/feature count/regularization on training/validation only, and evaluate independent held-out inputs after settings are fixed.
- Report constant/train-mean and current-input baselines, matched resistor and bulb-free hardware controls, a ten-tap linear history reference and a nonlinear history reference. Match drive and sampling; explain the role of each comparison.
- Replace the speech-focused protocol/roadmap and legacy board diagrams with a NARMA signal-flow figure, circuit with variable/measurement labels, step-to-feature timing diagram, delay-memory curve, target/prediction/residual overlay and paired error comparison across bulbs/seeds.
- Mark all previous S6 charts historical; rebuild new figures from traceable new records and saved settings. Keep simulated and measured outcomes visibly distinct.

## Verified sources and scope

- Picco, Jaurigue, Luedge and Massar (2025), Efficient optimisation of physical reservoir computers using only a delayed input, Communications Engineering 4, 3. https://doi.org/10.1038/s44172-025-00340-6 ; accessible full text https://pmc.ncbi.nlm.nih.gov/articles/PMC11742992/ . Experimental support for delayed-input augmentation with a linear readout. Its optoelectronic apparatus is not an NE-2 circuit, and its performance does not predict ours. Its displayed NARMA sum index appears inconsistent; keep our explicit standard recurrence and verify indexing against independent source/code.
- Ortín and Pesquera (2019), Tackling the Trade-Off Between Information Processing Capacity and Rate in Delay-Based Reservoir Computers, Frontiers in Physics 7, 210. https://doi.org/10.3389/fphy.2019.00210 . Supports the need for nonlinear processing and usable memory and discusses sampling/response/delay tradeoffs. It does not validate NE-2 component values or imply that input-step time should equal a particular RC time constant.
- Existing project literature and decisions: docs/research/ne2_circuit_literature.md and docs/DECISIONS.md. These contain historical audio choices that the new design will explicitly supersede.
