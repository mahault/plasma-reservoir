# NE-2 relaxation-oscillator reservoir: literature review

Date: 2026-10-13. Scope: support (or not) for the provisional circuit: one NE-2 lamp, ~90 V DC boost supply, Rs charging C, C in parallel with the lamp (Pearson–Anson relaxation oscillator), laptop audio AC-coupled through Re into the same node, photodiode + low-side current-sense readout, Arduino UNO ADC.

Labels: **Cited** = stated by the numbered source; **Derived** = follows by arithmetic/logic from cited facts; **Inferred** = my judgement, not stated by any source.
Search tools: Consensus, alphaXiv, web search. Numbers from datasheets were read directly from the PDF (text layer or scanned page image), not from memory.

---

## 1. NE-2 / small neon glow-lamp device model

**Two critical voltages and the relaxation cycle.** A neon lamp has an upper ("start a flash") and lower ("flash ceases") critical voltage; with a capacitor in parallel and a series resistor to DC, the capacitor charges to the upper value, the lamp fires and discharges it down to the lower value, and the cycle repeats [17] (**Cited**; Paranjpé 1928 attributes the explanation to Mecke and Lambrez 1926). The original description of the circuit is Pearson and Anson [16] (**Cited**: bibliographic record only, full text not read; sources list it as Proc. Phys. Soc. London vol. 34, dated 1921, not 1922).

**I–V characteristic and hysteresis.** DC discharges show hysteresis between the Townsend (breakdown) and glow regimes: on a backward sweep the discharge voltage falls below the breakdown voltage, and the self-sustaining voltage coincides with the backward-sweep voltage; it decreases with initial plasma density [18] (**Cited**, PIC-MCC simulation, not an NE-2). A simulation attributes glow-discharge V–I hysteresis to bistability between relaxation oscillation and the equilibrium state [19] (**Cited**; conference paper, venue not verified). Kennedy and Chua model the neon bulb as a three-segment piecewise-linear current-controlled resistor, and this was enough to reproduce their experiment [4] (**Cited**). Self-oscillations in a parallel-plate argon glow discharge exist in the negative-differential-resistance region and are reproduced by a plain RC charge/discharge circuit model; frequency rises with current and falls with external capacitance [20] (**Cited**, not a neon lamp).

**Statistical and formative time lag, memory effect.** In neon-filled tubes (1–13 mbar, laboratory diodes, not NE-2 lamps):
- Breakdown voltage distributions depend on how long the tube rested since the last discharge (relaxation time τ, measured 0.1–100 s); the effective electron yield fell by one order of magnitude over that range [21] (**Cited**).
- For τ ≤ 0.1 s the formative time (~0.1 ms) dominates the total delay; for τ > 0.1 s the statistical delay dominates; the "memory curve" was measured for τ from 3 ms to 300 s [22] (**Cited**).
- The delay distribution is a convolution of exponential (statistical) and Gaussian (formative) parts; at overvoltages of a few percent the full convolution must be used [23][24] (**Cited**). At 10 mbar: Gaussian for τ < 15 ms, Weibull for 15–150 ms, exponential for τ > 150 ms [25] (**Cited**).
- The long memory is **not** explained by Ne metastables (quenched too fast); it is governed by decay of molecular ions, Ne₂⁺ and N₂⁺ from nitrogen impurities [26] (**Cited**). Cathode surface charges also change the delays [27] (**Cited**).
- **Inferred:** a relaxation oscillator firing every few ms sits inside the τ range where the firing delay depends on the previous interval. This is a physical fading-memory mechanism for a reservoir, but it is also a source of jitter. No source measured it in an NE-2.

**Dark effect, light sensitivity.** The glow-lamp catalogue [2] states that in a darkened environment "starting voltage sometimes rises", and that some types use a radioactive additive to reduce this (**Cited**). CML footnote 9 (for some high-brightness types) gives "Maximum breakdown voltage in total darkness 100VAC" [1] (**Cited**). Light modulates a neon relaxation oscillator's frequency enough to entrain it: chopped neon-resonant laser light locks the oscillator to the chopping frequency [14] (**Cited**).

**Ageing.** CML: "End of life occurs when breakdown voltage increases to line voltage and lamp will no longer start"; DC life is approx. 60% of AC life at equal currents [1] (**Cited**). The catalogue specifies, per type, the hours for a 5 V change in breakdown or maintaining voltage (e.g. NE-2AS: 2,500 h at 0.3 mA; NE-2L: 6,000 h) and a burn-in "Aging Procedure" of 100 h at design current or 24 h at 0.6 mA [2] (**Cited**).

**Temperature.** The catalogue says use of indicator lamps above 300 °F, and of circuit-component types outside −60 °F to +165 °F, is not recommended [2] (**Cited**). No peer-reviewed quantitative temperature coefficient of NE-2 breakdown voltage was found (**gap**).

**Lamp-to-lamp spread.** Only datasheet min/avg/max ranges were found: e.g. NE-2AS initial DC breakdown 60/76/90 V; NE-2L 65/73/85 V [2] (**Cited**). The NE-2L note says "Individual lots may vary from average" [2]. No peer-reviewed statistical study of NE-2 spread was found (**gap**).

**Surprise (Cited, [2]):** the manufacturer's selection table recommends NE-23 and NE-76 for sawtooth oscillators and NE-77/NE-96 for trigger circuits, not the NE-2 (an indicator lamp).

### NE-2 datasheet values found

Values copied exactly from the PDFs. "—" = not stated in that document.

| Manufacturer / source | Part | Breakdown (striking) V | Maintaining V | Current | URL |
|---|---|---|---|---|---|
| CML-IT, "Aviation Neon Lamps" / "Neon Indicator Lamps" [1] | A1A (NE-2) | Max. 65 VAC, 90 VDC | — | Design current max 0.6 mA; series R 100K 1/4 W (100–125 V), 540K 1/3 W (220–250 V); avg life 25,000 h | https://assets.rs-online.com/v1698855769/Datasheets/33c338a3395bf8a48766cf8b62fb2d18.pdf |
| CML-IT [1] | A9A (NE-2E) | 65 VAC, 90 VDC (max) | — | 0.7 mA | same |
| CML-IT [1] | C2A (NE-2H), high brightness | 95 VAC, 135 VDC (max) | — | 1.9 mA; "For DC operation of high brightness lamps use a minimum of 150 circuit volts" | same |
| "Glow Lamp Specifications" catalogue, manufacturer not named on the scanned pages [2] | A1A (NE-2) | — | — | Nominal current 0.5 mA; external R 150K at 105–125 V; life 25,000 h | https://w140.com/tekwiki/images/e/e6/Neon_lamp_specifications.pdf |
| same [2] | NE-2AS | Initial DC 60 min / 76 avg / 90 max (in 5–50 footcandles) | Initial DC 58 avg @ 0.3 mA | Design 0.3 mA; extinguishing voltage 50 min (0.25 MΩ or more series R) | same |
| same [2] | NE-2L | Initial DC 65 / 73* / 85 (in 5–50 fc) | >50* avg @ 0.3 mA (*after 100 h at design current) | Design 0.3 mA | same |
| San Guang (via search snippet only) | NE-2 family | 65 VAC max (snippet) | — | 0.5 mA, 100 KΩ (snippet) | https://taydaelectronics.com/datasheets/files/sg004.PDF — **not verified**: HTTP 403 |

No document found gives a maintaining voltage for the plain NE-2. VCC (Chicago Miniature) sheets on Mouser timed out and were not read.

## 2. Neon relaxation-oscillator dynamics

- **Van der Pol and van der Mark 1927** [3] (**Cited**, record verified: Nature 120, 363–364, doi:10.1038/120363a0): a neon-lamp RC relaxation oscillator driven sinusoidally produced responses at integer submultiples of the drive ("frequency demultiplication") and an "irregular noise" between locking regimes.
- **Kennedy and Chua 1986** [4] (**Cited**): experimental confirmation of the period-adding route to chaos in van der Pol's driven neon circuit; a three-segment PWL neon model reproduces it. (One repository lists a conference version, ISCAS pp. 70–73; the journal record is IEEE TCAS 33, 974–980.)
- **Pugliese et al. 2015** [6] (**Cited**): a commercial neon discharge tube shows period-doubling and quasiperiodic routes to chaos when circuit capacitance is varied. A model built from the measured V–I curve needs extra degrees of freedom to show chaos (a 2-D system cannot), and its stability diagrams show multistability.
- **Generic theory** (**Cited**): mode-locked intervals form a devil's staircase via circle maps; at the critical line the staircase is complete [7]. An exact analysis of a modulated (integrate-and-fire-type) relaxation oscillator gives phase-locked, quasiperiodic, chaotic and complete-phase-locking regimes [8]. Devil's staircase in a forced van der Pol relaxation oscillator, experimental [5]. A UJT relaxation oscillator with parasitic delay behaves like a 2-D leaky integrate-and-fire model and reaches chaos through torus breakdown [9].
- **Entrainment by light** [14] (**Cited**): see §1.
- **Noise in firing times** (**Cited**): Abidi and Meyer give a normalized theory of relaxation-oscillator timing jitter [10] (electronic, not neon). For neon, the breakdown-delay statistics in §1 [22]–[25] are the relevant jitter source. No paper measuring NE-2 oscillator period jitter was found (**gap**).
- **Inferred:** audio summed into the node acts as a forcing term on a relaxation oscillator, so the system will mode-lock to tonal components (Arnold tongues) and may go chaotic at large drive. Mode-locking is not wanted in a reservoir: inside a tongue the firing pattern stops depending on small input differences. Expect to need drive amplitudes well below the locking/chaos thresholds, and to measure them.

## 3. Gas discharge / plasma as a physical reservoir; neon as a neuron

- **No peer-reviewed work found that uses a plasma, glow discharge or neon lamp as a reservoir computer**, nor one using a neon lamp as an artificial neuron. Searches covered Consensus, alphaXiv and the web. Hits for "plasma reservoir computing" were reservoir computing used to *model* tokamak plasmas, O₂-plasma-treated memristors, or oil-reservoir stimulation. This is a key finding (**Cited absence**, limited to these searches).
- Reviews of physical RC cover electronic, photonic, spintronic, mechanical and other substrates, not gas discharges [28][29][30] (**Cited**).
- **Closest analogues** (**Cited**):
  - Two coupled VO₂ relaxation oscillators used as a reservoir via high-order synchronization (XOR task; inputs static or spike sequences) [31] (IOP Conf. Series).
  - A single van der Pol oscillator as a physical reservoir, built on a field-programmable analog array (logic tasks) [32].
  - LIF neuron circuits using threshold devices: an SCR-based ultra-compact LIF [33]; ZnO diffusive-memristor LIF/oscillation neurons [34].
  - A UJT relaxation oscillator mapped to a 2-D LIF model [9].
- **Inferred:** a Pearson–Anson neon oscillator is structurally a leaky integrate-and-fire unit (C integrates, Rs and lamp leakage set the leak, breakdown is the threshold, extinction is the reset). That analogy is mine; no peer-reviewed source states it for neon. Whether it computes as a reservoir is an **untested hypothesis**.

## 4. Single-node reservoirs, time-multiplexing, input encoding

- **Appeltant et al. 2011** [11] (**Cited**, verified Nat. Commun. 2, 468): one nonlinear node with delayed feedback replaces a network. Input is sample-and-held for one delay τ and multiplied by a random mask to give N virtual nodes spaced θ = τ/N. Spoken digits: τ = 80, N = 400, θ = 0.2 (in units of node time constant T), mask values 0.59, 0.41, 0. θ must be below the node's response time so that neighbouring virtual nodes couple; for θ > 3 performance drops to shift-register level. Electronic Mackey–Glass node (T = 10 ms) with digital delay loop, ADC/DAC.
- **Torrejon et al. 2017** [12] (**Cited**, Nature 547, 428–431): a single spin-torque nano-oscillator, time-multiplexed. Random binary mask, 400 virtual neurons; each masked value applied as a constant current for θ ≈ 100 ns, "about 5 times smaller than the relaxation time of the oscillator". The useful properties named are nonlinear amplitude response to current, memory from the relaxation time, and low noise.
- **Dambre et al. 2012** [13] (**Cited**): total information-processing capacity is bounded by the number of linearly independent state variables, and reaches the bound with fading memory; memory and nonlinearity trade off.
- **Derived for this circuit:** the published single-node schemes all feed the input through a mask at a rate faster than the node's relaxation time, and read many samples per input step. Summing raw audio into the node voltage (as planned) has **no mask and no defined virtual-node timing**. The closest equivalent would be: θ shorter than the RC recharge time and the deionisation time, and several ADC samples per firing interval. The UNO's ADC rate limits this; check it against the measured firing period.
- **Inferred:** the neon oscillator has no delay loop, so its only memory is (a) the capacitor charge state within one cycle and (b) the breakdown-delay memory of §1. Both reset or saturate quickly. Expect short memory capacity.

## 5. Readout and evaluation

- **Memory capacity.** Jaeger defined short-term memory capacity in GMD Report 152 [35] (technical report, not peer-reviewed; commonly dated 2002, not 2001). MC is bounded by reservoir size for linear reservoirs [36] (**Cited**). Numerical MC estimates can exceed theory for purely numerical reasons [37] (**Cited**; **[preprint, not peer-reviewed]** per the index; used only as a caution about computing MC).
- **Consistency.** Uchida, McAllister and Roy 2004 (PRL) is already reviewed in the repo (`research/lyapunov_consistency_experimental_design.md`); not repeated.
- **No-reservoir control baseline (strongly supported):**
  - Torrejon et al. ran the same preprocessed inputs straight to the trained readout, bypassing the oscillator. With spectrogram features, the no-oscillator rate was "consistent with random choices", and the oscillator added about 70% (up to 80%). With cochlear features the oscillator reached up to 99.6% and cut the error by up to 15×, but no absolute control rate is given [12] (**Cited**).
  - Abreu Araujo et al. 2020 show that nonlinearity in the acoustic preprocessing is essential to feature extraction. They propose the **gain over preprocessing alone** as the fair hardware benchmark [15] (**Cited**).
  - Hikasa et al. 2026 report four configurations including "baseline without PRC"; cochleagram alone gave about 90% [38] (**Cited**; venue not verified).
- **Derived:** every accuracy claim for the NE-2 must be paired with: (i) the same features through the same linear readout with the lamp removed or bypassed; (ii) the same with the lamp replaced by a linear RC; (iii) the input-only (photodiode reading the audio with no discharge) case. Without these, a result cannot show that the bulb computes.

## 6. Audio / spoken-word classification with physical reservoirs

| Ref | Substrate | Data / encoding | Result (as reported) |
|---|---|---|---|
| [11] | Electronic Mackey–Glass, delay | TI-46, 500 words, cochlear model, 86 channels, mask | WER 0.2% exp. |
| [12] | Spin-torque oscillator, 1 device | TI-46, spectrogram 65 ch or cochlear 78 ch, binary mask, 400 virtual neurons | up to 99.6% (cochlear) |
| [39] | WOx memristors | isolated spoken digits, partial inputs | 99.2% |
| [40] | Dynamic memristors, parallel | spoken digits, controllable mask | WER 0.4% |
| [41] | PEDOT:PSS colloid | audio encoded as spike sequences | "high accuracy" |
| [42] | Nanoparticle networks | spoken digits | "state-of-the-art" |
| [43] | Skyrmion reservoir | spoken digits, multidimensional input | 97.4% |
| [44] | Ion-gating reservoir + throat sensor | raw sensor voltage → pulse sequences, no spectral features | 96.8% |

- **Cited pattern:** nearly all high scores use cochleagram or spectrogram preprocessing in software, then a mask [11][12][15]. Raw-signal input without spectral features is rare and newer [44].
- **Inferred:** feeding raw laptop audio into the node is the hard (raw) case. Expect much lower accuracy than the table, and run the §5 controls first.

---

## 7. Discharge-physics simulators (search 2026-10-26: web, alphaXiv, Crossref)

No published simulation of an NE-2 (or any neon indicator lamp) in an external circuit with discharge physics was found (**gap**). Closest tools:

| Source | What it simulates | Fit to our bulb | Status |
|---|---|---|---|
| Yamashita, Hara & Sriraman 2024, *Phys. Plasmas* 31, 073510, doi:10.1063/5.0198151 | Hysteresis between Townsend breakdown and glow discharge (kinetic modelling) | Physics behind the switch model's V_b/V_e hysteresis (D-20) | **Cited** (Crossref-verified); content not yet read |
| Iqbal et al. 2026, PASCHEN-1D, arXiv:2608.07721 | 1D drift–diffusion–Poisson fluid + electrode emission + lumped R/L/C circuit (topologies incl. source R, series C, shunt C ≈ circuit A) | Validated for Ar and N2 only; authors state 1D gives no normal-glow plateau | **[preprint, not peer-reviewed]**; paper says open source, no repository link found |
| Zapdos (MOOSE), Comput. Phys. Commun. 2023, LGPL-2.1, github.com/shannon-lab/zapdos | Finite-element plasma fluid, DC kernels | General; no neon lamp case | open source |
| FEDM (FEniCS), *Plasma Sources Sci. Technol.* 2023, doi:10.1088/1361-6595/acc54b | 2D fluid, low-pressure Ar glow benchmark | General | open source |
| Donkó et al. 2021, eduPIC, *PSST* 30, 095017 | 1D PIC/MCC teaching code (RF) | Would need DC + circuit changes | GPL-3 |
| Frontiers in Physics 2021, doi:10.3389/fphy.2021.751335 | 2D COMSOL neon glow discharge | Neon, but no external circuit; commercial | not read in full |
| Stamenković et al., neon breakdown time-delay models (OSTI 21556538) | Statistical and formative breakdown delay in neon | Breakdown jitter / memory (§1 refs [21–25]) | not read in full |
| Marković, Gocić, Stamenković & Petrović 2007, *Phys. Plasmas* 14, 103504, doi:10.1063/1.2779279 | Neon 6.6 mbar: afterglow memory of breakdown delay; charged-particle decay over hundreds of ms; metastable hypothesis rejected | Form of Y(τ) in `bulb_model` | **Cited** (Crossref abstract); paywalled |
| Maluckov et al. 2004, *Phys. Plasmas* 11, 5328, doi:10.1063/1.1806478 | Neon 6.5 mbar: delay = exponential statistical + Gaussian formative (convolution model, 1000 measurements) | Delay distribution in `bulb_model` | **Cited** (abstract) |
| Pejović & Pejović 2008, *J. Vac. Sci. Technol. A* 26, 1326, doi:10.1116/1.2966435 | Argon 4 mbar: statistical delay negligible for afterglow 3–70 ms, Laue distribution beyond; total ≈ statistical | Laue form | **Cited** (abstract); argon |

## 8. IPC benchmarks, Lyapunov method, Teensy facts (search 2026-10-29: alphaXiv, Crossref, PJRC)

| Source | What it gives us | Status |
|---|---|---|
| Yamaguchi, Tsunegi, Nakajima, Taniguchi 2023, *Phys. Rev. B* 107, 054406, doi:10.1103/PhysRevB.107.054406 (arXiv 2302.03769) | Single spin-torque oscillator, time-multiplexed, N_node = 250, binary pulse input: maximum short-term memory capacity 4.02 (one setting) and 5.76 (best); MC maximal near the edge of the echo state property; notes that total IPC is bounded by the number of linearly independent outputs | **Cited** (arXiv full text read; venue Crossref-verified) |
| Akashi et al. 2020, *Phys. Rev. Research* 2, 043303, doi:10.1103/PhysRevResearch.2.043303 | IPC of spintronic reservoirs changes drastically across input-driven bifurcations | **Cited** (abstract only; numbers not read) |
| Kubota, Takahashi, Nakajima 2021, *Phys. Rev. Research* 3, 043135, doi:10.1103/PhysRevResearch.3.043135 | IPC framework for stochastically driven systems | record verified; not read |
| Furuta et al. 2018, *Phys. Rev. Applied* 10, 034063; Tsunegi et al. 2018, *Jpn. J. Appl. Phys.* 57, 120307 | Spin-torque reservoir memory capacity | records verified; not read |
| Harkhoe & Van der Sande 2019, *Photonics* 6, 124, doi:10.3390/photonics6040124 | Task-independent (IPC) analysis of delay-based semiconductor lasers | record verified; page returned 403, not read |
| Martínez-Peña et al. 2020, *Cognitive Computation*, doi:10.1007/s12559-020-09772-y | IPC of spin-based quantum reservoirs | record verified; not read |
| Abarbanel, Rulkov, Sushchik 1996, *Phys. Rev. E* 53, 4528, doi:10.1103/PhysRevE.53.4528 | Auxiliary-system method: a driven response copy started elsewhere converges iff generalized synchronization (conditional Lyapunov exponent < 0) | **Cited** (Crossref-verified; method standard) |
| Tanaka et al. 2019, *Neural Networks* 115, 100, doi:10.1016/j.neunet.2019.03.005; Nakajima 2020, *JJAP* 59, 060501, doi:10.35848/1347-4065/ab8d4f; Lukoševičius & Jaeger 2009, *Comput. Sci. Rev.* 3, 127, doi:10.1016/j.cosrev.2009.03.005 | Reviews / introductions for physical RC and ESNs | records verified (learning resources) |
| PJRC Teensy 4.1 page, https://www.pjrc.com/store/teensy41.html; PWM page, https://www.pjrc.com/teensy/td_pulse.html | 3.3 V pins, not 5 V tolerant; analog 0–3.3 V, up to 12 bit, "only up to 10 bits are normally usable due to noise"; no DAC (MQS, audio shield); 8-bit ideal PWM at 600 MHz = 585937.5 Hz | **Cited** (manufacturer documentation, read 2026-10-29) |

**Gap:** no peer-reviewed IPC value for a single threshold/relaxation device (neon, UJT, SCR) was found; the comparison in sim_experiments §3 therefore uses the Dambre bound and a spin-torque oscillator.

## Implications for the schematic

| Design choice | Status | Basis |
|---|---|---|
| Neon lamp + C + Rs from DC = relaxation oscillator | **Supported** as a circuit (Pearson–Anson, two critical voltages) | [16][17][3][4] |
| Using that oscillator as a *reservoir* | **Unsupported**: no peer-reviewed plasma/neon reservoir found; untested hypothesis | §3 |
| Audio summed into the node as a forcing term | **Supported** that forcing modulates/entrains firing; **risk**: mode-locking and chaos are documented for exactly this circuit | [3][4][6][8][14] |
| ~90 V DC supply for an NE-2 | **Contradicted / marginal**: CML max DC striking is 90 VDC and the catalogue NE-2AS max breakdown is 90 V. A 90 V supply cannot fire every lamp, and the dark effect raises breakdown. Need headroom (**Derived**) | [1][2] |
| Lamp in a dark enclosure for the photodiode | **Risk**: the dark effect raises starting voltage, and external light changes firing. Shield from stray light, but keep the light level constant, and log it | [2][14] |
| Rs value | Datasheets give 100K–150K for 105–125 V *indicator* use at 0.5–0.6 mA. For an oscillator, Rs must be large enough that the lamp extinguishes (catalogue extinguishing test uses ≥0.25 MΩ) (**Derived**) | [1][2] |
| Photodiode as main readout | **Partly supported**: light output follows discharge; no source on NE-2 optical bandwidth (**gap**) | — |
| Low-side current-sense resistor | No literature-specific objection (**Inferred**) | — |
| Single node with no mask / delay loop | **Unsupported by single-node RC literature**, which relies on a mask, θ below node time, and sampling many virtual nodes per step | [11][12] |
| Fading memory from breakdown-delay statistics | **Plausible** (memory curve, ms–s timescale), but measured only in lab neon diodes, not NE-2s | [21]–[26] |
| Lamp burn-in before experiments | **Supported**: manufacturer burn-in procedure; voltages drift by a few V over thousands of hours | [1][2] |
| Control baselines (no lamp, linear RC, input only) | **Required** by the literature | [12][15][38] |
| Lamp-to-lamp and temperature spread | **Gap**: datasheet ranges only; measure several lamps and log temperature | [1][2] |

---

## References

1. CML Innovative Technologies (CML-IT). "Aviation Neon Lamps" / "Neon Indicator Lamps" datasheet (RS Components host), n.d. https://assets.rs-online.com/v1698855769/Datasheets/33c338a3395bf8a48766cf8b62fb2d18.pdf
2. "Glow Lamp Specifications" catalogue (scanned; manufacturer not named on the pages read; hosted by TekWiki, uploaded 2023). https://w140.com/tekwiki/images/e/e6/Neon_lamp_specifications.pdf
3. van der Pol, B., van der Mark, J. (1927). Frequency demultiplication. *Nature* 120, 363–364. https://doi.org/10.1038/120363a0
4. Kennedy, M. P., Chua, L. O. (1986). Van der Pol and chaos. *IEEE Trans. Circuits and Systems* 33, 974–980. https://consensus.app/papers/details/ee70da03fc6e5cacb3fd402a63d7daa3/ ; tech. report https://www2.eecs.berkeley.edu/Pubs/TechRpts/1985/ERL-85-97.pdf
5. Gilbert, T., et al. (2000). Stable oscillations and devil's staircase in the van der Pol oscillator. *Int. J. Bifurcation and Chaos*. https://consensus.app/papers/details/1dbd8532f704513aa9a81741b52a6f36/
6. Pugliese, E., Meucci, R., Euzzor, S., Freire, J. G., Gallas, J. A. C. (2015). Complex dynamics of a dc glow discharge tube: experimental modeling and stability diagrams. *Scientific Reports* 5, 8447. https://doi.org/10.1038/srep08447
7. Bak, P., et al. (1985). Mode-locking and the transition to chaos in dissipative systems. *Physica Scripta*. https://consensus.app/papers/details/4f7b8ae79f32550d9edae735a5081c5f/
8. Christiansen, B., et al. (1990). Routes to chaos and complete phase locking in modulated relaxation oscillators. *Phys. Rev. A*. https://consensus.app/papers/details/7f10bd91a1665835ba40467c28ae5f5b/
9. Di Garbo, A., et al. (2019). Delayed dynamics in an electronic relaxation oscillator. *Phys. Rev. E*. https://consensus.app/papers/details/1d84a60339f05c25b71b025d3cfbb388/
10. Abidi, A., et al. (1983). Noise in relaxation oscillators. *IEEE J. Solid-State Circuits*. https://consensus.app/papers/details/282dc3f97a135a5fa2b0102f68def555/
11. Appeltant, L., Soriano, M. C., Van der Sande, G., Danckaert, J., Massar, S., Dambre, J., Schrauwen, B., Mirasso, C. R., Fischer, I. (2011). Information processing using a single dynamical node as complex system. *Nature Communications* 2, 468. https://doi.org/10.1038/ncomms1476 (PMC3195233)
12. Torrejon, J., et al. (2017). Neuromorphic computing with nanoscale spintronic oscillators. *Nature* 547, 428–431. https://doi.org/10.1038/nature23011 (PMC5575904)
13. Dambre, J., Verstraeten, D., Schrauwen, B., Massar, S. (2012). Information processing capacity of dynamical systems. *Scientific Reports* 2, 514. https://doi.org/10.1038/srep00514
14. Koepke, M. (as indexed; full author list not verified, MDPI page returned 403) (2024). Detection of optogalvanic spectra using driven quasi-periodic oscillator dynamics. *Atoms* 12(8), 42. https://www.mdpi.com/2218-2004/12/8/42
15. Abreu Araujo, F., et al. (2020). Role of non-linear data processing on speech recognition task in the framework of reservoir computing. *Scientific Reports* 10, 328. https://doi.org/10.1038/s41598-019-56991-x
16. Pearson, S. O., Anson, H. St. G. (1921). The neon tube as a means of producing intermittent currents. *Proc. Physical Society of London* 34(1), 204–212. https://doi.org/10.1088/1478-7814/34/1/341 (record only; full text not read)
17. Paranjpé, G., et al. (1928). A new type of low frequency low voltage discharge in a neon lamp. *Nature*. https://consensus.app/papers/details/dbd6814945925922a4b2653478e72f41/
18. Yamashita, Y., et al. (2024). Hysteresis between gas breakdown and plasma discharge. *Physics of Plasmas*. https://consensus.app/papers/details/7705d68adf1e541ab25b360c36fa1b79/
19. Mizuno, N., et al. (2003). Simulation of hysteresis in glow discharge. Venue not verified. https://consensus.app/papers/details/c32c9262e7c95deb8d532f3f60d68ee2/
20. He, S.-J., et al. (2020). Experiment and simulation of the characteristics and mechanisms of self-oscillations in parallel-plate glow discharges. *J. Applied Physics*. https://consensus.app/papers/details/b9dac6ccccb9529fa297be008f451fe9/
21. Maluckov, C., et al. (2002). Breakdown-voltage memory effect in a neon-filled diode at 1 mbar. *IEEE Trans. Plasma Science*. https://consensus.app/papers/details/e6bdc2ea0aca53a0b82c7044e5c52fa1/
22. Spasić, I., et al. (2003). The statistical time-delay and the breakdown formative time contributions to the memory effect in Ne at 7 mbar pressure. *J. Phys. D*. https://consensus.app/papers/details/8fe89a8366b855e6ae4902eee502a9e6/
23. Maluckov, C., et al. (2003). Statistical analysis of electrical breakdown time delay distributions in neon tube at 13.3 mbar. *IEEE Trans. Plasma Science*. https://consensus.app/papers/details/77473206583957c496fd058fd4aa3bb1/
24. Radović, M. (2005). Investigation of the influence of overvoltage, auxiliary glow current and relaxation time on the electrical breakdown time delay distributions in neon. *Contributions to Plasma Physics*. https://consensus.app/papers/details/82bcd42ed1a35e4fa9621896b92bceca/
25. Maluckov, C., et al. (2016). Breakdown in low pressure Ne gas: mechanisms and statistical analysis of time delay. *IEEE Trans. Dielectrics and Electrical Insulation*. https://consensus.app/papers/details/04c089b3065b5fccad31c339e1e4ccdc/
26. Marković, V., et al. (2007). Metastable and charged particle decay in neon afterglow studied by the breakdown time delay measurements. *Physics of Plasmas*. https://consensus.app/papers/details/3f3b0f1831fe544db84718fcd7592582/
27. Stamenković, S., et al. (2013). Influence of different cathode surfaces on the breakdown time delay in neon DC glow discharge. *Vacuum*. https://consensus.app/papers/details/525d866f673e5d4993e32836f00fc976/
28. Tanaka, G., et al. (2019). Recent advances in physical reservoir computing: a review. *Neural Networks*. https://consensus.app/papers/details/e38e809132515dd1a066ec1849a6a223/
29. Liang, X., et al. (2024). Physical reservoir computing with emerging electronics. *Nature Electronics*. https://consensus.app/papers/details/9bdfec774ca85461a65e20ece74cb528/
30. Stepney, S. (2024). Physical reservoir computing: a tutorial. *Natural Computing*. https://consensus.app/papers/details/600d5959b4a95e4398d965e80e769b00/
31. Velichko, A., et al. (2020). Reservoir computing using high order synchronization of coupled oscillators. *IOP Conf. Series: Materials Science and Engineering*. https://consensus.app/papers/details/b8ce54d043985c51a17089d3bea1cc7d/
32. Shougat, M. R. E. U., et al. (2023). The van der Pol physical reservoir computer. *Neuromorphic Computing and Engineering*. https://consensus.app/papers/details/314ba8daa77351e5a012e630bc12031d/
33. Rozenberg, M., et al. (2019). An ultra-compact leaky-integrate-and-fire model for building spiking neural networks. *Scientific Reports*. https://consensus.app/papers/details/88f0aaceaa9c5769bca0721cdd8168c9/
34. Wang, L., et al. (2025). Leaky integrate-and-fire and oscillation neurons based on ZnO diffusive memristors for spiking neural networks. *Science China Materials*. https://consensus.app/papers/details/3624f8d61858590b8ce787e5c6effc20/
35. Jaeger, H. (2002). Short term memory in echo state networks. GMD Report 152, German National Research Center for Information Technology. Technical report, not peer-reviewed; cited for the MC definition. Record: https://publica.fraunhofer.de/handle/publica/291111
36. Farkaš, I., et al. (2016). Computational analysis of memory capacity in echo state networks. *Neural Networks*. https://consensus.app/papers/details/6c49194f52ee5691b130d391901da27a/
37. Ballarin, G., et al. (2023). Memory of recurrent networks: do we compute it right? arXiv **[preprint, not peer-reviewed]**. https://consensus.app/papers/details/b0420dc8cd1d5c3cb36af3ef4b3155b6/
38. Hikasa, S., et al. (2026). Spoken digit recognition and speaker classification by nonlinear interfered spin wave-based physical reservoir computing. Venue not verified. https://consensus.app/papers/details/a534a29a9c5b5723982395bce0452157/
39. Moon, J., et al. (2019). Temporal data classification and forecasting using a memristor-based reservoir computing system. *Nature Electronics*. https://consensus.app/papers/details/b76382b3dc245e9dafebc852fef91b62/
40. Zhong, Y., et al. (2021). Dynamic memristor-based reservoir computing for high-efficiency temporal signal processing. *Nature Communications*. https://consensus.app/papers/details/59fff2caa0335276aa1f7c8ab3ff4717/
41. Fortulan, R., et al. (2024). Achieving liquid processors by colloidal suspensions for reservoir computing. *Communications Materials*. https://consensus.app/papers/details/0d75b1f43ee2571787da32b958c2d708/
42. Mallinson, J., et al. (2024). Experimental demonstration of reservoir computing with self-assembled percolating networks of nanoparticles. *Advanced Materials*. https://consensus.app/papers/details/25558629b74d57ceb06d2411a8e599e7/
43. Msiska, R., et al. (2022). Audio classification with skyrmion reservoirs. *Advanced Intelligent Systems*. https://consensus.app/papers/details/eff0734e661b59098ef802a6cc5bc1e5/
44. Nishioka, D., et al. (2026). Ion-gating reservoir computing for preprocessing-free speech recognition from throat vibrations. *Advanced Electronic Materials*. https://consensus.app/papers/details/724b513a05bb5668a97e44201cd43288/
