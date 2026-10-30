# Audit disposition and evidence limits

The initial audit reviewed circuit-a-pipeline at 3063690. The original master remains unchanged. These new branches include corrections; existing historical datasets/results were not silently rewritten.

| Finding | Disposition |
|---|---|
| GP training/prediction off by one | Corrected to same-step window endpoints; independent seeded output randomness and shape validation. |
| Delay-zero counted as memory | Instantaneous capacity reported separately; MC uses positive delays. Existing finite-data correction retained. |
| Lost drop counts/calibration | Versioned records retain counters, source, board and known ADC settings. Legacy missing evidence remains unknown. |
| Duplicate/path/partial-write risk | Reject duplicate IDs/reserved keys/escaping names; atomic file publication; rollback and portable-session regressions. Single writer required. |
| ADC sample timestamp offset | Corrected nominal model alignment; physical Teensy latency remains unverified. |
| Shared mutable simulation globals | Explicit immutable profiles and setup; saved metadata determines analysis timing. |
| Experiment scripts imported as analysis | Reusable orchestration moved to analysis modules; commands call the same implementation. |
| Missing conducting resistance | Affine calculation includes slope; bench approximation labeled if slope/intercept unavailable. |
| One flash reused twice | Deterministic one-to-one greedy matching; not a global optimum. |
| Delayed strike below threshold | Preserved and documented as unresolved modeling behavior, with regression coverage. |
| Largest Lyapunov claim | Relabeled finite-time diagnostic; linear eigenvalue special case tested. |
| Stale physical-loader tests | Replaced with the preserved raw CSV contract and explicit unimplemented live stub. Legacy timestamps are never used as logged voltage input. |

The reviewed combined implementation passed 160 tests including ngspice, UNO/simavr and Teensy compilation. Seven new regressions reproduced and fixed four independent-review findings: initial serial loss, mismatched replica drive/provenance, multiprocessing job serialization and fresh output directories. Final branch-specific counts are recorded in each branch README. Source setup and dependency isolation are checked with a wheel installed in a fresh environment. No physical hardware was activated.

Remaining Unknowns: NE-2 delay parameters, stray capacitance, optical transfer, temperature/ageing behavior and actual Teensy timing. Always-on discharge physics is not established by the hysteretic switch. The Teensy firmware plays STEPS/SINE only; D-41's SD/streamed speech playback remains unimplemented. Existing laptop E5 capture is a separate supported path.

The GP twin is an input-history surrogate, not an identified autonomous plasma state model. Its fidelity needs held-out physical trials with logged inputs. A3's descriptive heuristic, one shuffled capacity cutoff, and finite-time contraction slopes are not statistical or dynamical proofs. Measurements across bulbs, controls and trials remain necessary.

Commit author/committer metadata on the new branch commits uses an unlinked neutral identity. Existing personal history on older remote branches and authenticated GitHub push records remain outside that change.
