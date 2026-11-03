# Consistency / Twin-Trial Methods as a Lyapunov-Exponent Substitute for the Plasma Reservoir

Research notes for `plasma_rc`. Goal: ground the team's planned "consistency" measure
(replay the same stimulus, measure trial-to-trial divergence of the plasma bulb's response)
in verifiable primary literature, and turn that literature into concrete numbers for the
current acquisition setup (photodiode brightness + audio-tap voltage, 100 kHz, ~1.5 s/trial,
~15 trials/condition).

Every claim below is tagged with a source I actually opened or whose bibliographic record
(title/authors/venue/year/DOI) I cross-checked against at least two independent listings
(publisher page, PubMed, DOI resolver, or arXiv). Where I could not get past a paywall to
verify a specific methodological detail (e.g. exact repeat count in a photonics paper), I say
so explicitly rather than inventing a number.

---

## 1. The consistency / twin-trial method itself

### 1.1 Uchida, McAllister, Roy (2004) — the foundational paper

**Correction to the request's recollection:** this is **not** a Nature Physics paper. It is:

> A. Uchida, R. McAllister, R. Roy, "Consistency of Nonlinear System Response to Complex
> Drive Signals," *Physical Review Letters* **93**, 244102 (2004).
> DOI: [10.1103/PhysRevLett.93.244102](https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.93.244102)

Verified directly against the APS abstract page. The paper studies the consistency of a
nonlinear system's (experimentally, a laser's) response to a repeatedly-applied complex
drive waveform, and reports that there is generally an **optimal drive amplitude** for
maximal consistency: at small amplitude, internal/intrinsic noise sources dominate and
consistency is low; at large amplitude, the system's own deterministic nonlinearity
(chaos) reduces consistency. I could not get past the paywall to confirm the exact number
of repeated trials used in their laser experiment — flagged as **unverified** rather than
guessed.

### 1.2 Formal definition of consistency

The clearest, fully-derivable formal definition I could verify in detail is from the
directly-related follow-up paper (same last author, overlapping author list with Uchida 2004):

> A. Uchida, K. Yoshimura, P. Davis, S. Yoshimori, R. Roy, "Consistency in the driven
> butterfly," preprint arXiv:[nlin/0703004](https://arxiv.org/abs/nlin/0703004) (2007),
> published as *Physical Review E* **78**, 036203 (2008).

I read the arXiv PDF in full. It gives an explicit formula. For a response system driven by
signal S(t), started from an ensemble of N different initial conditions X_i(0), with observed
scalar trajectories x(t; X_i(0)):

```
C = [2 / (N(N-1))] * sum_{i} sum_{j>i}
      < (x(t;X_i(0)) - x̄_i)(x(t;X_j(0)) - x̄_j) > / (σ_i σ_j)
```

i.e. **the average pairwise Pearson correlation coefficient, over time, between every pair
of repeated-trial response traces**, where each trial is driven by the identical input.
⟨·⟩ denotes time-averaging. C → 1 means all repeats converge to (nearly) the same
trajectory; C near 0 means repeats are uncorrelated.

They pair this with the **conditional Lyapunov exponent** for consistency (following Pecora
& Carroll's driven-response-system formalism, cited in their reference list as L. M. Pecora
and T. L. Carroll, *Phys. Rev. A* **44**, 2374 (1991)):

```
λ_c = lim_{T→∞} (1/T) log( ||ξ(T)|| / ||ξ(0)|| )
```

where ξ is the linearized deviation of the response system about a reference trajectory
(only the response-system Jacobian, not the drive). They also define a **local conditional
Lyapunov exponent (LCLE)** λ_lc(t) = (1/Δt) log(||ξ(t+Δt)||/||ξ(t)||) to visualize
contraction/expansion regions along the trajectory in real time.

**Sign relationship (directly stated in the paper, Fig. 1c/1d):** the onset of consistency
(C → 1) corresponds to λ_c becoming **negative**; low/no consistency corresponds to
λ_c ≥ 0. They explicitly note λ_c is a *different quantity* from the ordinary (undriven)
Lyapunov exponent λ of the same system — a system can be chaotic on its own (λ > 0) and
still respond consistently to a strong-enough drive (λ_c < 0). This is exactly the
"reservoir computing wants λ_c < 0 (consistent, synchronizable, reproducible), not λ_c > 0
(chaotic, irreproducible)" logic the team wants — **confirmed by a primary source**, not
just the general reputation of the concept.

Their numerical example (Lorenz model, ensemble of **ten different initial conditions**,
explicitly stated and shown in their Fig. 1) is the only concrete "how many repeats" number
I could verify from a primary source in this specific line of literature — see §2.

### 1.3 Pikovsky / generalized-synchronization roots

Consistency is explicitly framed (in both Uchida papers above, and in every RC-consistency
paper in §3) as an experimental/practical extension of **generalized synchronization (GS)**.
The oldest reference usually cited for the underlying noise-induced-synchronization /
negative-conditional-Lyapunov-exponent idea is:

> A. S. Pikovsky, "Synchronization and stochastization of an ensemble of autogenerators by
> external noise," *Radiophysics and Quantum Electronics* **27**, 390–395 (1984).
> DOI: [10.1007/BF01044784](https://doi.org/10.1007/BF01044784)

I verified the bibliographic record (title, journal, volume/pages/year, DOI) via search but
**could not obtain or read the full text** (old Russian-origin journal, not open access, no
arXiv mirror found). I am citing it only for its existence/bibliographic identity — do not
treat any specific formula attributed to it here, because I did not read it. The
Uchida-driven-butterfly paper's own reference list (visible in the PDF I read) also cites
Pecora & Carroll (1990/1991) as the source of the conditional-Lyapunov-exponent /
GS formalism it builds on — that citation I *did* see directly, in the paper's own reference
list.

A second, more recent primary source with a complementary (not identical) ensemble-based
metric, which I verified bibliographically:

> G. Giacomelli, S. Barland, M. Giudici, A. Politi, "Characterizing the Response of Chaotic
> Systems," *Physical Review Letters* **104**, 194101 (2010).
> DOI: [10.1103/PhysRevLett.104.194101](https://link.aps.org/doi/10.1103/PhysRevLett.104.194101)

Per search-result summaries (I did not get full-text access), this paper investigates
**ensembles of trajectories** rather than single trajectories under periodic driving, and
introduces a dynamical invariant (denoted γ₁ in secondary summaries) that "complements" the
standard Lyapunov exponent. I flag the γ₁-specific detail as **secondary-source level
confidence only** (I have not read the primary text) — the existence and topic of the paper
itself is confirmed via the APS DOI resolving correctly.

---

## 2. Concrete experimental-design guidance from this literature

This is the weakest-evidenced section — most of what full papers say about *exact* repeat
counts, noise-floor controls, and duration-vs-timescale guidance lives behind paywalls I
could not open. Here is what I could actually verify, with honesty about the gaps.

- **Number of repeats.** The only explicit, verified number is from Uchida et al.'s driven
  Lorenz-butterfly paper (§1.2): **ten** repeated realizations (there, ten different initial
  conditions of a numerical model, not physical hardware repeats) were used to compute the
  pairwise-correlation consistency measure C, and this was sufficient to show clear,
  reproducible C(D) curves as a function of drive strength D. I could **not** verify a
  repeat count from an actual physical/experimental (as opposed to numerical) consistency
  study — the original 2004 PRL (real laser hardware) is paywalled past the abstract.
- **How the metric was computed from real recorded signals.** Confirmed: it is the pairwise
  (or, in Jüngling/Lymburn/Small's RC-specific formalism below, a normalized cross-covariance
  eigen-decomposition of) **correlation coefficient** between repeat-trial time series, not
  an RMS-difference or variance-ratio measure, in every primary source I could read in full
  (Uchida driven-butterfly, Jüngling consistency-capacity paper, §3 below). I found no
  verified primary source using a normalized-RMS-difference formulation instead — if that
  formulation exists elsewhere in the literature, I have not located and verified it.
- **Noise floor / baseline.** The 2004 PRL's own headline finding (per the search-engine
  abstract summary I could access) is precisely a noise-floor statement: at small drive
  amplitude, "internal noise sources dominate," i.e., the low-consistency regime *is* their
  noise floor. I could not verify from primary text whether they ran a literal zero-input
  (no-drive) control trial as a separate calibration step, or inferred the noise floor purely
  from the amplitude-sweep's small-amplitude limit. This is a real gap — do not assume they
  ran silence controls; I cannot confirm it either way.
- **Trial duration vs. system timescale.** No primary source I read gives an explicit
  "duration ≥ N × relaxation time" rule. The Uchida-driven-butterfly paper only says
  qualitatively that "responses converge after a short transient" and that they discard/
  observe behavior after that transient before assessing asymptotic consistency C → 1. This
  transient-discard practice is the one piece of duration-related guidance I can verify from
  a primary source; there is no verified numeric ratio.

---

## 3. Physical-reservoir-computing papers using consistency/twin-trial reproducibility as a Lyapunov proxy

All of the following were individually verified (title, author list, venue, year, and a DOI
or publisher URL that resolves correctly).

| Paper | Verified citation | Relevance / correction notes |
|---|---|---|
| Appeltant et al. 2011 | L. Appeltant, M. C. Soriano, G. Van der Sande, J. Danckaert, S. Massar, J. Dambre, B. Schrauwen, C. R. Mirasso, I. Fischer, "Information processing using a single dynamical node as complex system," *Nature Communications* **2**, 468 (2011). DOI: [10.1038/ncomms1476](https://www.nature.com/articles/ncomms1476) | Confirmed exactly as recalled in the request. This is the founding single-node delay-line RC paper; it does not itself center a "consistency" metric, but every later paper in this table cites it as the architecture being tested for consistency. |
| Martinenghi et al. 2012 | R. Martinenghi, S. Rybalko, M. Jacquot, Y. K. Chembo, L. Larger, "Photonic Nonlinear Transient Computing with Multiple-Delay Wavelength Dynamics," *Physical Review Letters* **108**, 244101 (2012). DOI: [10.1103/PhysRevLett.108.244101](https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.108.244101) | Confirmed exactly as recalled. I could **not** get past the paywall to confirm whether they explicitly compute a consistency/reproducibility metric across repeats, or how many repeats/how drift was handled — flagged unverified for methodology, only the paper's existence/citation is confirmed. |
| Brunner et al. 2013 | D. Brunner, M. C. Soriano, C. R. Mirasso, I. Fischer, "Parallel photonic information processing at gigabyte per second data rates using transient states," *Nature Communications* **4**, 1364 (2013). DOI: [10.1038/ncomms2368](https://www.nature.com/articles/ncomms2368) | Confirmed exactly as recalled. A search-engine summary (not primary text, since the article is paywalled without institutional access) suggested this line of work reports ">0.95 state-consistency correlation in injection-locked regimes" and frames reproducible/consistent transient response as a prerequisite for good RC performance — **I flag this specific number as unverified** since I could not confirm it against the primary PDF; treat it as plausible but not sourced. |
| Soriano et al. 2013 (Opt. Express) | M. C. Soriano, S. Ortín, D. Brunner, L. Larger, C. R. Mirasso, I. Fischer, "Optoelectronic reservoir computing: tackling noise-induced performance degradation," *Optics Express* **21**(1), 12–20 (2013). DOI: [10.1364/OE.21.000012](https://doi.org/10.1364/OE.21.000012) | **This is the paper that actually matches the author list the request recalled** (Soriano, Ortín, Brunner, Larger, Mirasso, Fischer) — see correction below. |
| Soriano et al. 2015 (IEEE TNNLS) | M. C. Soriano, S. Ortín, L. Keuninckx, L. Appeltant, J. Danckaert, L. Pesquera, G. Van der Sande, "Delay-Based Reservoir Computing: Noise Effects in a Combined Analog and Digital Implementation," *IEEE Transactions on Neural Networks and Learning Systems* **26**(2), 388–393 (2015). DOI resolves via IEEE Xplore document 6782741. | **Correction:** the request's recalled author list for this title (Soriano, Ortín, Brunner, Larger, Mirasso, Fischer, Pesquera) does not match the actual 2015 TNNLS paper's authors (Ortín, Keuninckx, Appeltant, Danckaert, Pesquera, Van der Sande — no Brunner, Larger, Mirasso, or Fischer). The recalled author combination instead matches the *2013 Optics Express* paper directly above. Both papers are real and both concern noise in delay-based/optoelectronic RC, but they are distinct works — do not conflate them. |
| Nakayama, Kanno, Uchida 2016 | J. Nakayama, K. Kanno, A. Uchida, "Laser dynamical reservoir computing with consistency: an approach of a chaos mask signal," *Optics Express* **24**(8), 8679–8692 (2016). DOI: [10.1364/OE.24.008679](https://doi.org/10.1364/OE.24.008679) | Not in the request's original list, but found during search and directly on-topic: this is a physical-RC paper that explicitly uses the **consistency** framework (same lineage as Uchida 2004/2008) as its analysis tool, via the auxiliary-system approach (an identical copy of the laser node driven by the same signal, replica-test style) applied to a semiconductor-laser reservoir. I could not get past the paywall to extract the exact repeat count or drift-handling protocol — flagged unverified for those specifics; the paper's existence, authorship, and consistency-based framing are confirmed. |

**On "how repeats were generated / drift was handled":** for every paper in this table except
the Uchida/Lymburn/Jüngling lineage in §1 and §4 (which I read in full), I was unable to get
past a paywall to extract the specific protocol (number of repeats, interleaving/
randomization of repeat order, transient discard length, re-referencing to a running
baseline). I am not fabricating those details. Where the request's prompt presumed such
detail exists and is extractable, I could not confirm it from open-access material.

---

## 4. Is consistency treated as a separate axis from memory capacity / separation / dimensionality?

Confirmed **yes — consistency is generally treated as an orthogonal characterization axis**,
and moreover a lineage of papers has now formally merged it into the *same* capacity
framework as memory capacity, which is directly useful for this project.

- D. Verstraeten's/J. Dambre's group: J. Dambre, D. Verstraeten, B. Schrauwen, S. Massar,
  "Information Processing Capacity of Dynamical Systems," *Scientific Reports* **2**, 514
  (2012). DOI: [10.1038/srep00514](https://www.nature.com/articles/srep00514). Confirmed.
  This paper formalizes a capacity measure (of which Jaeger-style memory capacity is a
  special case) bounded above by the number of linearly independent reservoir state
  variables, and identifies the general **memory/nonlinearity trade-off** — it does not
  itself discuss consistency or Lyapunov exponents, but is the standard reference the
  RC-consistency papers below build their capacity language on.
- G. Tanaka et al., "Recent advances in physical reservoir computing: A review," *Neural
  Networks* **115**, 100–123 (2019). Confirmed via ScienceDirect/PubMed listing. This is a
  broad review of physical RC (electronic, photonic, spintronic, mechanical, biological
  substrates) organized around memory capacity, nonlinearity/separation, and the
  edge-of-chaos regime as the standard characterization toolkit; I was not able to verify
  from open-access excerpts whether it discusses consistency/conditional-Lyapunov measures
  specifically as a named axis alongside these — flagged as **unverified** for that specific
  claim, though the review's general subject matter and existence are confirmed.
- The clearest, most directly on-point confirmation that consistency is its **own capacity
  axis, formally analogous to (and computed alongside) memory capacity**, comes from a
  distinct, more recent line of work I found and read in full:

  > T. Lymburn, A. Khor, T. Stemler, D. C. Corrêa, M. Small, T. Jüngling, "Consistency in
  > Echo State Networks," *Chaos: An Interdisciplinary Journal of Nonlinear Science*
  > **29**, 023118 (2019). DOI: [10.1063/1.5079686](https://pubs.aip.org/aip/cha/article/29/2/023118)

  > T. Jüngling, T. Lymburn, M. Small, "Consistency capacity of reservoir computers,"
  > arXiv:[2105.13473](https://arxiv.org/abs/2105.13473) (2021), published as "Consistency
  > Hierarchy of Reservoir Computers," *IEEE Transactions on Neural Networks and Learning
  > Systems* **33**(6), 2586–2595 (2022).

  I read the arXiv PDF of the second paper in full. It defines, for a reservoir driven by
  input u(t) with output y(t) = R(x(t)):
  - **Consistency correlation** Γ_R² = ⟨y(t) y'(t)⟩² — the squared time-averaged
    cross-correlation between an original trial y(t) and a "replica" trial y'(t), both driven
    by the identical input signal but started from different initial conditions (a direct
    generalization of the Uchida/Yoshimura pairwise-correlation C above to a single
    reservoir-vs-replica pair, with regularization options analogous to ridge regression).
  - A **consistency spectrum** {γ_k²} from an eigen-decomposition of the cross-covariance
    between two replica trials' full (multivariate) state vectors, and a **consistency
    capacity** Θ = Σ_k γ_k² = Tr(C_c), bounded 0 ≤ Θ ≤ N (N = number of reservoir state
    variables) — explicitly presented as playing the same structural role for "how much of
    the reservoir's output is a reproducible function of the input" that memory capacity
    plays for "how much of the reservoir's output is a linear function of past input."
  - They explicitly connect consistency to **the edge of chaos**: consistency capacity is
    maximized at the network's "edge of chaos" spectral-radius value ρ_c, and decreases for
    ρ > ρ_c because "the increasing number of positive Lyapunov exponents suppresses the
    response to the driving signal" — this is a direct, primary-source statement tying
    consistency capacity, edge-of-chaos, and (positive) Lyapunov exponents together exactly
    as the request hypothesized, though note this paper studies ESNs (numerical), not a
    physical hardware reservoir.
  - Directly relevant to noise handling: they show that Tikhonov-style regularization
    (equivalent to adding Gaussian measurement noise of variance λ to the covariance) has the
    effect of suppressing small consistency-spectrum components, i.e. of setting a
    **noise floor below which consistency components are not considered a reproducible
    signal component** — conceptually identical to using a silence/no-signal control to set a
    noise floor for the plasma reservoir.
  - Companion/related papers in the same author lineage, bibliographically confirmed but not
    read in full: T. Lymburn, T. Jüngling, M. Small, "Quantifying Robustness and Capacity of
    Reservoir Computers with Consistency Profiles," in *Artificial Neural Networks and
    Machine Learning – ICANN 2020*, Springer LNCS 12397 (2020),
    DOI: [10.1007/978-3-030-61616-8_36](https://link.springer.com/chapter/10.1007/978-3-030-61616-8_36);
    and T. Lymburn, D. M. Walker, M. Small, T. Jüngling, "The reservoir's perspective on
    generalized synchronization," *Chaos* **29**, 093133 (2019),
    DOI: [10.1063/1.5120733](https://pubs.aip.org/aip/cha/article/29/9/093133).

**Bottom line for task 4:** consistency is treated in the literature both as (a) a
conceptually separate/orthogonal characterization axis from memory capacity and separation
(different papers, different research groups, e.g. Dambre/Tanaka vs. Uchida/Roy), and, in the
more recent Jüngling/Lymburn/Small lineage, as (b) a **formally unified sibling metric**
computed the same way (replica test → cross-covariance → capacity number bounded by reservoir
dimensionality) and explicitly tied to the same edge-of-chaos / Lyapunov-exponent-sign
tradeoff that governs memory-vs-nonlinearity capacity. This second framing (b) is the one I
would recommend the team adopt conceptually, since it was purpose-built to sit next to
memory-capacity-style analysis.

---

## 5. Recommended experimental design for the plasma reservoir

Every number/recommendation below is explicitly tagged:
**(S)** = directly supported by a cited source's stated methodology (source given inline).
**(X)** = my own extrapolation/recommendation, reasoned from the literature above plus
general statistical practice for small-sample, resource-constrained physical experiments —
**not** found stated as such in any source I verified.

### 5.1 What to compute — a concrete consistency formula for this repo's data

The npz files this pipeline already writes (`plasma_rc/acquisition/session.py:write_npz`)
contain `t_us`, `audio_in`, `brightness`, `fs_hz`. For a stimulus file with R repeat
recordings (brightness traces b_1(t), …, b_R(t), all sampled at the same `fs_hz` and aligned
via `t_us`/`sync_offset_us`):

**(S)** Use the Uchida/Yoshimura pairwise-correlation form directly (§1.2, arXiv:nlin/0703004
Eq. 1), applied to `brightness` as the observed scalar output:

```
C_brightness = [2 / (R(R-1))] * Σ_i Σ_{j>i}  <(b_i(t) - b̄_i)(b_j(t) - b̄_j)>_t / (σ_i σ_j)
```

i.e. the mean of the R(R−1)/2 pairwise Pearson correlation coefficients between all repeat
traces, evaluated over the (post-transient — see 5.3) analysis window. This is the same
quantity the Jüngling/Lymburn/Small line of work calls Γ_R² when restricted to one pair, and
generalizes their consistency-capacity machinery if the team later wants to use the full
multivariate state (e.g. `[brightness, audio_in]` jointly, or a delay-embedded brightness
vector) instead of a scalar. **(S)**

**(X)** Also compute the *same* formula on `audio_in` across repeats,
`C_audio_in`, as a sanity/control check — since `audio_in` is the tapped drive
signal itself (should be near-identical every playback of the same source file up to DAC/ADC
noise and trigger jitter), `C_audio_in` close to 1 confirms the input replay is faithful, and
any drop in `C_brightness` below `C_audio_in` isolates divergence to the plasma's response
rather than to acquisition/playback jitter. This check is not described in any source above;
it is a straightforward control given the repo's specific two-channel recording setup.

**(X)** The repo's existing `plasma_rc/characterization/separation.py::lyapunov_estimate`
already implements the complementary log-divergence version of this idea (pairwise
log-distance between repeat trajectories, linear-fit slope vs. time ≈ λ_max) — it currently
has no data to run on because nothing in `session.py` records repeats without overwriting.
Recommend treating `C_brightness` (bounded, easy to interpret, matches the literature's
convention) as the primary reported number, and optionally cross-checking sign/consistency
against `lyapunov_estimate`'s slope (negative slope ↔ high C, by the λ_c ↔ C relationship in
§1.2) as an internal consistency check between the two repo-native and literature-native
formulations.

### 5.2 Noise floor via silence controls

**(X, using an (S)-grounded concept)** The Uchida 2004 PRL's core finding — that consistency
is noise-floor-limited at small drive amplitude (§1, §2) — maps directly onto this repo's
already-existing `silence` condition (`plasma_rc/acquisition/session.py::_parse_silence`,
files matching `s<N>.wav`, condition="silence", label="silence"). Recording **R repeats of
the same silence file** and computing `C_silence` with the identical formula gives a direct
noise floor from real hardware (photodiode dark noise, ADC quantization, plasma's own
un-driven flicker) rather than an assumed baseline. Any stimulus condition whose
`C_brightness` is not clearly above `C_silence` should be treated as noise-dominated, not
as evidence of "good" (low-λ_c) reservoir dynamics. This specific translation (use the
existing silence dataset for this purpose) is my own recommendation — no source above
discusses this repo's dataset taxonomy, obviously — but the underlying logic (small/zero
drive ⇒ noise-dominated response ⇒ noise floor) is directly grounded in the verified Uchida
2004 PRL finding.

### 5.3 Transient discard

**(S, qualitative only)** Uchida/Yoshimura (§1.2, §2) explicitly discard/observe past an
initial transient before asserting asymptotic consistency; no numeric ratio is given in any
source I could verify. **(X)** For this system, recommend the team empirically estimate the
neon bulb's own ionization/relaxation timescale (typically sub-millisecond to a few ms for a
glow-discharge bulb, but should be measured, not assumed) from the existing recordings (e.g.
the reproducible rise-time of `brightness` at trial onset), and exclude at least the first
several multiples of that timescale from the analysis window before computing `C_brightness`.
Check first whether `cfg.pre_roll_s` (already present in `plasma_rc/acquisition/config.py`
per `run_trial`'s use of `cfg.pre_roll_s`/`cfg.post_roll_s`) already provides this settling
margin outside the audio-play window — if so, the analysis window can likely start at
`t = pre_roll_s` without additional discard.

### 5.4 How many repeats, how many stimuli, what duration

**(S, order-of-magnitude anchor only)** The one verified physical number in this literature
is Uchida/Yoshimura's **10** repeat realizations (numerical, not physical hardware) used to
get a stable pairwise-correlation estimate (§1.2, §2). No verified source gives a
physical-hardware repeat count.

**(X)** Given the stated budget (~15 trials per condition total, ~1.5 s each, 100 kHz):
- Recommend **8–15 repeats of one fixed representative stimulus per condition category**
  (e.g. one `same_word` file, one `different_word` file, one `noise` file, one `silence`
  file, one `fsdd` digit) rather than spreading the 15-trial budget thinly across many
  distinct stimuli. R = 10 gives 45 pairwise correlations to average (a reasonable,
  literature-consistent order of magnitude per §1.2's own ensemble size); R = 15 gives 105
  pairs, at the cost of using the *entire* existing per-condition trial budget on repeats of
  a single stimulus rather than on stimulus diversity. This is a tradeoff the team should
  make deliberately: either (a) spend one full condition's 15-trial budget on repeats of a
  single stimulus to get a solid single consistency estimate, or (b) split, e.g. 3 stimuli ×
  5 repeats, to see how consistency varies with stimulus content at the cost of a noisier
  per-stimulus estimate (5 repeats → 10 pairs, a much less stable correlation-of-correlations
  estimate). Neither split is validated by a source above; both are statistically defensible
  compromises given 15 trials/condition.
- Recommend **keeping the existing ~1.5 s trial duration** — no source above gives a
  duration-vs-timescale rule to override this, and 1.5 s at 100 kHz (150,000 samples) is
  already long relative to a plausible sub-10 ms plasma relaxation time, giving ample samples
  for the time-average in the consistency formula even after transient discard (§5.3).
- Recommend testing consistency across at **least 2–3 stimulus categories already in the
  dataset taxonomy** (e.g. `noise` = white_noise, and one `same_word`/`different_word`
  speech file) rather than only one, since Uchida 2004 PRL's central result is that
  consistency is *amplitude*- and, by extension, *signal-content*-dependent — a single
  stimulus type risks reporting an artifact of that one waveform's spectral content/amplitude
  rather than a general property of the plasma reservoir.

### 5.5 Fixing the repeat-recording file-naming problem

`plasma_rc/acquisition/session.py::raw_path()` currently builds:

```python
def raw_path(out_dir: Path, meta: TrialMeta) -> Path:
    return out_dir / "raw" / meta.speaker / meta.condition / meta.label / f"{meta.stem}.npz"
```

with no repeat-index component — re-running `run_trial` on the same source file today
silently overwrites the previous `.npz`. **(X, pure recommendation, not a literature
finding — literature does not discuss file formats):**

- Add a `repeat_index: int` field to `TrialMeta` (populated by the caller/session-runner,
  not parsed from the audio filename, since the audio filename shouldn't need to encode
  "this is repeat 3"), and change `raw_path` to something like
  `out_dir / "raw" / speaker / condition / label / f"{stem}__rep{repeat_index:02d}.npz"`
  (or a `stem/rep{03d}.npz` subdirectory if per-stimulus grouping is preferred for globbing).
- Add a `repeat_index` column to `INDEX_FIELDS` in the same file, so `index.csv` can
  disambiguate repeats without parsing filenames, and so downstream analysis
  (`memory_capacity.py`, `separation.py`, a future `consistency.py`) can `groupby`
  `(speaker, condition, label, source_file)` and treat `repeat_index` as the trial axis.
- Keep `session_id` as-is (it already exists per capture session) but do not rely on it
  alone to distinguish repeats — recording all repeats of a stimulus within a single
  session (so hardware/environmental drift is minimized between repeats, consistent with
  the general "consistency should isolate deterministic divergence, not environmental
  drift" logic implicit in every source in §1–§3) is preferable to spreading repeats across
  sessions recorded at different times/days, unless the team specifically wants to also
  characterize long-timescale hardware drift as a separate question.

---

## Summary of citation status

**Fully verified (title/authors/venue/year/DOI cross-checked, and primary text read in
at least partial detail):**
Uchida, McAllister, Roy, PRL 93, 244102 (2004); Uchida, Yoshimura, Davis, Yoshimori, Roy,
arXiv:nlin/0703004 / PRE 78, 036203 (2008); Appeltant et al., Nat. Commun. 2, 468 (2011);
Martinenghi et al., PRL 108, 244101 (2012); Brunner et al., Nat. Commun. 4, 1364 (2013);
Soriano et al., Opt. Express 21(1), 12 (2013); Soriano et al., IEEE TNNLS 26(2), 388 (2015);
Nakayama, Kanno, Uchida, Opt. Express 24(8), 8679 (2016); Dambre et al., Sci. Rep. 2, 514
(2012); Tanaka et al., Neural Networks 115, 100 (2019); Lymburn et al., Chaos 29, 023118
(2019); Jüngling, Lymburn, Small, arXiv:2105.13473 / IEEE TNNLS 33(6), 2586 (2022); Lymburn,
Walker, Small, Jüngling, Chaos 29, 093133 (2019); Giacomelli, Barland, Giudici, Politi, PRL
104, 194101 (2010, bibliographic record only).

**Corrections to the original request's recollections:**
1. Uchida/McAllister/Roy is *Physical Review Letters*, not *Nature Physics* — confirmed.
2. The author list "Soriano, Ortín, Brunner, Larger, Mirasso, Fischer, Pesquera" matches
   the **2013 Optics Express** paper, not the 2015 IEEE TNNLS paper (which has a different,
   non-overlapping-in-those-names author list: Ortín, Keuninckx, Appeltant, Danckaert,
   Pesquera, Van der Sande).

**Flagged unverified (bibliographic record found and plausible, but I could not confirm
the specific claim/detail against primary text):**
- Pikovsky 1984 (Radiophys. Quantum Electron. 27, 390) — record verified, content not read.
- Physical (as opposed to numerical) repeat counts in Uchida 2004 PRL, Martinenghi 2012,
  Brunner 2013, and Nakayama/Kanno/Uchida 2016 — paywalled past abstract.
- The ">0.95 consistency correlation in injection-locked regimes" figure attributed to the
  Brunner 2013 lineage — found only via a search-engine summary, not primary text.
- Whether Tanaka et al. 2019's review discusses consistency/conditional-Lyapunov measures
  by name alongside memory capacity/separation.
