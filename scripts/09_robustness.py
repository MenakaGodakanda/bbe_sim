"""Robustness analyses added in response to review (REAL ledger; no synthetic data).

R1  parameter interactions: visibility of tainted value over a grid of floor delta x share threshold theta x
    linker (oracle, pi = 0, pi = 0.5) x matching window. Two visibility measures are reported:
      visibility_floor      share of arriving tainted value held at an account with T >= delta
      visibility_full_rule  share held at an account that BBE would actually flag (T >= delta AND T >= theta*B)
R2  clustered bootstrap: victims are resampled in clusters (all victims whose first receipt came from the same
    sender address), which respects dependence among addresses funded by the same source.
R3  heterogeneous transfer costs: the fee depends on the victim's destination chain (ASSUMED illustrative fee
    table in config.yaml). The bound with c replaced by the minimum fee must still hold.

Usage: python3 scripts/09_robustness.py [--ledger PATH --out DIR]   (the options are only for code smoke tests)
"""
import os, sys, argparse, itertools
import numpy as np, pandas as pd, yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bbe.units import to_u
from bbe.linking import candidates
from bbe.replay import seeded_replay

ap = argparse.ArgumentParser(); ap.add_argument("--ledger"); ap.add_argument("--out"); args = ap.parse_args()
root = os.path.join(os.path.dirname(__file__), "..")
cfg = yaml.safe_load(open(os.path.join(root, "config.yaml")))
out = args.out or os.path.join(root, cfg["out_dir"]); os.makedirs(out, exist_ok=True)
R = dict(deltas_usd=[1, 10, 100, 1000], thetas=[[1, 100], [1, 20], [1, 10], [1, 5]], windows_s=[1800, 3600, 7200],
         pis=[0.0, 0.5], bootstrap_clusters=2000,
         chain_fee_usd={"1": 0.01, "2": 2.0, "4": 0.10, "5": 0.02, "6": 0.10, "10": 0.05, "14": 0.01, "16": 0.05,
                        "22": 0.01, "23": 0.10, "24": 0.10, "30": 0.05, "default": 0.05})
R.update(cfg.get("robustness", {}))

led = pd.read_parquet(args.ledger or os.path.join(root, cfg["processed_dir"], "ledger.parquet"))
for c in ("amt_in_u", "amt_out_u"):
    led[c] = led[c].astype("int64")
led = led.reset_index(drop=True)
norm = lambda c: (str(c)[:-2] if str(c).endswith(".0") else str(c))
led["src_chain"] = led.src_chain.map(norm); led["dst_chain"] = led.dst_chain.map(norm)
led["src_key"] = led.src_chain + ":" + led.src_addr; led["dst_key"] = led.dst_chain + ":" + led.dst_addr
t_dep, t_wd = led.t_dep.tolist(), led.t_wd.tolist()
src, dst = led.src_key.tolist(), led.dst_key.tolist()
ain, aout = led.amt_in_u.tolist(), led.amt_out_u.tolist()
ev = sorted([(t_dep[i], 0, i) for i in range(len(led))] + [(t_wd[i], 1, i) for i in range(len(led))], key=lambda e: (e[0], e[1]))

# ---- seeds: an independent hypothetical draw with the E4 volume range (200 seeds, 1,000 to 1,000,000 USD) -------------------------------------
rng = np.random.default_rng(cfg["seed"])
vol = led.groupby("src_key")["amt_in_u"].sum()
elig = vol[(vol >= to_u(cfg["e4_seed_min_usd"])) & (vol <= to_u(cfg["e4_seed_max_usd"]))].index.to_numpy()
seeds = set(np.random.default_rng(cfg["seed"] + 7).choice(elig, size=min(cfg["e4_seed_count"], len(elig)), replace=False).tolist())

# ---- R1 ------------------------------------------------------------------------------------------------
wd = led[["t_wd", "amt_out_u", "token", "dst_chain"]]
rows, acct = [], []
variants = [("oracle", None, None)] + [(f"linker_pi{pi}", pi, w) for w in R["windows_s"] for pi in R["pis"]]
for name, pi, w in variants:
    cands = None if pi is None else candidates(led[["t_dep", "amt_in_u", "token", "dst_chain"]], wd, w, 0.02)
    arr, acc, _ = seeded_replay(ev, src, dst, ain, aout, seeds, cands, pi)
    acc.update(variant=name, window_s=w); acct.append(acc)
    tot = acc["delivered"]
    for d_usd, (p, q) in itertools.product(R["deltas_usd"], R["thetas"]):
        d = max(to_u(d_usd), 1)
        f = sum(a for a, T, B in arr if T >= d)
        full = sum(a for a, T, B in arr if T >= d and T * q >= p * B)
        rows.append(dict(variant=name, window_s=w, delta_usd=d_usd, theta=p / q, delivered_usd=tot / 1e6,
                         share_of_true_link_delivered=None,
                         visibility_floor=f / tot if tot else None, visibility_full_rule=full / tot if tot else None))
r1 = pd.DataFrame(rows)
orc = acct[0]["delivered"]
r1["share_of_true_link_delivered"] = r1.delivered_usd * 1e6 / orc if orc else None
r1.to_csv(f"{out}/R1_interaction_grid.csv", index=False)
pd.DataFrame(acct).to_csv(f"{out}/R1_conservation.csv", index=False)

# ---- R2: clustered bootstrap of victim-population leverage ---------------------------------------------
p, q = cfg["theta"]; c_tx = to_u(cfg["cost_per_transfer_usd"])
rec = led.sort_values("t_wd", kind="mergesort")
first_sender = rec.drop_duplicates("dst_key").set_index("dst_key")["src_key"]
cnt = led.groupby("dst_key").size(); hubs = set(cnt[cnt > cfg["hub_receipt_threshold"]].index)
bal = led.groupby("dst_key")["amt_out_u"].sum(); bal = bal[~bal.index.isin(hubs)]
cl = first_sender.reindex(bal.index)
def cost_vec(B, rule, d=0):
    share = np.maximum(1, -(-(p * B) // (q - p)))
    return np.ones_like(B) + c_tx if rule == "poison" else (share + c_tx if rule == "share" else np.maximum(np.maximum(d, share), 1) + c_tx)
def lev(cv, bud): return int(np.searchsorted(np.cumsum(np.sort(cv)), bud, side="right"))
groups = pd.Series(np.arange(len(bal))).groupby(cl.to_numpy()).apply(lambda s: s.to_numpy()).tolist()
Bv = bal.to_numpy().astype(np.int64)
brng = np.random.default_rng(cfg["seed"] + 2); rows = []
draws = [np.concatenate([groups[j] for j in brng.integers(0, len(groups), len(groups))]) for _ in range(R["bootstrap_clusters"])]
for bud in cfg["budgets_usd"]:
    for rule, ds in (("poison", [0]), ("share", [0]), ("bbe", [100])):
        for d in ds:
            full = lev(cost_vec(Bv, rule, to_u(d)), to_u(bud))
            v = np.array([lev(cost_vec(Bv[ix], rule, to_u(d)), to_u(bud)) for ix in draws])
            rows.append(dict(budget_usd=bud, rule=rule, delta_usd=d, flagged=full, n_clusters=len(groups), n_victims=len(Bv),
                             lo=np.quantile(v, .025), hi=np.quantile(v, .975)))
pd.DataFrame(rows).to_csv(f"{out}/R2_clustered_bootstrap.csv", index=False)

# ---- R3: heterogeneous transfer cost (cost depends on the victim's chain) ------------------------------
vchain = pd.Series(bal.index.str.split(":").str[0], index=bal.index)
fee = vchain.map(lambda c: R["chain_fee_usd"].get(c, R["chain_fee_usd"]["default"]))
cu = np.array([to_u(x) for x in fee], dtype=np.int64); cmin = float(fee.min()); rows = []
for bud in cfg["budgets_usd"]:
    for d in cfg["delta_usd"]:
        share = np.maximum(1, -(-(p * Bv) // (q - p)))
        n = lev(np.maximum(np.maximum(to_u(d), share), 1) + cu, to_u(bud))
        rows.append(dict(budget_usd=bud, delta_usd=d, flagged_BBE=n, bound_with_min_fee=bud / (d + cmin), min_fee_usd=cmin,
                         bound_holds=n <= bud / (d + cmin)))
r3 = pd.DataFrame(rows); r3.to_csv(f"{out}/R3_heterogeneous_cost.csv", index=False)
assert r3.bound_holds.all(), "Theorem 1 with c_min violated"
print("R1 rows", len(r1), "| R3 rows", len(r3), "| R3 bound holds:", bool(r3.bound_holds.all()))
