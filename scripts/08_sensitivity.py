"""Sensitivity analyses on the REAL ledger (no synthetic data; dust injection is an in-memory counterfactual).

S1  attacker cost per transfer c          -> closed-form leverage vs the Theorem 1 bound
S2  hub-exclusion threshold                -> how the non-hub population and leverage change
S3  victim sample size and random seed     -> stability of the E3 replay and the closed-form match
S4  E4 seed draw and seed-volume range     -> stability of tainted-value visibility (hypothetical seeds)
S5  assumed opening balance of victims     -> effect of unobserved opening balances on leverage
S6  share threshold theta                  -> closed-form leverage and replay agreement for several thetas

Usage:  python3 scripts/08_sensitivity.py            (reads data/processed/ledger.parquet, writes outputs/)
Optional: --ledger PATH --out DIR (used only for code smoke tests).
"""
import os, sys, json, argparse
import numpy as np, pandas as pd, yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bbe.units import to_u
from bbe.engine import Ledger
from bbe.attack import min_dust
from bbe.replay import seeded_replay

ap = argparse.ArgumentParser(); ap.add_argument("--ledger"); ap.add_argument("--out"); args = ap.parse_args()
root = os.path.join(os.path.dirname(__file__), "..")
cfg = yaml.safe_load(open(os.path.join(root, "config.yaml")))
out = args.out or os.path.join(root, cfg["out_dir"]); os.makedirs(out, exist_ok=True)
S = dict(cost_usd=[0.01, 0.05, 0.25, 1.0], hub_thresholds=[10, 50, 100, 500], seed_offsets=[0, 1, 2, 3, 4],
         victim_sizes=[1000, 5000, 10000], opening_balances_usd=[0, 100, 1000],
         e4_volume_ranges=[[1000, 1000000], [100, 10000], [10000, 10000000]], e4_draws=[0, 1, 2, 3, 4], theta_pairs=[[1, 100], [1, 20], [1, 10], [1, 5]])
S.update(cfg.get("sensitivity", {}))
p, q = cfg["theta"]; base_c = cfg["cost_per_transfer_usd"]

# ---- load the ledger exactly as scripts/05 does ------------------------------
led = pd.read_parquet(args.ledger or os.path.join(root, cfg["processed_dir"], "ledger.parquet"))
for c in ("amt_in_u", "amt_out_u"):
    led[c] = led[c].astype("int64")
led = led.reset_index(drop=True)
def norm(c):
    c = str(c); return c[:-2] if c.endswith(".0") else c
led["src_chain"] = led.src_chain.map(norm); led["dst_chain"] = led.dst_chain.map(norm)
if cfg.get("chain_qualified", True):
    led["src_key"] = led.src_chain + ":" + led.src_addr; led["dst_key"] = led.dst_chain + ":" + led.dst_addr
else:
    led["src_key"] = led.src_addr; led["dst_key"] = led.dst_addr
rec_cnt = led.groupby("dst_key").size()
bal_all = led.groupby("dst_key")["amt_out_u"].sum()
def nonhub_balances(thr):
    hubs = set(rec_cnt[rec_cnt > thr].index)
    return bal_all[~bal_all.index.isin(hubs)], hubs

def cost_vec(B, rule, d, c_u, pp=None, qq=None):
    pp = p if pp is None else pp; qq = q if qq is None else qq
    share = np.maximum(1, -(-(pp * B) // (qq - pp)))
    if rule == "poison": return np.ones_like(B) + c_u
    if rule == "share": return share + c_u
    return np.maximum(np.maximum(d, share), 1) + c_u
def lev(cv, budget):
    return int(np.searchsorted(np.cumsum(np.sort(cv)), budget, side="right"))

summary = {"n_transfers": int(len(led))}
base_nonhub, base_hubs = nonhub_balances(cfg["hub_receipt_threshold"])
B0 = base_nonhub.to_numpy().astype(np.int64)

# ---- S1: attacker cost per transfer ------------------------------------------
rows = []
for c in S["cost_usd"]:
    cu = to_u(c)
    for bud in cfg["budgets_usd"]:
        bu = to_u(bud)
        for rule, ds in (("poison", [0]), ("share", [0]), ("bbe", cfg["delta_usd"])):
            for d in ds:
                n = lev(cost_vec(B0, rule, to_u(d), cu), bu)
                bound = bud / (d + c) if rule == "bbe" else None
                rows.append(dict(cost_usd=c, budget_usd=bud, rule=rule, delta_usd=d, flagged=n, bound=bound,
                                 bound_holds=(n <= bound) if bound is not None else None))
s1 = pd.DataFrame(rows); s1.to_csv(f"{out}/S1_cost_sweep.csv", index=False)
summary["S1_bound_holds_all"] = bool(s1[s1.rule == "bbe"].bound_holds.all())

# ---- S2: hub threshold ---------------------------------------------------------
rows = []
for thr in S["hub_thresholds"]:
    nb, hubs = nonhub_balances(thr); B = nb.to_numpy().astype(np.int64)
    hv = float(bal_all[bal_all.index.isin(hubs)].sum() / bal_all.sum())
    for bud in cfg["budgets_usd"]:
        bu = to_u(bud)
        rows.append(dict(hub_threshold=thr, n_hubs=len(hubs), hub_value_share=hv, n_victims=len(B),
                         median_balance_usd=float(np.median(B)) / 1e6, budget_usd=bud,
                         poison=lev(cost_vec(B, "poison", 0, to_u(base_c)), bu),
                         share=lev(cost_vec(B, "share", 0, to_u(base_c)), bu),
                         bbe_floor100=lev(cost_vec(B, "bbe", to_u(100), to_u(base_c)), bu),
                         bound_floor100=bud / (100 + base_c)))
s2 = pd.DataFrame(rows); s2.to_csv(f"{out}/S2_hub_threshold.csv", index=False)

# ---- shared event list (plain Python ints) -------------------------------------
t_dep = led.t_dep.tolist(); t_wd = led.t_wd.tolist()
src = led.src_key.tolist(); dst = led.dst_key.tolist(); ain = led.amt_in_u.tolist(); aout = led.amt_out_u.tolist()
ev = [(t_dep[i], 0, i) for i in range(len(led))] + [(t_wd[i], 1, i) for i in range(len(led))]
ev.sort(key=lambda e: (e[0], e[1]))
first_recv = {}
for t, kind, i in ev:
    if kind == 1 and dst[i] not in first_recv:
        first_recv[dst[i]] = i
cand = [a for a in first_recv if a not in base_hubs]

def replay(pol, rule, delta, vict, pp=None, qq=None):
    pp = p if pp is None else pp; qq = q if qq is None else qq
    L = Ledger(pol); done = {}; mism = 0; now = 0
    for t, kind, i in ev:
        if kind == 0:
            L.transfer(src[i], "BRIDGE", ain[i])
        else:
            a = dst[i]; L.fund(a, aout[i])
            if a in vict and a not in done:
                d = min_dust(rule, L.bal[a], delta=delta, p=pp, q=qq)
                L.fund("ATT", d, True); L.transfer("ATT", a, d); done[a] = d
                ok = L.flagged(a, rule, delta, pp, qq); now += ok; mism += (not ok)
    dv = np.array(list(done.values()), dtype=float) / 1e6
    return dict(injected=len(done), flagged_immediately=now, closed_form_mismatch=mism,
                mean_dust_usd=float(dv.mean()) if len(dv) else None, median_dust_usd=float(np.median(dv)) if len(dv) else None)

# ---- S3: victim sample size and seed -------------------------------------------
configs = [(o, cfg["victim_sample"]) for o in S["seed_offsets"]] + \
          [(0, n) for n in S["victim_sizes"] if n != cfg["victim_sample"]]
rows = []
for off, n in configs:
    rng = np.random.default_rng(cfg["seed"] + off)
    vict = set(rng.choice(cand, size=min(n, len(cand)), replace=False).tolist())
    for pol, rule, delta in [("fifo", "bbe", to_u(100)), ("haircut", "share", 0)]:
        r = replay(pol, rule, delta, vict)
        r.update(seed_offset=off, victim_sample=n, policy=pol, rule=rule, delta_usd=delta / 1e6)
        rows.append(r)
s3 = pd.DataFrame(rows); s3.to_csv(f"{out}/S3_replay_stability.csv", index=False)
summary["S3_max_mismatch"] = int(s3.closed_form_mismatch.max())
summary["S3_runs"] = int(len(s3))
e3p = os.path.join(out, "E3_replay.csv")
if os.path.exists(e3p):  # seed offset 0 at the configured sample size must reproduce E3
    e3 = pd.read_csv(e3p); base = s3[(s3.seed_offset == 0) & (s3.victim_sample == cfg["victim_sample"])]
    chk = []
    for _, r in base.iterrows():
        m = e3[(e3.policy == r.policy) & (e3.rule == r.rule) & (np.isclose(e3.delta_usd, r.delta_usd))]
        if len(m): chk.append(int(m.iloc[0].flagged_immediately) == int(r.flagged_immediately))
    summary["S3_reproduces_E3"] = bool(chk) and all(chk)

# ---- S4: E4 seed draw and seed-volume range (hypothetical seeds on real flows) ----
vol = led.groupby("src_key")["amt_in_u"].sum()
def e4_oracle(seeds):
    arrivals, acc, _ = seeded_replay(ev, src, dst, ain, aout, seeds)   # shared, accounting-checked replay
    return [(a, T) for a, T, B in arrivals], acc["seeded"]
rows = []
for lo, hi in S["e4_volume_ranges"]:
    elig = vol[(vol >= to_u(lo)) & (vol <= to_u(hi))].index.to_numpy()
    if len(elig) == 0: continue
    for dr in S["e4_draws"]:
        rng = np.random.default_rng(cfg["seed"] + 100 + dr)
        seeds = set(rng.choice(elig, size=min(cfg["e4_seed_count"], len(elig)), replace=False).tolist())
        arr, seeded = e4_oracle(seeds); tot = sum(a for a, _ in arr)
        for d in [0, to_u(1), to_u(100), to_u(1000)]:
            seen = sum(a for a, T in arr if T >= max(d, 1))
            rows.append(dict(vol_min_usd=lo, vol_max_usd=hi, draw=dr, n_seeds=len(seeds), delta_usd=d / 1e6,
                             arrivals=len(arr), seeded_usd=seeded / 1e6, tainted_arrived_usd=tot / 1e6,
                             recall=(seen / tot if tot else None)))
s4 = pd.DataFrame(rows); s4.to_csv(f"{out}/S4_e4_stability.csv", index=False)

# ---- S5: assumed opening balance -----------------------------------------------
rows = []
for o in S["opening_balances_usd"]:
    B = B0 + to_u(o)
    for bud in cfg["budgets_usd"]:
        bu = to_u(bud)
        rows.append(dict(opening_balance_usd=o, budget_usd=bud,
                         poison=lev(cost_vec(B, "poison", 0, to_u(base_c)), bu),
                         share=lev(cost_vec(B, "share", 0, to_u(base_c)), bu),
                         bbe_floor100=lev(cost_vec(B, "bbe", to_u(100), to_u(base_c)), bu),
                         bound_floor100=bud / (100 + base_c)))
s5 = pd.DataFrame(rows); s5.to_csv(f"{out}/S5_opening_balance.csv", index=False)
summary["S5_bbe_floor100_max"] = int(s5.bbe_floor100.max())

# ---- S6: share threshold theta ---------------------------------------------------
rng6 = np.random.default_rng(cfg["seed"])
vict6 = set(rng6.choice(cand, size=min(cfg["victim_sample"], len(cand)), replace=False).tolist())
rows = []
for pp, qq in S["theta_pairs"]:
    for bud in cfg["budgets_usd"]:
        bu = to_u(bud)
        rows.append(dict(theta_pct=100.0 * pp / qq, budget_usd=bud, kind="closed_form",
                         share=lev(cost_vec(B0, "share", 0, to_u(base_c), pp, qq), bu),
                         bbe_floor100=lev(cost_vec(B0, "bbe", to_u(100), to_u(base_c), pp, qq), bu),
                         bound_floor100=bud / (100 + base_c), floor_stops_binding_above_balance_usd=100.0 * (qq - pp) / pp))
    r = replay("fifo", "bbe", to_u(100), vict6, pp, qq)
    rows.append(dict(theta_pct=100.0 * pp / qq, kind="replay_fifo_bbe100", injected=r["injected"],
                     flagged_immediately=r["flagged_immediately"], closed_form_mismatch=r["closed_form_mismatch"],
                     median_dust_usd=r["median_dust_usd"]))
s6 = pd.DataFrame(rows); s6.to_csv(f"{out}/S6_theta.csv", index=False)
summary["S6_max_mismatch"] = int(s6[s6.kind == "replay_fifo_bbe100"].closed_form_mismatch.max())

# headline ranges for the paper text
e3a = s3[(s3.victim_sample == cfg["victim_sample"]) & (s3.policy == "fifo")]
summary["S3_bbe_flagged_fraction_range"] = [float((e3a.flagged_immediately / e3a.injected).min()),
                                              float((e3a.flagged_immediately / e3a.injected).max())]
if len(s4):
    r100 = s4[np.isclose(s4.delta_usd, 100) & (s4.vol_min_usd == cfg["e4_seed_min_usd"])]
    if len(r100): summary["S4_recall_delta100_range"] = [float(r100.recall.min()), float(r100.recall.max())]
json.dump(summary, open(f"{out}/sensitivity_summary.json", "w"), indent=2)

# ---- figure: BBE leverage against c, at two floors where c matters ------------------
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.1))
cols = {100: "C0", 1000: "C1", 10000: "C2"}
for ax, d in zip(axes, (1, 10)):
    for bud, g in s1[(s1.rule == "bbe") & (np.isclose(s1.delta_usd, d))].groupby("budget_usd"):
        ax.plot(g.cost_usd, g.flagged, marker="o", color=cols[bud], label=f"BBE, budget ${bud:,.0f}")
        ax.plot(g.cost_usd, g.bound, linestyle="--", color=cols[bud], alpha=0.7)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_title(f"floor $\\delta$ = {d} USD", fontsize=10)
    ax.set_xlabel("attacker cost per transfer $c$ (USD)"); ax.set_ylabel("accounts flagged")
h, l = axes[0].get_legend_handles_labels()
h.append(Line2D([], [], linestyle="--", color="grey")); l.append("bound $B/(\\delta+c)$")
fig.legend(h, l, loc="lower center", ncol=4, fontsize=8, frameon=False)
fig.tight_layout(rect=(0, 0.08, 1, 1)); fig.savefig(f"{out}/fig_sens_cost.png", dpi=200)
print(json.dumps(summary, indent=2)); print("sensitivity outputs written to", out)
