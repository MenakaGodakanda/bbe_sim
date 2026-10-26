"""Seeded replay of bridged flows with explicit cross-chain taint accounting (Algorithm 4, seeded mode).

Cross-chain bookkeeping. A deposit REMOVES m tainted units from the source ledger (Ledger.lock);
nothing is credited on the bridge side. Each unit of m is then assigned to exactly one of the
categories below, so taint is never duplicated and every loss is named:

  not_followed : deposit has no candidate, or 1/k < pi (link not followed)
  remainder    : floor remainder m - k*floor(m/k) of a followed link
  capped       : allocated to a withdrawal j beyond the amount y_j that j actually pays out
                 (arises when candidate sets overlap and j is allocated by several deposits)
  leftover     : still pending when the replay ends
  delivered    : credited as tainted value at the receiver (Ledger.fund)

Identity checked on every run:  sum(m) = not_followed + remainder + capped + leftover + delivered.
System-wide: seeded_taint = taint_on_ledger + (sum(m) - delivered), because delivered taint is the
only taint ever created on a destination ledger and it is always covered by a prior lock.
"""
from .engine import Ledger


def seeded_replay(ev, src, dst, ain, aout, seeds, cands=None, pi=None, check=True):
    """ev: sorted events (t, kind, i), kind 0 = deposit, 1 = withdrawal (deposits first on ties).
    cands: dict i -> iterable of candidate withdrawal ids (None => oracle link i -> i).
    pi: confidence threshold (ignored for oracle). Returns (arrivals, accounting, ledger).
    arrivals: list of (tainted_amount, taint_after, balance_after) per tainted arrival."""
    L = Ledger("fifo")
    pend, arrivals = {}, []
    acc = dict(seeded=0, locked_taint=0, not_followed=0, remainder=0, capped=0, leftover=0, delivered=0)
    for t, kind, i in ev:
        if kind == 0:
            a, x = src[i], ain[i]
            if a in seeds:
                L.fund(a, x, True)
                acc["seeded"] += x
            m = L.lock(a, x)
            if m:
                acc["locked_taint"] += m
                if cands is None:                       # oracle: the true link
                    pend[i] = pend.get(i, 0) + m
                else:
                    c = list(cands[i]); k = len(c)
                    if k >= 1 and 1.0 / k >= pi:
                        sh = m // k
                        acc["remainder"] += m - sh * k
                        for j in c:
                            pend[j] = pend.get(j, 0) + sh
                    else:
                        acc["not_followed"] += m
        else:
            a, x = dst[i], aout[i]
            p_i = pend.pop(i, 0)
            tj = min(p_i, x)
            acc["capped"] += p_i - tj
            L.fund(a, x - tj, False)
            if tj:
                L.fund(a, tj, True)
                acc["delivered"] += tj
                arrivals.append((tj, L.T[a], L.bal[a]))
    acc["leftover"] = sum(pend.values())
    if check:
        lhs = acc["locked_taint"]
        rhs = acc["not_followed"] + acc["remainder"] + acc["capped"] + acc["leftover"] + acc["delivered"]
        assert lhs == rhs, ("cross-chain taint accounting broken", acc)
        assert acc["delivered"] <= acc["locked_taint"], "delivered more taint than was locked"
        assert L.total_taint() == acc["seeded"] - acc["locked_taint"] + acc["delivered"], "system taint identity"
    return arrivals, acc, L

