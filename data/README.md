# Data

## Files

- `plasma_data_apple_m.csv` — 118 rows, 76.02s, columns `Timestamp_Seconds, Brightness, Frequency_Hz, Settle_Micros`
- `plasma_data_apple_c.csv` — 181 rows, 94.64s, same columns
- `plasma_data_with_amplifier.csv` — 97 rows, 41.8s, same columns
- `plasma_data_without_amplifier.csv` — 119 rows, 60.5s, same columns

The apple files were received 2026-07-15 via email from Majesty (forwarded through Alejandro), as two attachments on one Gmail thread. Each was downloaded 3-4 times by the browser (hence the `(1)`, `(2)`, `(3)` suffixes originally in Downloads) — verified byte-identical across repeats via MD5 and via Chrome's download history (same thread ID, matching byte counts), so only these two distinct files exist. Deduplicated copies were removed from Downloads.

The amplifier pair was received 2026-07-17, again forwarded through Alejandro. **The accompanying email text has not been read yet** (Gmail connector was down; files were pulled manually), so everything below about these two files is inferred from filenames and the data alone — in particular we do not know whether anyone was speaking during either recording, or what "amplifier" refers to in the signal chain (audio injection amp vs. sensor amp).

## What the amplifier pair shows (2026-07-17)

Summary statistics:

| file | duration | brightness (mean±std) | settle mean/max (µs) | settle peaks (prominence>500) |
|------|----------|----------------------|----------------------|-------------------------------|
| with_amplifier | 41.8s | 52.1 ± 0.7 | 157 / 304 | 0 |
| without_amplifier | 60.5s | 560.9 ± 2.5 | 965 / 2632 | 30 |
| apple_m (for reference) | 76.0s | 835.6 ± 12.2 | 1326 / 3656 | 31 |
| apple_c (for reference) | 94.6s | 823.2 ± 5.7 | 1207 / 3088 | 31 |

Three observations, pending confirmation from the email text / Majesty:

1. **`with_amplifier` sits in the same regime as the original "pbaseline" graphs** (brightness ~52 vs ~58-62 in the graphs; settle flat at ~152-304µs vs ~150-190µs). This is strong evidence that the original baseline-vs-word contrast Majesty circulated was a *hardware configuration difference* (amplifier in/out of the chain), not a computational effect — exactly the concern raised in the 2026-07-06 review.
2. **The operating point drifts across sessions even within a config.** `without_amplifier` sits at brightness ~561 while both apple recordings (presumably also amplifier-out, given their settle activity) sit at ~820-836. Cross-session comparisons of raw values are meaningless without same-session baselines.
3. **`without_amplifier` shows the same settle-peak activity signature as the apple word recordings** (30 peaks in 60s vs 31 in each apple file, same prominence threshold the classifier uses). If nobody was speaking during this recording, the "word detection" signal fires on intrinsic discharge noise alone, which would undermine the peak-counting classifier. If someone *was* speaking, it is not a baseline. Either way the email text is needed to interpret it.

PCA effective dimensionality (95% variance): `with_amplifier` collapses to 1/3 dims (it's essentially flat); the other three use 2/3.

## What `_m` and `_c` mean

Unknown. Not stated anywhere in the email or the files. Brightness levels are similar between the two (~820-836), so `_c` is not the low-brightness baseline described in the review below. Needs to be asked directly.

## Known limitations (as of 2026-07-17)

This data does **not** yet support the Step 1 characterization pipeline (`memory_capacity`, `separation_matrix`, `lyapunov_estimate`):

- **No input signal logged** — no `voltage_in` column, so `memory_capacity()` can't run.
- **No same-session baseline recording** — can't baseline-subtract, can't check whether "clustering" claims hold on equal footing.
- **No trial labels/boundaries** — each file is one continuous session, not the 50-trials-per-word the original report claimed. Both files do show a repeating burst structure (~12 prominence>500 frequency peaks each, ~21-22 brightness peaks each, irregularly spaced ~3-12s apart) that might correspond to repeated utterances, but there's no logged segmentation to treat these as discrete trials — that would need to come from Majesty, not be inferred after the fact.
- **No second word** — can't test the syllable-count confound (apple vs mango) raised in the review.
- **No audio-only control** — can't test whether the plasma contributes anything beyond what a mic + peak-counter would give.

Only `effective_dimensionality()` (PCA per recording) is honestly computable right now. See `experiments/real_data_diagnostic.py`.

## Background

This data request traces back to a review Mahault sent Alejandro (2026-07-06) of graphs Majesty circulated claiming to "prove" the plasma reservoir works. The review flagged: baseline recorded under different conditions than word trials (brightness ~60 vs ~800, an order of magnitude off on settle time too), a "scattered vs clustered" contrast that looked like an autoscaling artifact, and a classifier that's effectively counting syllable peaks in settle time — doable with a mic alone, no plasma required. The five items above are what's still needed to actually test that.
