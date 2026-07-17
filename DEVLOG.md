# Devlog

## 2026-07-17
- Two more recordings from Majesty (via Alejandro): data/plasma_data_with_amplifier.csv and data/plasma_data_without_amplifier.csv. Gmail connector was down, so the accompanying email text is still unread — interpretation is from filenames + data only.
- Key finding: `with_amplifier` reproduces the original "pbaseline" graph regime (brightness ~52, settle flat), while `without_amplifier` sits at brightness ~561 with heavy settle activity (30 prominence>500 peaks in 60s — same signature as the apple word recordings at 31 each). The original baseline-vs-word contrast looks like an amplifier-config difference, not computation. Details in data/README.md.
- real_data_diagnostic.py picks the new files up automatically; regenerated real_data_diagnostic.png with all four recordings on shared axes.

## 2026-07-15
- First real plasma recordings landed (343d907): two apple-electrode datasets (data/plasma_data_apple_c.csv, data/plasma_data_apple_m.csv) with a data/README.md describing them.
- Added experiments/real_data_diagnostic.py — an honest diagnostic of what the real recordings do and don't show — plus supporting changes to plasma_rc/reservoir/physical.py and a ROADMAP.md update.
