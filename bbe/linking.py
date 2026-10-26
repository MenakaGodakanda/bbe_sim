"""Cross-chain bridge-link inference: candidate matching, ambiguity, weights."""
import numpy as np
import pandas as pd


def candidates(dep: pd.DataFrame, wd: pd.DataFrame, window_s: int, fee_tol: float):
    """Candidate withdrawals for each deposit row. `wd` is the FULL withdrawal pool
    (never a thinned sample, which would understate ambiguity). Index labels of `wd`
    are returned. Match: same token and destination chain, withdrawal within
    window_s after the deposit, amount in [(1-fee_tol)*in, in]."""
    groups = {}
    # Deterministic: stable sort by (time, index) so ties never depend on input order.
    # Candidate sets of different deposits may overlap; allocation is handled in bbe.replay.
    for key, g in wd.assign(_ix=wd.index).sort_values(["t_wd", "_ix"], kind="mergesort").groupby(["token", "dst_chain"]):
        groups[key] = (g["t_wd"].to_numpy(), g["amt_out_u"].to_numpy(), g.index.to_numpy())
    empty = np.array([], dtype=np.int64)
    out = {}
    for i, t, a, tok, dc in zip(dep.index, dep["t_dep"].to_numpy(), dep["amt_in_u"].to_numpy(),
                                dep["token"], dep["dst_chain"]):
        g = groups.get((tok, dc))
        if g is None:
            out[i] = empty
            continue
        tw, aw, ix = g
        lo = np.searchsorted(tw, t, "left")
        hi = np.searchsorted(tw, t + window_s, "right")
        a_ = aw[lo:hi]
        out[i] = ix[lo:hi][(a_ <= a) & (a_ >= a * (1.0 - fee_tol))]
    return out


def link_stats(cands: dict, truth: dict, pi: float = 0.0):
    """Recall/precision of uniform-weight linking at confidence threshold pi, plus k."""
    ks, hit, tot, emitted, correct = [], 0, 0, 0, 0
    for d, cs in cands.items():
        k = len(cs)
        ks.append(k)
        tot += 1
        if k and 1.0 / k >= pi:
            emitted += 1
            if truth.get(d) in set(cs):
                hit += 1
                correct += 1
    ks = np.array(ks)
    return {"n": tot, "mean_k": float(ks.mean()) if tot else 0.0,
            "p_k1": float((ks == 1).mean()) if tot else 0.0,
            "recall": hit / tot if tot else 0.0,
            "precision": correct / emitted if emitted else 0.0}
