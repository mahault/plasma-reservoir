# Due diligence: circuit A, data flow and analysis plan (2026-10-24)

Review type: scoping. Question: is the circuit-A design, its data flow and its analysis plan (technical.md, D-01–D-27) logically sound and consistent with current literature, before code is written?
Labels: **Cited**, **Derived**, **Inferred**, **Unknown**. Preprints tagged **[preprint]**.

## Search log

| Tool | Date | Query (short) | Result |
|---|---|---|---|
| Consensus | 2026-10-24 | plasma / neon reservoir; conditional Lyapunov; excitable RC | Quota exhausted (resets 2026-11-01); not used |
| alphaXiv | 2026-10-24 | plasma, gas discharge, neon + reservoir computing | 10 hits, none a gas-discharge reservoir |
| alphaXiv | 2026-10-24 | conditional Lyapunov exponent, consistency, RC, experimental | 11 hits; Lymburn 2019, Jüngling 2021 relevant |
| alphaXiv | 2026-10-24 | MC / IPC estimation, noise, physical reservoir | Ramachandran & Massar 2026, Kotoku 2026 relevant |
| alphaXiv | 2026-10-24 | spiking / excitable single-node RC | Van Brandt 2026 (cites Mainen & Sejnowski 1995) |
| Web | 2026-10-24 | RC + plasma / glow discharge / neon lamp | No RC hit; neon-lamp GDD detectors only |
| Europe PMC | 2026-10-24 | Dambre 2012 full text (PMC3400147); Lymburn 2019; Mainen 1995 | Bibliographic records + Dambre methods |
| Datasheet | 2026-10-24 | Microchip ATmega328P (Atmel-7810D, 01/15), downloaded and searched | ADC, comparator, USART facts below |

## Findings

| # | Area | Verdict | Evidence | Action |
|---|---|---|---|---|
| A1 | Novelty: no neon/glow-discharge reservoir | **Holds** (medium confidence: Consensus not searched) | alphaXiv + web: none found | Keep "untested hypothesis" |
| A2 | Regime choice: excitable, not free-running | **Holds, stronger** | Spike times are reproducible under a time-varying input but accumulate jitter when self-oscillating: Mainen & Sejnowski 1995, *Science* 268:1503, doi:10.1126/science.7770778 (**Cited**, bibliographic record verified; described in Van Brandt et al. 2026 [preprint]). Matches D-21 | Add as support for D-21; add flash-time reliability as an S3 metric for the near-breakdown regime |
| A3 | Laptop audio for held steps | **Fails** | Headphone outputs are AC-coupled (**Inferred**); a held step through a first-order high-pass droops ≈ T_step/τ (**Derived**). Corner f_c **Unknown** | D-28: UNO-generated PWM-DAC input for IPC and λ_c runs; laptop only for speech |
| A4 | UNO ADC rate | **Constraint** | ADC clock 50–200 kHz for full resolution; 13 ADC clocks per conversion, S/H 2 ADC clocks after an auto-trigger; trigger source Timer1 compare match B (**Cited**, datasheet §23.3–23.4, Table 23-6). At 125 kHz: ≤ 9.6 k conversions/s total (**Derived**) | Rate set from E1 (task 4); per-channel rate = tick rate / channels |
| A5 | ADC source impedance | **Fails for HV divider and photodiode load** | "optimized for analog signals with an output impedance of approximately 10k or less" (**Cited**, datasheet §23.6.1) | D-29: op-amp buffers on A1 (photodiode) and A3 (node divider); closes D-16 |
| A6 | Anti-aliasing | **Missing** | "Signal components higher than the Nyquist frequency (f_ADC/2) should not be present … remove high frequency components with a low-pass filter" (**Cited**, datasheet §23.6.1) | D-30: RC low-pass on each ADC input, corner below f_ch/2. On A2 it also stretches µs flash pulses into samplable bumps whose area ∝ flash charge (**Derived**); the comparator on D6 stays unfiltered |
| A7 | Memory variable unobserved | **Gap** | §4.1: memory lives in v(t) during recovery | D-31: HV divider node → buffer → A3; divider enters the bias (Thevenin, §4) |
| A8 | Flash timing | **Holds** | ACIC routes comparator to Timer1 input capture (**Cited**, datasheet §22.3.2); timestamps at 62.5 ns CPU-clock resolution (**Derived**, 16 MHz) | Keep D-24 |
| A9 | Serial link | **Holds** | 1 Mbps at 16 MHz: UBRR = 0 (U2X = 0) or 1 (U2X = 1), error 0.0 % (**Cited**, datasheet Table 19-12). USB bridge throughput **Unknown** → E1 | 1 Mbaud; E1 checks no frame loss |
| A10 | IPC finite-data bias | **Needs correction** | Dambre 2012 used T = 10⁶ steps, i.i.d. uniform u ∈ [−1, 1], normalised Legendre products, and set capacities below a cutoff to zero (**Cited**, PMC3400147). With finite N each capacity has a positive bias ∝ 1/N; Richardson extrapolation 2C_N − C_{N/2} removes the leading term (Ramachandran & Massar 2026 **[preprint]**; group of Dambre 2012's co-author, used because it is the only source for the correction) | ipc.py: fixed split, shuffled-surrogate cutoff (task 9), Richardson step; report N steps used. 10⁶ steps is not reachable at ms steps (**Derived**), so bias correction is mandatory |
| A11 | Capacity bound N | **Update** | Bound = number of linearly independent readout signals (Dambre 2012, Thm 4). With features (i_b, light, v, flash count, last interval) N can be ≈ 5–6, not 3 | Update P12; check rank of the feature matrix |
| A12 | Consistency C | **Holds** | Replica test = same drive, repeated; Pearson correlation of responses (Uchida et al. 2008 PRE 78:036203; Lymburn et al. 2019 *Chaos* 29:023118, doi:10.1063/1.5079686, **Cited**). Jüngling et al. 2021 consistency capacity **[preprint]** | Keep C; repeats with different prefixes = replicas from different initial states |
| A13 | λ_c from hardware | **No peer-reviewed experimental method found** | Consistency literature treats positive conditional Lyapunov exponent as equivalent to noise (Jüngling 2021 [preprint]); Uchida 2008 computes λ_c from a model, not data | λ_c estimator ships labelled **untested hypothesis**: slope of mean log-distance between replicas, fitted only above the silence floor. C and flash-time reliability are the cited measures |
| A14 | Controls | **Holds** | Torrejon 2017, Abreu Araujo 2020 (lit. review [12], [15]) | Keep D-12; shuffled floor added (task 9) |
| A15 | Undriven Lyapunov exponent | **Not meaningful here** | Silent (near-breakdown) or DC glow (always-on) with no input, §4 (**Derived**) | Not measured; stated in technical.md |

## Open after this audit
- Journal version of Jüngling et al. 2021 not found; Ramachandran & Massar 2026 and Kotoku 2026 are preprints.
- Consensus search to be repeated after 2026-11-01 for A1 and A13.
- Flash pulse width, laptop high-pass corner, USB-bridge throughput: **Unknown** until bench tasks.

## References added
1. Z. F. Mainen, T. J. Sejnowski, "Reliability of spike timing in neocortical neurons", *Science* 268(5216):1503–1506 (1995). doi:10.1126/science.7770778
2. T. Lymburn et al., "Consistency in echo-state networks", *Chaos* 29(2):023118 (2019). doi:10.1063/1.5079686
3. T. Jüngling, T. Lymburn, M. Small, "Consistency capacity of reservoir computers", arXiv:2105.13473 (2021) **[preprint]**
4. R. U. Ramachandran, S. Massar, "Information processing capacity of stationary physical systems: theory, data-efficient estimation methods, and photonic demonstration", arXiv:2605.19152 (2026) **[preprint]**
5. L. Van Brandt et al., "Interplay between excitability and noise in analog spiking neurons", arXiv:2610.06720 (2026) **[preprint]** (used only as the pointer to ref 1)
6. Microchip, ATmega328P datasheet, Atmel-7810D–AVR–01/15
