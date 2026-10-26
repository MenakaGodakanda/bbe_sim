"""How are the deposit-withdrawal pairs of the Wormhole file identified, and are Tables 6 and 7 complete?  (REAL data only)

Each Wormhole record carries srcTxhash (source-chain deposit) and dstTxhash (destination-chain withdrawal). The study uses
the record itself as the reference pair (pair_id = _id) and never matches deposits to withdrawals for the reference link.
This script measures how clean that pairing is:
  * how many records carry both hashes, and whether each hash occurs once (a one-to-one pairing) or repeats;
  * the same checks for the 250,527 retained records;
  * whether srcUSD equals dstUSD and whether completion is after creation (context for the linker experiments).
It also writes the complete chain-pair table behind Table 7 (all pairs, and the top 25 by value), because the
earlier file E6_chain_pairs.csv kept only the 25 busiest pairs by number of transfers.

Usage: python3 scripts/11_pairing_check.py [--raw FILE --ledger FILE --out DIR]   (options only for smoke tests)
Output: outputs/pairing_check.csv, E6_chain_pairs_all.csv, E6_chain_pairs_top_by_value.csv
"""
import os, sys, argparse
import pandas as pd, yaml
ap = argparse.ArgumentParser(); ap.add_argument("--raw"); ap.add_argument("--ledger"); ap.add_argument("--out"); a = ap.parse_args()
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
cfg = yaml.safe_load(open(os.path.join(root, "config.yaml")))
out = a.out or os.path.join(root, cfg["out_dir"]); os.makedirs(out, exist_ok=True)
raw = pd.read_parquet(a.raw or os.path.join(root, cfg["raw_dir"], "wormhole_data.parquet"))
led = pd.read_parquet(a.ledger or os.path.join(root, cfg["processed_dir"], "ledger.parquet"))

def norm(h):  # the file sometimes writes '0x0x...' for the destination hash
    h = h.astype("string").str.strip().str.lower()
    return h.str.replace(r"^(0x)+", "0x", regex=True)

raw["_id"] = raw["_id"].astype(str)
raw["src_h"], raw["dst_h"] = norm(raw["srcTxhash"]), norm(raw["dstTxhash"])
raw["retained"] = raw["_id"].isin(set(led["pair_id"].astype(str)))
rows = []
for name, g in (("all records", raw), ("retained (ledger)", raw[raw.retained]), ("excluded", raw[~raw.retained])):
    both = g.src_h.notna() & g.dst_h.notna()
    gb = g[both]
    rows.append(dict(group=name, records=len(g), with_src_hash=int(g.src_h.notna().sum()), with_dst_hash=int(g.dst_h.notna().sum()),
                     with_both_hashes=int(both.sum()),
                     src_hash_unique_share=float((~gb.src_h.duplicated(keep=False)).mean()) if len(gb) else None,
                     dst_hash_unique_share=float((~gb.dst_h.duplicated(keep=False)).mean()) if len(gb) else None,
                     distinct_src_dst_pairs=int(gb[["src_h", "dst_h"]].drop_duplicates().shape[0]),
                     same_usd_both_ends_share=float((g.srcUSD == g.dstUSD).mean()),
                     completion_not_before_creation_share=float((g.completeTime >= g.createTime).mean())))
pd.DataFrame(rows).to_csv(f"{out}/pairing_check.csv", index=False)
print(pd.DataFrame(rows).T.to_string())

norm_c = lambda c: (str(c)[:-2] if str(c).endswith(".0") else str(c))
led["src_chain"], led["dst_chain"] = led.src_chain.map(norm_c), led.dst_chain.map(norm_c)
pr = led.groupby(["src_chain", "dst_chain"]).agg(n_transfers=("amt_in_u", "size"), value_usd=("amt_in_u", lambda x: x.sum() / 1e6)).reset_index()
pr.sort_values("n_transfers", ascending=False).to_csv(f"{out}/E6_chain_pairs_all.csv", index=False)
pr.sort_values("value_usd", ascending=False).head(25).to_csv(f"{out}/E6_chain_pairs_top_by_value.csv", index=False)
print("pairs:", len(pr), "| largest by value:", pr.sort_values("value_usd", ascending=False).head(1).values.tolist())
