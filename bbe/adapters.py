"""Map a real bridge parquet to the standard ledger schema. Real data only."""
import re
import pandas as pd
from .units import MICRO

GUESS = {
 "src_addr": ["src_addr","from_address","sender","source_address","from","src_sender","depositor"],
 "dst_addr": ["dst_addr","to_address","recipient","destination_address","to","dst_recipient","receiver"],
 "token": ["token","token_symbol","symbol","asset","src_token","token_address"],
 "amt_in": ["amt_in","amount_in","src_amount","amount_sent","amount","value_in","src_value"],
 "amt_out": ["amt_out","amount_out","dst_amount","amount_received","value_out","dst_value"],
 "t_dep": ["t_dep","src_timestamp","timestamp_src","deposit_timestamp","src_time","timestamp","block_timestamp_src"],
 "t_wd": ["t_wd","dst_timestamp","timestamp_dst","withdraw_timestamp","dst_time","block_timestamp_dst"],
 "src_chain": ["src_chain","source_chain","src_blockchain","chain_src","from_chain"],
 "dst_chain": ["dst_chain","destination_chain","dst_blockchain","chain_dst","to_chain"],
 "fee": ["fee","fee_usd","bridge_fee"],
 "pair_id": ["pair_id","id","transfer_id","message_id"],
}

def _find(cols, names):
    low = {c.lower(): c for c in cols}
    for n in names:
        if n in low:
            return low[n]
    return None

def resolve(cols, cfg):
    m = {}
    for k, names in GUESS.items():
        m[k] = cfg.get(k) or _find(cols, names)
    return m

def _ts(s):
    if pd.api.types.is_datetime64_any_dtype(s):
        if getattr(s.dt, "tz", None) is not None:
            s = s.dt.tz_convert("UTC").dt.tz_localize(None)
        sec = s.astype("int64") // 10**9
        return sec.where(s.notna())   # NaT -> NaN (rows dropped later)
    s = pd.to_numeric(s, errors="coerce")
    return (s // 1000) if s.dropna().median() > 1e11 else s

def _build_all(df, cfg, bridge):
    m = resolve(list(df.columns), cfg["columns"])
    need = ["src_addr","dst_addr","amt_in","t_dep","t_wd"]
    missing = [k for k in need if not m[k]]
    if missing:
        raise SystemExit(f"Cannot map columns {missing}. Fill 'columns:' in config.yaml using outputs/schema_report.txt")
    L = pd.DataFrame()
    L["src_addr"] = df[m["src_addr"]].astype(str).str.lower()
    L["dst_addr"] = df[m["dst_addr"]].astype(str).str.lower()
    L["token"] = df[m["token"]].astype(str) if m["token"] else "NA"
    scale = 10 ** (cfg.get("decimals") or 0)
    def amt(c):
        v = pd.to_numeric(df[c], errors="coerce") / scale
        return (v * MICRO).round().astype("Int64")
    L["amt_in_u"] = amt(m["amt_in"])
    L["amt_out_u"] = amt(m["amt_out"]) if m["amt_out"] else L["amt_in_u"]
    L["t_dep"] = _ts(df[m["t_dep"]]); L["t_wd"] = _ts(df[m["t_wd"]])
    L["src_chain"] = df[m["src_chain"]].astype(str) if m["src_chain"] else "NA"
    L["dst_chain"] = df[m["dst_chain"]].astype(str) if m["dst_chain"] else "NA"
    L["fee_u"] = (L["amt_in_u"] - L["amt_out_u"]).clip(lower=0)
    L["pair_id"] = df[m["pair_id"]].astype(str) if m["pair_id"] else df.index.astype(str)
    L["bridge"] = bridge
    return L, m


def to_ledger_report(df, cfg, bridge):
    """Ledger plus a filtering report: row counts after each cumulative filter, and a comparison
    of retained vs excluded records (so a reader can judge whether filtering biases the sample)."""
    L, m = _build_all(df, cfg, bridge)
    n0 = len(L)
    s1 = L.amt_in_u.notna() & L.amt_out_u.notna()
    s2 = s1 & L.t_dep.notna() & L.t_wd.notna()
    s3 = s2 & (L.amt_in_u > 0) & (L.amt_out_u > 0)
    s4 = s3 & (L.t_wd >= L.t_dep)
    steps = pd.DataFrame([
        ("all records in file", n0), ("with a dollar value at both ends", int(s1.sum())),
        ("... and with creation and completion times", int(s2.sum())),
        ("... and with positive values", int(s3.sum())),
        ("... and completion not before creation (retained)", int(s4.sum()))], columns=["step", "records"])
    steps["share_of_all"] = steps.records / n0
    L = L.assign(kept=s4)
    def summ(g):
        v = g.amt_in_u.astype("float64") / MICRO
        return pd.Series(dict(records=len(g), median_usd=v.median(), mean_usd=v.mean(), p25=v.quantile(.25), p75=v.quantile(.75),
                              n_src_chains=g.src_chain.nunique(), n_dst_chains=g.dst_chain.nunique(),
                              n_tokens=g.token.nunique(), first_dep=g.t_dep.min(), last_dep=g.t_dep.max()))
    comp = L.groupby("kept").apply(summ, include_groups=False)
    comp.index = comp.index.map({True: "retained", False: "excluded"})
    dst_share = (L.groupby("dst_chain").kept.agg(["size", "mean"]).rename(columns={"size": "records", "mean": "share_retained"})
                 .sort_values("records", ascending=False))
    return L[L.kept].drop(columns="kept").reset_index(drop=True), m, steps, comp, dst_share


def to_ledger(df, cfg, bridge):
    L, m, *_ = to_ledger_report(df, cfg, bridge)
    return L, m
