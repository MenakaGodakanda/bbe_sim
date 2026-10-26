#!/usr/bin/env python3
"""Figures 13 and 14 of the paper (cross-chain taint accounting; R1 interaction grid).

Usage:  python3 scripts/10_make_new_figures.py [--outputs outputs] [--out outputs]
Run after 05_run_experiments.py and 09_robustness.py. Reads E4_conservation.csv and R1_interaction_grid.csv,
writes fig_taint_accounting.png (Figure 13) and fig_interaction_grid.png (Figure 14), 300 dpi.
"""
import argparse, os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ap = argparse.ArgumentParser()
ap.add_argument("--outputs", default=os.path.join(ROOT, "outputs")); ap.add_argument("--out", default=os.path.join(ROOT, "outputs"))
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
RED="#b03a2e"; BLUE="#1f618d"; GREY="#566573"; GREEN="#1e8449"; AMBER="#b9770e"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})

# ---------------- Figure 13: where the deposited tainted value goes ----------------
c = pd.read_csv(os.path.join(a.outputs, "E4_conservation.csv"))
names = {"oracle": "True link", "linker_pi0.0": "Conserving linker, π = 0", "linker_pi0.5": "Conserving linker, π = 0.5"}
cats = [("delivered", "Delivered to receivers", GREEN, None), ("not_followed", "Not followed (no candidate or 1/k < π)", AMBER, None),
        ("capped", "Capped (overlapping candidate sets)", RED, "//")]
fig, ax = plt.subplots(figsize=(7.2, 2.7))
for r, (_, row) in enumerate(c.iloc[::-1].iterrows()):
    tot = row.locked_taint; left = 0
    for key, lab, col, hatch in cats:
        w = row[key] / tot * 100
        ax.barh(r, w, left=left, height=0.55, color=col, edgecolor="white", linewidth=1.2, hatch=hatch, label=lab if r == 0 else None)
        if w >= 10: ax.text(left + w / 2, r, f"{w:.1f}%", ha="center", va="center", color="white", fontsize=8, weight="bold")
        elif w >= 3: ax.text(100.8, r + 0.2, f"not followed {w:.1f}%", va="center", fontsize=7, color=AMBER)
        left += w
    capw = row["capped"] / tot * 100
    if capw < 3 and row["capped"] > 0: ax.text(100.8, r - 0.2, f"capped {capw:.2f}%", va="center", fontsize=7, color=RED)
ax.set_yticks(range(len(c))); ax.set_yticklabels([names[v] for v in c.variant.iloc[::-1]])
ax.set_xlim(0, 100); ax.set_clip_on(False); ax.set_xlabel("Share of tainted value deposited into bridges (%)")
for s in ("top", "right"): ax.spines[s].set_visible(False)
h, l = ax.get_legend_handles_labels(); ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.45, -0.28), ncol=3, frameon=False, fontsize=7)
fig.savefig(os.path.join(a.out, "fig_taint_accounting.png"), dpi=300, bbox_inches="tight", facecolor="white"); plt.close(fig)

# ---------------- Figure 14: interaction grid (R1) ----------------
g = pd.read_csv(os.path.join(a.outputs, "R1_interaction_grid.csv"))
deltas = sorted(g.delta_usd.unique()); thetas = sorted(g.theta.unique())
panels = [("True link", g[g.variant == "oracle"]),
          ("Linker, π = 0, 1 h", g[(g.variant == "linker_pi0.0") & (g.window_s == 3600)]),
          ("Linker, π = 0.5, 1 h", g[(g.variant == "linker_pi0.5") & (g.window_s == 3600)])]
cmap = LinearSegmentedColormap.from_list("b", ["#eaf2f8", "#1f618d"])
allv = np.concatenate([p.visibility_full_rule.to_numpy() for _, p in panels]) * 100
vmin, vmax = np.floor(allv.min()), np.ceil(allv.max())
fig = plt.figure(figsize=(7.4, 5.6)); gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.05], hspace=0.62, wspace=0.12)
for i, (t, p) in enumerate(panels):
    ax = fig.add_subplot(gs[0, i])
    M = np.array([[p[(p.delta_usd == d) & (np.isclose(p.theta, th))].visibility_full_rule.iloc[0] * 100 for th in thetas] for d in deltas])
    im = ax.imshow(M, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto", origin="lower")
    for y in range(len(deltas)):
        for x in range(len(thetas)):
            ax.text(x, y, f"{M[y, x]:.1f}", ha="center", va="center", fontsize=7.5, color="white" if M[y, x] > (vmin + vmax) / 2 + 1 else "#1b2631")
    ax.set_xticks(range(len(thetas))); ax.set_xticklabels([f"{th*100:g}%" for th in thetas]); ax.set_xlabel("share threshold θ")
    ax.set_yticks(range(len(deltas))); ax.set_yticklabels([f"{d:g}" for d in deltas] if i == 0 else [])
    if i == 0: ax.set_ylabel("floor δ (USD)")
    ax.set_title(t, fontsize=8.5, weight="bold", color=GREY)
cax = fig.add_axes([0.92, 0.57, 0.015, 0.3]); cb = fig.colorbar(im, cax=cax); cb.set_label("tainted value flagged (%)", fontsize=7.5)
fig.text(0.5, 0.935, "(a) Visibility under the full BBE rule (floor and share condition)", ha="center", fontsize=8.5, weight="bold")
ax = fig.add_subplot(gs[1, :])
cols = {"oracle": GREY, "linker_pi0.0": BLUE, "linker_pi0.5": GREEN}; styles = {1800: ":", 3600: "-", 7200: "--"}
for (v, w), p in g.groupby(["variant", g.window_s.fillna(0)]):
    p = p[np.isclose(p.theta, 0.1)].sort_values("delta_usd")
    lab = "True link" if v == "oracle" else f"π = {v[-3:]}, {int(w/60)} min"
    ax.plot(p.delta_usd, p.visibility_floor * 100, color=cols[v], ls="-" if v == "oracle" else styles[int(w)], marker="o", ms=3.5, lw=1.4, label=lab)
ax.set_xscale("log"); ax.set_xticks(deltas); ax.set_xticklabels([f"{d:g}" for d in deltas]); ax.set_xlabel("floor δ (USD)")
ax.set_ylabel("tainted value at or above the floor (%)"); ax.set_ylim(97, 100.1)
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.legend(ncol=3, frameon=False, fontsize=7, loc="lower left")
ax.set_title("(b) Visibility against the floor alone (does not depend on θ)", fontsize=8.5, weight="bold", loc="left")
fig.savefig(os.path.join(a.out, "fig_interaction_grid.png"), dpi=300, bbox_inches="tight", facecolor="white"); plt.close(fig)
print("written to", a.out)
