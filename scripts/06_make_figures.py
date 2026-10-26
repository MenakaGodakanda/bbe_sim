import os, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
root = os.path.join(os.path.dirname(__file__), ".."); out = os.path.join(root, "outputs")
e2 = pd.read_csv(f"{out}/E2_leverage.csv"); e2 = e2[e2["pop"] == "nonhub"]
fig, ax = plt.subplots(figsize=(6.2, 4.2)); cols = {100: "C0", 1000: "C1", 10000: "C2"}
for B, g in e2.groupby("budget_usd"):
    b = g[(g.rule == "bbe") & (g.flagged > 0)]
    ax.plot(b.delta_usd, b.flagged, marker="o", color=cols[B], label=f"BBE, budget ${B:,.0f}")
    ax.scatter([0.5], [g[g.rule == "share"].flagged.iloc[0]], marker="s", color=cols[B], facecolors="none")
    ax.scatter([0.35], [g[g.rule == "poison"].flagged.iloc[0]], marker="^", color=cols[B], facecolors="none")
ax.scatter([], [], marker="s", color="k", facecolors="none", label="share rule (left)"); ax.scatter([], [], marker="^", color="k", facecolors="none", label="poison (left)")
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("floor delta (USD)"); ax.set_ylabel("victims flagged"); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(f"{out}/fig_leverage.png", dpi=200)
e1 = pd.read_csv(f"{out}/E1_linking.csv"); fig, ax = plt.subplots(figsize=(6.2, 4.2))
for f, g in e1.groupby("fee_tol"): ax.plot(g.window_s, g.mean_k, marker="o", label=f"fee tol {f}")
ax.set_xlabel("time window (s)"); ax.set_ylabel("mean candidates per deposit (k)"); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(f"{out}/fig_ambiguity.png", dpi=200)
e1p = pd.read_csv(f"{out}/E1_pi_sweep.csv"); fig, ax = plt.subplots(figsize=(6.2, 4.2))
ax.plot(e1p.pi, e1p.recall, marker="o"); ax.set_xlabel("confidence threshold pi"); ax.set_ylabel("link recall")
fig.tight_layout(); fig.savefig(f"{out}/fig_pi.png", dpi=200)
if os.path.exists(f"{out}/E4_recall.csv"):
    e4 = pd.read_csv(f"{out}/E4_recall.csv"); fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for v, g in e4.groupby("variant"): ax.plot(g.delta_usd.clip(lower=0.5), g.recall, marker="o", label=v)
    ax.set_xscale("log"); ax.set_xlabel("floor delta (USD)"); ax.set_ylabel("tainted value visible at arrival"); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(f"{out}/fig_recall.png", dpi=200)
print("figures written to outputs/")
