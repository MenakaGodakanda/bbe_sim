"""Build standard ledger (real data only) from raw parquet files."""
import os, sys, yaml
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bbe.adapters import to_ledger_report

root = os.path.join(os.path.dirname(__file__), "..")
cfg = yaml.safe_load(open(os.path.join(root, "config.yaml")))
parts, log = [], open(os.path.join(root, cfg["out_dir"], "ledger_build_report.txt"), "w")
for b in cfg["bridges"]:
    df = pd.read_parquet(os.path.join(root, cfg["raw_dir"], f"{b}_data.parquet"))
    L, m, steps, comp, dst_share = to_ledger_report(df, cfg, b)
    out_dir = os.path.join(root, cfg["out_dir"])
    steps.to_csv(os.path.join(out_dir, f"filter_steps_{b}.csv"), index=False)
    comp.to_csv(os.path.join(out_dir, f"filter_retained_vs_excluded_{b}.csv"))
    dst_share.to_csv(os.path.join(out_dir, f"filter_retention_by_dst_chain_{b}.csv"))
    print(steps.to_string(index=False), file=log); print(comp.to_string(), file=log)
    msg = f"{b}: raw={len(df)} kept={len(L)} mapping={m}"
    print(msg); print(msg, file=log)
    parts.append(L)
led = pd.concat(parts, ignore_index=True)
led.to_parquet(os.path.join(root, cfg["processed_dir"], "ledger.parquet"))
s = led.describe(include="all").T.to_string()
print(s); print(s, file=log)
