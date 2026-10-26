"""Account-based taint-propagation engine with exact integer arithmetic.

Policies: 'poison', 'haircut', 'fifo'. Flagging rules: 'poison' (T>0),
'share' (T/B >= theta), 'bbe' (T>=delta AND T/B >= theta).
Opening balances are unobserved on real data; a transfer exceeding the
tracked balance is covered by an implicit CLEAN top-up (documented assumption).
"""
from collections import deque, defaultdict


class Ledger:
    def __init__(self, policy: str):
        assert policy in ("poison", "haircut", "fifo")
        self.policy = policy
        self.bal = defaultdict(int)
        self.T = defaultdict(int)
        self.lots = defaultdict(deque) if policy == "fifo" else None  # [amt, tainted]

    # -- helpers -------------------------------------------------------
    def _push(self, a, amt, tainted):
        if amt <= 0:
            return
        d = self.lots[a]
        if d and d[-1][1] == tainted:
            d[-1][0] += amt
        else:
            d.append([amt, tainted])

    def fund(self, a, amt, tainted=False):
        """External inflow (clean or tainted) into address a."""
        self.bal[a] += amt
        if tainted:
            self.T[a] += amt
        if self.policy == "fifo":
            self._push(a, amt, tainted)

    def _topup(self, a, need):
        if self.bal[a] < need:
            self.fund(a, need - self.bal[a], False)

    def transfer(self, s, r, x):
        """Move x units from s to r under the chosen policy; returns taint moved."""
        if x <= 0 or s == r:
            return 0
        self._topup(s, x)
        if self.policy == "haircut":
            moved = x * self.T[s] // self.bal[s]
        elif self.policy == "poison":
            moved = x if self.T[s] > 0 else 0   # whole transfer becomes tainted
        else:  # fifo
            moved, left = 0, x
            d = self.lots[s]
            while left > 0:
                lot = d[0]
                take = min(lot[0], left)
                if lot[1]:
                    moved += take
                    if r is not None:
                        self._push(r, take, True)
                elif r is not None:
                    self._push(r, take, False)
                lot[0] -= take
                left -= take
                if lot[0] == 0:
                    d.popleft()
        self.bal[s] -= x
        if r is not None:
            self.bal[r] += x
        if self.policy == "poison":
            # sender keeps its taint flag only while it holds >0 balance
            if self.T[s] > 0:
                self.T[s] = self.bal[s]
            if moved and r is not None:
                self.T[r] = self.bal[r]
        else:
            self.T[s] -= moved
            if r is not None:
                self.T[r] += moved
        return moved

    def lock(self, s, x):
        """Bridge deposit: remove x units from s WITHOUT crediting any account on this
        ledger (the value leaves the chain). Returns the tainted amount that left.
        The caller must account for it explicitly (see bbe.replay)."""
        return self.transfer(s, None, x)

    def exposure_ppm(self, a):
        b = self.bal[a]
        return 0 if b == 0 else self.T[a] * 1_000_000 // b

    def flagged(self, a, rule, delta=0, theta_num=1, theta_den=10):
        t, b = self.T[a], self.bal[a]
        if t <= 0:
            return False
        if rule == "poison":
            return True
        share = t * theta_den >= theta_num * b
        if rule == "share":
            return share
        if rule == "bbe":
            return t >= delta and share
        raise ValueError(rule)

    def total_taint(self):
        return sum(self.T.values())
