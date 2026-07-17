# Recording Protocol — Plasma Reservoir Data Collection

Follow this exactly and one recording session gives us everything Step 1 of the
roadmap needs. Every deviation (config change, missing baseline, unlabeled
trial) makes the session unusable for characterization, which is what happened
to the four recordings we have so far.

## 1. Hardware rules

- **Pick one amplifier configuration and never change it mid-study.** We have
  measured that amplifier in vs. out moves brightness from ~52 to ~560+ ADC
  counts. Any config change invalidates all comparisons across it.
- Same sensor position, same gain, same bulb, same speaker-to-mic distance for
  every recording in the study. If anything must change, that starts a new
  study, not a new session.
- Write down the config once at the top of the session notes: amplifier
  in/out, supply voltage, sensor distance, room.

## 2. CSV format

One row per sample, keep the existing columns and add the input signal:

```
Timestamp_Seconds, Audio_In, Brightness, Frequency_Hz, Settle_Micros
```

- `Audio_In` — raw ADC reading of the audio/voltage signal being injected
  into the plasma, sampled in the same loop as the other columns. This is the
  most important change: without a logged input we cannot compute memory
  capacity or show the plasma transforms the signal at all.
- Log actual timestamps as you already do. Consistent sampling matters more
  than hitting exactly 10 Hz, but aim for a steady rate (current recordings
  are ~0.4-0.5 s per sample, not the 10 Hz in the spec — either is fine if
  it is steady and honest).

## 3. Session structure

Each session is one sitting, one config, one folder: `session_YYYYMMDD/`.

1. **Baseline first, every session.** 60 seconds of silence (nobody speaks,
   no audio injected) recorded with the exact same setup, saved as
   `baseline.csv`. No exceptions — this is what lets us baseline-subtract
   and handle the session-to-session drift we have already observed
   (brightness ~561 vs ~835 in what looks like the same config).
2. **Trials.** One file per utterance, named `<word>_<nn>.csv`
   (`apple_01.csv` … `apple_10.csv`). Start recording ~1 s before speaking,
   stop ~1 s after. One word per file — no continuous multi-word sessions.
3. **Words.** At minimum: `apple`, `mango`, `banana`. Apple vs. mango is the
   critical pair (same syllable count) — it tests whether the system does
   more than count syllables. 10+ repeats per word, same speaker, same
   volume, same distance.
4. **Optional but valuable:** the same word at 50/75/100% volume
   (`apple_v50_01.csv` etc.), and a second speaker.

## 4. The control run (decides everything)

Repeat the full session — baseline plus 10+ trials of each word — with the
**plasma out of the loop**: microphone/audio envelope wired straight through
the same logging pipeline, same CSV format, files in `control_YYYYMMDD/`
named the same way (`apple_01.csv` …).

This is the experiment that answers the whole question. If a readout trained
on plasma states beats the same readout trained on the plasma-free control,
the plasma is computing. If not, it is acting as a transducer and we fix the
encoding before anything else.

## 5. What to send

The complete session folder(s): baseline, all trial files, the control
folder, and the session notes (config description, who spoke, anything that
went wrong). Partial sessions are not useful — a session without its baseline
or with a mid-session config change cannot enter the analysis.

## What we run on it (already built, `plasma_rc`)

- `separation_matrix()` — are words distinguishable in state space?
  Target: inter-class > 2× intra-class distance.
- `lyapunov_estimate()` — is the reservoir deterministic enough across
  repeated trials of the same word?
- `memory_capacity()` — needs `Audio_In`. Target: MC > 5.
- `effective_dimensionality()` — how many of the 3 state dims are used.
- Held-out linear readout accuracy, plasma vs. control — the decisive test.
