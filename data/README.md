# Data

## Files

- `plasma_data_apple_m.csv` — 118 rows, 76.02s, columns `Timestamp_Seconds, Brightness, Frequency_Hz, Settle_Micros`
- `plasma_data_apple_c.csv` — 181 rows, 94.64s, same columns

Both received 2026-07-15 via email from Majesty (forwarded through Alejandro), as two attachments on one Gmail thread. Each was downloaded 3-4 times by the browser (hence the `(1)`, `(2)`, `(3)` suffixes originally in Downloads) — verified byte-identical across repeats via MD5 and via Chrome's download history (same thread ID, matching byte counts), so only these two distinct files exist. Deduplicated copies were removed from Downloads.

## What `_m` and `_c` mean

Unknown. Not stated anywhere in the email or the files. Brightness levels are similar between the two (~820-836), so `_c` is not the low-brightness baseline described in the review below. Needs to be asked directly.

## Known limitations (as of 2026-07-15)

This data does **not** yet support the Step 1 characterization pipeline (`memory_capacity`, `separation_matrix`, `lyapunov_estimate`):

- **No input signal logged** — no `voltage_in` column, so `memory_capacity()` can't run.
- **No same-session baseline recording** — can't baseline-subtract, can't check whether "clustering" claims hold on equal footing.
- **No trial labels/boundaries** — each file is one continuous session, not the 50-trials-per-word the original report claimed. Both files do show a repeating burst structure (~12 prominence>500 frequency peaks each, ~21-22 brightness peaks each, irregularly spaced ~3-12s apart) that might correspond to repeated utterances, but there's no logged segmentation to treat these as discrete trials — that would need to come from Majesty, not be inferred after the fact.
- **No second word** — can't test the syllable-count confound (apple vs mango) raised in the review.
- **No audio-only control** — can't test whether the plasma contributes anything beyond what a mic + peak-counter would give.

Only `effective_dimensionality()` (PCA per recording) is honestly computable right now. See `experiments/real_data_diagnostic.py`.

## Background

This data request traces back to a review Mahault sent Alejandro (2026-07-06) of graphs Majesty circulated claiming to "prove" the plasma reservoir works. The review flagged: baseline recorded under different conditions than word trials (brightness ~60 vs ~800, an order of magnitude off on settle time too), a "scattered vs clustered" contrast that looked like an autoscaling artifact, and a classifier that's effectively counting syllable peaks in settle time — doable with a mic alone, no plasma required. The five items above are what's still needed to actually test that.
