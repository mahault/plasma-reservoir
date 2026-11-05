"""Figures and tables for docs/study_2026-11-04.md from results/study_*/results.json.
    python -m experiments.study_figures results/study_20261104/results.json docs/study
Palette: dataviz reference categorical slots in fixed order (validated: scripts/validate_palette.js, light).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from experiments.study import CONDITIONS, EDGE, R1, R2, lamp, make  # noqa: E402
from plasma_rc.sim import simulate  # noqa: E402
from plasma_rc.stimuli import held_input  # noqa: E402

SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
INK, MUTED, GRID, SURFACE = "#1f1f1e", "#5c5c58", "#e6e6e3", "#fcfcfb"
NAMES = list(CONDITIONS)
COLOR = dict(zip(NAMES, SLOTS))
plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 10, "legend.frameon": False})


def group(results, kind):
    g = defaultdict(list)
    for r in results:
        if r["kind"] == kind and "error" not in r["result"]:
            g[r["name"]].append(r["result"])
    return g


def ms(values):
    v = np.array([x for x in values if x is not None], float)
    return (float(v.mean()), float(v.std())) if v.size else (np.nan, np.nan)


def fmt(m, s):
    return f"{m:.3f} ± {s:.3f}"


def save(fig, out, name):
    fig.tight_layout()
    fig.savefig(out / name, dpi=160)
    plt.close(fig)


def fig_regimes(out):
    cfg, lv = make({}), np.arange(256)
    v_th = np.array([cfg.thevenin(cfg.drive(x / 255))[0] for x in lv])
    i_op = np.array([max(cfg.operating_current(cfg.drive(x / 255)), 0) for x in lv]) * 1e3
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
    for a, y, ref, lab, tag in ((ax[0], v_th, cfg.get("lamp", "V_b"), "Thévenin voltage V_th [V]", "V_b"),
                                (ax[1], i_op, cfg.get("lamp", "I_x") * 1e3, "lit operating current i_op [mA]", "I_x")):
        a.plot(lv, y, color=SLOTS[0], lw=2)
        a.axhline(ref, color=MUTED, lw=1, ls="--")
        a.text(5, ref, f" {tag}", color=MUTED, fontsize=8, va="bottom")
        for (lo, hi), name in ((R1, "R1 band"), (R2, "R2 band")):
            a.axvspan(lo, hi, color=GRID, alpha=0.6, lw=0)
            a.text((lo + hi) / 2, y.max(), name, ha="center", va="top", color=MUTED, fontsize=8)
        a.axvspan(*EDGE, fill=False, hatch="///", edgecolor=SLOTS[6], lw=0, alpha=0.3)
        a.text(EDGE[0], y.min(), " edge band", color=MUTED, fontsize=8, va="bottom")
        a.set_xlabel("DAC level")
        a.set_ylabel(lab)
    save(fig, out, "fig1_regimes.png")


def fig_traces(out):
    fig, axes = plt.subplots(4, 1, figsize=(10, 8.4), sharex=True)
    for ax, name in zip(axes, ("R2 lamp", "R1 lamp", "R1 afterglow (hyp.)", "R0/R1 edge lamp")):
        band, kind, ov = CONDITIONS[name]
        cfg = make(ov)
        levels, _ = held_input(8, 3, lo=band[0], hi=band[1])
        tr = simulate(cfg, levels / 255, 20e-6, 400, lamp(kind, cfg), 3)
        ax.plot(tr.t.ravel() * 1e6, tr.v.ravel(), color=COLOR[name], lw=1.2, label="node v")
        ax.plot(tr.t.ravel() * 1e6, tr.v_d.ravel(), color=MUTED, lw=1, ls="--", label="drive V_D")
        ax.set_ylabel("V")
        ax.set_title(name, loc="left", fontsize=10, color=INK)
    axes[0].legend(loc="lower right", ncol=2)
    axes[-1].set_xlabel("time [µs] (8 input steps of 20 µs)")
    save(fig, out, "fig2_traces.png")


def hbars(ax, labels, vals, colors, xlabel, ref=None):
    y, m, s = np.arange(len(labels)), [v[0] for v in vals], [v[1] for v in vals]
    ax.barh(y, m, xerr=s, color=colors, height=0.6, error_kw={"ecolor": INK, "lw": 1})
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    if ref is not None:
        ax.axvline(ref, color=MUTED, ls="--", lw=1)
    for yi, mi in zip(y, m):
        ax.text(mi, yi, f" {mi:.2f}", va="center", fontsize=8, color=INK)


def fig_benchmarks(res, out, tables):
    main_r, base = group(res, "main"), group(res, "baseline")[""]
    bnames = list(base[0])
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    for ax, n in zip(axes, ("2", "5", "10")):
        vals = [ms([r["narma"][n] for r in main_r[c]]) for c in NAMES] + [ms([b[k][n] for b in base]) for k in bnames]
        hbars(ax, NAMES + bnames, vals, [COLOR[c] for c in NAMES] + [GRID] * len(bnames), f"NARMA-{n} test NMSE", 1.0)
        tables.append((f"NARMA-{n} NMSE", NAMES + bnames, vals))
    save(fig, out, "fig3_narma.png")
    fig, ax = plt.subplots(figsize=(8, 4))
    for c in NAMES:
        mc = np.array([r["mc"] for r in main_r[c]])
        ax.errorbar(np.arange(1, mc.shape[1] + 1), mc.mean(0), yerr=mc.std(0), color=COLOR[c], lw=2, marker="o",
                    ms=4, capsize=2, label=c)
    ax.set(xlabel="delay d [input steps]", ylabel="linear capacity C(d)", ylim=(-0.05, 1.05))
    ax.legend(fontsize=8)
    save(fig, out, "fig4_memory.png")
    binr = group(res, "binary")
    keys = list(binr[NAMES[0]][0])
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.6), sharey=True)
    for ax, k in zip(axes, keys):
        vals = [ms([r[k] for r in binr[c]]) for c in NAMES]
        hbars(ax, NAMES, vals, [COLOR[c] for c in NAMES], f"accuracy: XOR of b[k−d], d ∈ {k[3:]}", 0.5)
        ax.set_xlim(0.3, 1.05)
        tables.append((f"accuracy {k}", NAMES, vals))
    save(fig, out, "fig5_xor.png")
    rk = group(res, "rank")
    km = [ms([r["kernel_rank"] for r in rk[c]]) for c in NAMES]
    gm = [ms([r["generalization_rank"] for r in rk[c]]) for c in NAMES]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    y = np.arange(len(NAMES))
    ax.barh(y - 0.17, [k[0] for k in km], xerr=[k[1] for k in km], height=0.32, color=SLOTS[0], label="kernel rank")
    ax.barh(y + 0.17, [g[0] for g in gm], xerr=[g[1] for g in gm], height=0.32, color=SLOTS[1],
            label="generalization rank")
    ax.set_yticks(y, NAMES)
    ax.invert_yaxis()
    ax.set_xlabel("numerical rank (σ > 1 % of σ_max), 24 state dimensions")
    ax.legend(fontsize=8, loc="lower right")
    save(fig, out, "fig6_rank.png")
    tables += [("kernel rank", NAMES, km), ("generalization rank", NAMES, gm)]
    ly = group(res, "lyap")
    fig, ax = plt.subplots(figsize=(8, 4))
    for c in NAMES:
        d = np.array([r["dist_v"] for r in ly[c]])
        ax.semilogy(np.maximum(np.median(d, 0), 1e-12), color=COLOR[c], lw=2, label=c)
    ax.set(xlabel="input step", ylabel="median max |v_a − v_b| per step [V]")
    ax.legend(fontsize=8)
    save(fig, out, "fig7_divergence.png")
    conv = [(float(np.median([r["converged_step"] if r["converged_step"] is not None else np.inf for r in ly[c]])), 0.0)
            for c in NAMES]
    tables.append(("twin-trajectory convergence step (median; inf = not within 200 steps)", NAMES, conv))
    return main_r


def fig_sweeps(res, out, tables):
    specs = (("sweep_T", "step length T_step [µs]", 1e6), ("sweep_tau", "driver pole τ_drv [µs]", 1e6),
             ("sweep_C", "node capacitance C_s [pF]", 1e12), ("sweep_ts", "mean statistical delay t_s [µs]", 1e6),
             ("sweep_M", "within-step samples M", 1))
    fig, axes = plt.subplots(2, len(specs), figsize=(18, 6.4))
    for j, (kind, xlabel, scale) in enumerate(specs):
        g = group(res, kind)
        for s in sorted({k.split("|")[0] for k in g}):
            pts = sorted((float(k.split("|")[1]), k) for k in g if k.startswith(s + "|"))
            xs = np.array([p[0] for p in pts]) * scale
            for i, metric in enumerate(("mc", "narma10")):
                vals = [ms([sum(r["mc"]) if metric == "mc" else r["narma"]["10"] for r in g[k]]) for _, k in pts]
                if metric == "narma10":   # a diverged readout (NMSE ≫ 1) would flatten the panel: clip and label
                    for x, (m, _) in zip(xs, vals):
                        if m > 1.6:
                            axes[i, j].annotate(f"{m:.0f} (off scale)", (x, 1.6), ha="right", va="top", fontsize=7,
                                                color=INK)
                    vals = [(min(m, 1.6), s if m <= 1.6 else 0.0) for m, s in vals]
                    axes[i, j].set_ylim(0.5, 1.65)
                axes[i, j].errorbar(xs, [v[0] for v in vals], yerr=[v[1] for v in vals], marker="o", ms=4, lw=2,
                                    capsize=2, color=COLOR.get(s, SLOTS[0]), label=s)
                tables.append((f"{kind} {metric} — {s}", [f"{x:g}" for x in xs], vals))
        for i in range(2):
            axes[i, j].set(xlabel=xlabel, ylabel=("memory capacity Σ C(d), d=1..4", "NARMA-10 NMSE")[i])
            if kind in ("sweep_T", "sweep_C"):
                axes[i, j].set_xscale("log")
        axes[0, j].legend(fontsize=7)
    save(fig, out, "fig8_sweeps.png")


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    data = json.loads(src.read_text())
    res, tables = data["results"], []
    fig_regimes(out)
    fig_traces(out)
    main_r = fig_benchmarks(res, out, tables)
    fig_sweeps(res, out, tables)
    lines = ["| Condition | MC Σ C(d), d=1..8 | IPC degree 2 | consistency κ | attribution Δ | flashes/step |",
             "|---|---|---|---|---|---|"]
    for c in NAMES:
        rs = main_r[c]
        vals = (ms([sum(r["mc"]) for r in rs]), ms([r["ipc2"] for r in rs]),
                ms([r["consistency"]["nmse_consistency"] for r in rs]), ms([r["attribution"]["gain"] for r in rs]),
                ms([r["flashes_per_step"] for r in rs]))
        lines.append(f"| {c} | " + " | ".join(fmt(*v) for v in vals) + " |")
    lines += ["", "| Ablation: flash counts only | NARMA-10 NMSE | MC Σ C(d), d=1..4 | IPC degree 2 |", "|---|---|---|---|"]
    lines += [f"| {c} | {fmt(*ms([r['ablation_flash_counts']['narma10'] for r in main_r[c]]))} | "
              f"{fmt(*ms([sum(r['ablation_flash_counts']['mc']) for r in main_r[c]]))} | "
              f"{fmt(*ms([r['ablation_flash_counts']['ipc2'] for r in main_r[c]]))} |"
              for c in NAMES if all("ablation_flash_counts" in r for r in main_r[c])]
    for title, labels, vals in tables:
        lines += ["", f"**{title}**", "", "| | " + " | ".join(labels) + " |", "|---" * (len(labels) + 1) + "|",
                  "| mean ± std | " + " | ".join(fmt(*v) for v in vals) + " |"]
    lines += ["", "**Solver tolerance check (R1 lamp, seed 0)**", ""]
    lines += [f"- rtol {k.split('|')[1]}: NARMA-10 {v[0]['narma']['10']:.4f}, flashes/step {v[0]['flashes_per_step']:.3f}"
              for k, v in group(res, "tolerance").items()]
    lines += ["", f"git HEAD {data['git_head']}; base {data['base']}; label: {data['label']}"]
    (out / "tables.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
