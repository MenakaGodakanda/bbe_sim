"""Dust-attack economics: closed-form minimal dust and greedy leverage."""
from .units import ceil_div


def min_dust(policy_rule, B, delta=0, p=1, q=10, unit=1):
    """Smallest dust d (micro-USD) that flags a victim with clean balance B.
    Rules: 'poison' -> unit; 'share' -> ceil(pB/(q-p)); 'bbe' -> max(delta, share, unit)."""
    share = max(unit, ceil_div(p * B, q - p))
    if policy_rule == "poison":
        return unit
    if policy_rule == "share":
        return share
    if policy_rule == "bbe":
        return max(delta, share, unit)
    raise ValueError(policy_rule)


def greedy_leverage(balances, budget, rule, cost_per_transfer=0, **kw):
    """Number of victims an attacker with `budget` can flag, cheapest first."""
    costs = sorted(min_dust(rule, b, **kw) + cost_per_transfer for b in balances)
    n, spent = 0, 0
    for c in costs:
        if spent + c > budget:
            break
        spent += c
        n += 1
    return n, spent
