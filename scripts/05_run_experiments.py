"""Experiments on the REAL ledger. Attacker injection is an in-memory counterfactual only.
All amounts are converted to Python ints before the replay (numpy int64 would overflow
in the haircut product x*T)."""
import os, sys, yaml, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bbe.units import to_u
from bbe.engine import Ledger
from bbe.attack import min_dust
from bbe.linking import candidates, link_stats
from bbe.replay import seeded_replay

root = os.path.join(os.path.dirname(__file__), "..")
cfg = yaml.safe_load(open(os.path.join(root, "config.yaml")))
out = os.path.join(root, cfg["out_dir"]); rng = np.random.default_rng(cfg["seed"])
led = pd.read_parquet(os.path.join(root, cfg["processed_dir"], "ledger.parquet"))
for c in ("amt_in_u", "amt_out_u"):
    led[c] = led[c].astype("int64")
led = led.reset_index(drop=True)
def norm(c):
    c = str(c)
    return c[:-2] if c.endswith(".0") else c
led["src_chain"] = led.src_chain.map(norm); led["dst_chain"] = led.dst_chain.map(norm)
if cfg.get("chain_qualified", True):   # account = (chain, address); an address on two chains is two accounts
    led["src_key"] = led.src_chain + ":" + led.src_addr; led["dst_key"] = led.dst_chain + ":" + led.dst_addr
else:
    led["src_key"] = led.src_addr; led["dst_key"] = led.dst_addr
p, q = cfg["theta"]; res = {"n_transfers": int(len(led)), "chain_qualified": bool(cfg.get("chain_qualified", True)),
                            "n_dst_addresses_unqualified": int(led.dst_addr.nunique()),
                            "n_src_chains": int(led.src_chain.nunique()), "n_dst_chains": int(led.dst_chain.nunique())}
c_tx = to_u(cfg["cost_per_transfer_usd"])

# ---- populations: all destinations vs non-hub destinations ----------------
rec_cnt = led.groupby("dst_key").size()
hubs = set(rec_cnt[rec_cnt > cfg["hub_receipt_threshold"]].index)
res["n_dst_addresses"] = int(len(rec_cnt)); res["n_hubs_removed"] = len(hubs)
res["hub_share_of_value"] = float(led[led.dst_key.isin(hubs)].amt_out_u.sum() / led.amt_out_u.sum())
bal_all = led.groupby("dst_key")["amt_out_u"].sum()
pops = {"all": bal_all, "nonhub": bal_all[~bal_all.index.isin(hubs)]}
for k, v in pops.items():
    res[f"victims_{k}"] = int(len(v)); res[f"median_balance_usd_{k}"] = float(np.median(v.to_numpy()) / 1e6)

# ---- E1: link ambiguity against the FULL withdrawal pool ------------------
s = led.sample(min(cfg["link_sample"], len(led)), random_state=cfg["seed"])
dep = s[["t_dep", "amt_in_u", "token", "dst_chain"]]
wd = led[["t_wd", "amt_out_u", "token", "dst_chain"]]
truth = {i: i for i in s.index}
rows = []
for w in cfg["link_window_s"]:
    for f in cfg["link_fee_tol"]:
        st = link_stats(candidates(dep, wd, w, f), truth, 0.0); st.update(window_s=w, fee_tol=f); rows.append(st)
pd.DataFrame(rows).to_csv(f"{out}/E1_linking.csv", index=False)
cc = candidates(dep, wd, 3600, 0.02)
kk = np.array([len(v) for v in cc.values()])
pd.DataFrame([dict(link_stats(cc, truth, pi), pi=pi) for pi in [0, .1, .2, .34, .5, 1.0]]).to_csv(f"{out}/E1_pi_sweep.csv", index=False)
pd.DataFrame({"k": np.minimum(kk, 20)}).value_counts().sort_index().rename("n").reset_index().to_csv(f"{out}/E1_k_hist.csv", index=False)

# ---- E2: attacker leverage (closed form + bootstrap) ----------------------
def cost_vec(B, rule, d=0):
    share = np.maximum(1, -(-(p * B) // (q - p)))
    if rule == "poison": return np.ones_like(B) + c_tx
    if rule == "share": return share + c_tx
    return np.maximum(np.maximum(d, share), 1) + c_tx
def lev(cv, budget):
    return int(np.searchsorted(np.cumsum(np.sort(cv)), budget, side="right"))
rows, brows = [], []
brng = np.random.default_rng(cfg["seed"] + 1)
for name, ser in pops.items():
    B = ser.to_numpy().astype(np.int64)
    idx = [brng.integers(0, len(B), len(B)) for _ in range(cfg["bootstrap_n"])]
    for bud in cfg["budgets_usd"]:
        bu = to_u(bud)
        for rule, ds in (("poison", [0]), ("share", [0]), ("bbe", cfg["delta_usd"])):
            for d in ds:
                cv = cost_vec(B, rule, to_u(d)); n = lev(cv, bu)
                rows.append(dict(pop=name, budget_usd=bud, rule=rule, delta_usd=d, flagged=n,
                                 bound=(bud / (d + cfg["cost_per_transfer_usd"]) if rule == "bbe" else None)))
                if (rule != "bbe") or d == 100:
                    vals = np.array([lev(cv[ii], bu) for ii in idx])
                    brows.append(dict(pop=name, budget_usd=bud, rule=rule, delta_usd=d, mean=vals.mean(),
                                      lo=np.quantile(vals, .025), hi=np.quantile(vals, .975)))
pd.DataFrame(rows).to_csv(f"{out}/E2_leverage.csv", index=False)
pd.DataFrame(brows).to_csv(f"{out}/E2b_bootstrap.csv", index=False)

# ---- event list with plain Python ints -------------------------------------
t_dep = led.t_dep.tolist(); t_wd = led.t_wd.tolist()
src = led.src_key.tolist(); dst = led.dst_key.tolist()
ain = led.amt_in_u.tolist(); aout = led.amt_out_u.tolist()
ev = [(t_dep[i], 0, i) for i in range(len(led))] + [(t_wd[i], 1, i) for i in range(len(led))]
ev.sort(key=lambda e: (e[0], e[1]))
first_recv = {}
for t, kind, i in ev:
    if kind == 1 and dst[i] not in first_recv:
        first_recv[dst[i]] = i
cand = [a for a in first_recv if a not in hubs]
vict = set(rng.choice(cand, size=min(cfg["victim_sample"], len(cand)), replace=False).tolist())

# ---- E3: counterfactual replay vs closed form (non-hub victims) ------------
rows = []
# propagation policy x flag rule (3 x 3): separates the effect of propagation from the effect of the flag rule.
# Poison propagation is non-conserving, so its rows are baselines, not candidates.
E3_GRID = [(pol, rule, (to_u(100) if rule == "bbe" else 0)) for pol in ("poison", "haircut", "fifo")
           for rule in ("poison", "share", "bbe")]
for pol, rule, delta in E3_GRID:
    L = Ledger(pol); done = {}; mism = 0; now = 0
    for t, kind, i in ev:
        if kind == 0:
            L.transfer(src[i], "BRIDGE", ain[i])
        else:
            a = dst[i]; L.fund(a, aout[i])
            if a in vict and a not in done:
                d = min_dust(rule, L.bal[a], delta=delta, p=p, q=q)
                L.fund("ATT", d, True); L.transfer("ATT", a, d); done[a] = d
                ok = L.flagged(a, rule, delta, p, q); now += ok; mism += (not ok)
    pers = sum(L.flagged(a, rule, delta, p, q) for a in done)
    rows.append(dict(policy=pol, rule=rule, delta_usd=delta / 1e6, injected=len(done), flagged_immediately=now,
                     closed_form_mismatch=mism, flagged_at_end=pers, mean_dust_usd=float(np.mean(list(done.values()))) / 1e6,
                     median_dust_usd=float(np.median(list(done.values()))) / 1e6,
                     taint_conserved=(L.total_taint() == sum(done.values())) if pol != "poison" else None,
                     conserving_policy=(pol != "poison")))
pd.DataFrame(rows).to_csv(f"{out}/E3_replay.csv", index=False)

# ---- E4: recall of genuinely tainted value arriving at destinations --------
ofac = set()
fp = os.path.join(root, cfg["raw_dir"], "sanctioned_addresses_ETH.txt")
if os.path.exists(fp):
    ofac = {l.strip().lower() for l in open(fp) if l.strip()}
res["ofac_overlap_src"] = len(set(led.src_addr) & ofac); res["ofac_overlap_dst"] = len(set(led.dst_addr) & ofac)
if res["ofac_overlap_src"]:
    seeds, stype = set(led.loc[led.src_addr.isin(ofac), "src_key"]), "ofac"
else:  # what-if on REAL flows: addresses assumed illicit; labelled as hypothetical in outputs
    vol = led.groupby("src_key")["amt_in_u"].sum()
    elig = vol[(vol >= to_u(cfg["e4_seed_min_usd"])) & (vol <= to_u(cfg["e4_seed_max_usd"]))].index.to_numpy()
    seeds = set(rng.choice(elig, size=min(cfg["e4_seed_count"], len(elig)), replace=False).tolist())
    stype = "hypothetical_seeds_on_real_flows"
res["e4_seed_type"] = stype; res["e4_n_seeds"] = len(seeds)
cands = candidates(led[["t_dep", "amt_in_u", "token", "dst_chain"]], wd, 3600, 0.02)
rows, acct_rows = [], []
for variant, pi in [("oracle", None)] + [(f"linker_pi{x}", x) for x in cfg["linker_pi_variants"]]:
    arrivals, acc, _L = seeded_replay(ev, src, dst, ain, aout, seeds, None if pi is None else cands, pi)
    acc.update(variant=variant); acct_rows.append(acc)
    seeded = acc["seeded"]; tot = acc["delivered"]
    for d in [0] + [to_u(x) for x in cfg["delta_usd"]]:
        seen = sum(a for a, T, B in arrivals if T >= max(d, 1))
        seen_full = sum(a for a, T, B in arrivals if T >= max(d, 1) and T * q >= p * B)  # floor AND share condition
        rows.append(dict(seed_type=stype, variant=variant, delta_usd=d / 1e6, arrivals=len(arrivals),
                         seeded_usd=seeded / 1e6, tainted_arrived_usd=tot / 1e6,
                         arrival_volume_over_seeded=(tot / seeded if seeded else None),
                         visibility_floor=(seen / tot if tot else None),
                         visibility_full_rule=(seen_full / tot if tot else None)))
pd.DataFrame(acct_rows).to_csv(f"{out}/E4_conservation.csv", index=False)
for r in rows: r["recall"] = r["visibility_floor"]   # legacy column name kept for older scripts
pd.DataFrame(rows).to_csv(f"{out}/E4_recall.csv", index=False)

# ---- E5: case study (non-hub, median balance, >=3 receipts) ----------------
cnt = led.groupby("dst_key").size(); nb = pops["nonhub"]
cset = nb[nb.index.isin(cnt[cnt >= 3].index)]
case = (cset - np.median(cset.to_numpy())).abs().idxmin()
evc = [(t, k, i) for t, k, i in ev if (src[i] == case and k == 0) or (dst[i] == case and k == 1)]
trace = []
for pol, rule, delta in [("poison", "poison", 0), ("haircut", "share", 0), ("fifo", "bbe", to_u(100))]:
    L = Ledger(pol); done = False
    for t, kind, i in evc:
        if kind == 0:
            L.transfer(case, "BRIDGE", ain[i]); trace.append(dict(policy=pol, rule=rule, t=t, event="out", dust_usd=None))
        else:
            L.fund(case, aout[i]); ev_name = "in"; dv = None
            if not done:
                d = min_dust(rule, L.bal[case], delta=delta, p=p, q=q)
                L.fund("ATT", d, True); L.transfer("ATT", case, d); done = True; ev_name = "in+dust"; dv = d / 1e6
            trace.append(dict(policy=pol, rule=rule, t=t, event=ev_name, dust_usd=dv))
        trace[-1].update(bal_usd=L.bal[case] / 1e6, taint_usd=L.T[case] / 1e6, flagged=L.flagged(case, rule, delta, p, q))
pd.DataFrame(trace).to_csv(f"{out}/E5_case_trace.csv", index=False)

# ---- E6: breakdown by destination chain and chain pair ----------------------
CHAIN = {"1": "Solana", "2": "Ethereum", "4": "BNB Chain", "5": "Polygon", "6": "Avalanche", "10": "Fantom",
         "13": "Klaytn", "14": "Celo", "16": "Moonbeam", "21": "Sui", "22": "Aptos", "23": "Arbitrum", "24": "Optimism", "30": "Base"}
kk_by = pd.Series({i: len(v) for i, v in cc.items()})
rows = []
for ch, g in led.groupby("dst_chain"):
    b = g.groupby("dst_key")["amt_out_u"].sum(); b = b[~b.index.isin(hubs)]
    B = b.to_numpy().astype(np.int64)
    if len(B) == 0: continue
    bu = to_u(1000); sk = kk_by[kk_by.index.isin(g.index)]
    rows.append(dict(dst_chain=ch, name=CHAIN.get(ch, ""), n_transfers=len(g), n_victims=len(B),
                     median_balance_usd=float(np.median(B)) / 1e6,
                     poison=lev(cost_vec(B, "poison"), bu), share=lev(cost_vec(B, "share"), bu),
                     bbe_floor100=lev(cost_vec(B, "bbe", to_u(100)), bu), bound=int(1000 / (100 + cfg["cost_per_transfer_usd"])),
                     sampled_deposits=len(sk), mean_k=(float(sk.mean()) if len(sk) else None),
                     share_unique=(float((sk == 1).mean()) if len(sk) else None)))
pd.DataFrame(rows).sort_values("n_transfers", ascending=False).to_csv(f"{out}/E6_by_dst_chain.csv", index=False)
pr = led.groupby(["src_chain", "dst_chain"]).agg(n_transfers=("amt_in_u", "size"), value_usd=("amt_in_u", lambda x: x.sum() / 1e6))
pr.sort_values("n_transfers", ascending=False).head(25).to_csv(f"{out}/E6_chain_pairs.csv")
res["case_address"] = case; res["E1_mean_k_central"] = float(kk.mean())
json.dump(res, open(f"{out}/summary.json", "w"), indent=2)
print(json.dumps(res, indent=2))
