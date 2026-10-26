# Scripts, formulas, algorithms and outputs explained

This guide explains, in plain language, what every script does, what each formula and algorithm of the paper means, which line of code implements it, and where each output file appears in the paper. You do not need a background in blockchains or taint analysis to follow it.

Contents

1. [The idea in five minutes](#1-the-idea-in-five-minutes)
2. [Notation](#2-notation)
3. [The formulas, one by one](#3-the-formulas-one-by-one)
4. [Theorem 1 in plain words](#4-theorem-1-in-plain-words)
5. [The algorithms, one by one](#5-the-algorithms-one-by-one)
6. [The scripts, one by one](#6-the-scripts-one-by-one)
7. [Where each output appears in the paper](#7-where-each-output-appears-in-the-paper)
8. [Where each paper figure comes from](#8-where-each-paper-figure-comes-from)
9. [What each test proves](#9-what-each-test-proves)
10. [How to check one number from the paper](#10-how-to-check-one-number-from-the-paper)

Section numbers, table numbers, figure numbers and equation numbers below refer to the paper.

---

## 1. The idea in five minutes

**Taint.** Compliance teams follow money from account to account. If an account received money that can be traced back to a criminal or sanctioned source, part of its balance is called *tainted*. An account with a balance of 200 dollars, of which 50 dollars can be traced back to an illicit source, has taint `T = 50`.

**Flagging.** A screening system decides whether an account is "too exposed". If it is, the account is *flagged*: an exchange may block it, or an analyst may review it.

**Dusting.** On most blockchains you cannot refuse an incoming transfer. An attacker who holds some tainted money can send a small amount to many innocent accounts. If the screening rule is naive, all of those accounts now look exposed and get flagged. This is dusting.

**Cost to the attacker.** The attacker pays for the dust and for the fee `c` of every transfer. The question of the paper is: *how many innocent accounts can an attacker flag with a given budget `B`?*

**Three flagging rules compared.**

| Rule | An account is flagged when | What it costs the attacker per victim |
|---|---|---|
| Poison | it holds any taint at all | almost nothing (one unit of money) |
| Share rule | its tainted share `T/balance` is at least `theta` (for example 10%) | about one ninth of the victim's balance, so little for poor victims |
| **BBE** | `T >= delta` **and** `T >= theta x balance` | at least `delta`, whatever the victim's balance |

**Bridges.** A bridge moves money from one blockchain to another. The money is locked on the first chain and released on the second chain, but the two events are separate. A screening system that wants to follow taint across a bridge has to *guess* which withdrawal belongs to which deposit. A bad guess can spread taint to the wrong people, so BBE spreads taint over the candidates in a way that never creates new taint, and ignores guesses that are too uncertain.

**What the code does.** It takes 250,527 real transfers on the Wormhole bridge, replays them, and measures: how ambiguous the bridge matching is (E1), how many victims an attacker can flag under each rule (E2), whether a real replay agrees with the formulas (E3), how much of an assumed illicit flow BBE still sees (E4), what happens to one real account (E5), and whether the results depend on the chain (E6). Then it varies the design choices (S1 to S6) and tests dependence and interactions (R1 to R3).

---

## 2. Notation

| Symbol | Meaning | In the code |
|---|---|---|
| `B_a` | balance of account `a` (all value it holds) | `Ledger.bal[a]` |
| `T_a` | tainted part of the balance, `0 <= T_a <= B_a` | `Ledger.T[a]` |
| `delta` (δ) | the floor: smallest tainted amount that can be flagged, in US dollars | `delta_usd` in `config.yaml` |
| `theta` (θ) = `p/q` | share threshold, for example 1/10 = 10% | `theta: [1, 10]` |
| `B` (in Theorem 1) | the attacker's total budget | `budgets_usd` |
| `c` | the attacker's fee per transfer | `cost_per_transfer_usd` |
| `u` | smallest transferable unit, 1 micro-US-dollar | `units.MICRO` |
| `V` | a victim's clean balance before the dust | `bal[a]` |
| `D` | total tainted value the attacker injects | |
| `f` | number of addresses flagged at one instant | |
| `Δ` (Delta) | matching window in seconds | `link_window_s` |
| `φ` (phi) | fee tolerance of the linker, for example 2% | `link_fee_tol` |
| `k_i` | ambiguity: number of candidate withdrawals of deposit `i` | `len(candidates[i])` |
| `π` (pi) | confidence threshold: a link is followed only if `1/k >= π` | `linker_pi_variants` |
| `m` | tainted amount carried by a bridge deposit | |
| `τ_j` | tainted value delivered by withdrawal `j` | |

**Units.** All money is stored as an integer number of micro-dollars (1 USD = 1,000,000 units). Integers never round, so total taint is conserved exactly and thresholds are compared exactly. `bbe/units.py` converts with `to_u()` and provides `ceil_div()`.

---

## 3. The formulas, one by one

### Equation (1): haircut propagation

```
ΔT = floor( x · T_s / B_s )
```

**Meaning.** When a sender `s` moves `x` units to a receiver, the amount of taint that moves is proportional to the sender's tainted share. The floor operator keeps the result an integer; any remainder stays with the sender, so the total taint in the system does not change.

**Example.** The sender holds 200 and 50 of it is tainted. It sends 80. Taint moved: floor(80 x 50 / 200) = 20. After the transfer the sender holds 120 with 30 tainted, and the receiver gains 80 with 20 tainted. Total taint: 50 before and 50 after.

**Code.** `Ledger.transfer` in `bbe/engine.py`, branch `self.policy == "haircut"`: `moved = x * self.T[s] // self.bal[s]`.

**Used by.** The "share rule" rows of E2 and E3, and optionally BBE with haircut (E3, S3).

The two other propagation rules sit beside it in the same function. **Poison** marks the whole transfer as tainted if the sender has any taint (it does *not* conserve taint, so it is only a baseline). **FIFO** keeps each account's money as a queue of lots, each marked clean or tainted, and moves the oldest lots first (it conserves taint). BBE uses FIFO unless stated otherwise.

### Equation (2): the BBE flag rule

```
flag(a)  ⟺  T_a > 0  and  T_a >= δ  and  T_a >= θ · B_a
```

**Meaning.** An account is flagged only if it holds some taint, at least `δ` dollars of it, and the taint is at least a share `θ` of the whole balance. The floor stops attackers from flagging poor users with a trace amount. The share condition stops the defender from flagging rich users merely because they received a tainted amount that is negligible against their holdings.

**Example** (δ = 100, θ = 10%).

| Account | Balance | Tainted | Share | Poison | Share rule | BBE |
|---|---|---|---|---|---|---|
| A | 1,000 | 150 | 15% | flagged | flagged | **flagged** |
| B | 30 | 5 | 16.7% | flagged | flagged | not flagged (5 < 100) |
| C | 5,000 | 150 | 3% | flagged | not flagged | not flagged (share too small) |

**Code.** `Ledger.flagged(a, rule, delta, theta_num, theta_den)` in `bbe/engine.py`. The share test is done in integers: `t * theta_den >= theta_num * b`, so there is no rounding at the threshold. For BBE it is `t >= delta and share`.

**Used by.** Every experiment that counts flags (E2, E3, E5, E6, S1 to S6, R1 to R3).

### Equation (3): the cheapest dust that flags a victim

```
d_poison = u
d_share  = max( u , ceil( p·V / (q − p) ) )
d_BBE    = max( δ , d_share )
```

**Meaning.** For a victim with clean balance `V`, this is the smallest tainted amount `d` that the attacker must send to make the victim flagged.

**Where the share formula comes from.** After the dust the victim holds `V + d`, of which `d` is tainted. The share rule needs `d / (V + d) >= p/q`. Solving gives `d >= p·V / (q − p)`, rounded up to a whole unit. With θ = 10% (p = 1, q = 10) this is `V / 9`: about one ninth of the victim's balance.

**Example** (θ = 10%, δ = 100 dollars).

| Victim balance `V` | Poison | Share rule | BBE |
|---|---|---|---|
| 30 | 0.000001 | 30 / 9 = 3.34 (rounded up to a unit) | max(100, 3.34) = **100** |
| 450 | 0.000001 | 50 | max(100, 50) = **100** |
| 900 | 0.000001 | 100 | 100 (the floor stops binding here) |
| 2,000 | 0.000001 | 222.23 | max(100, 222.23) = **222.23** |

The floor `δ` only matters for victims with `V <= δ(q − p)/p`, which is 900 dollars for δ = 100 and θ = 10%. Richer victims are already protected by the share condition. This is why BBE adds protection for the many low-balance accounts and nothing for wealthy ones (Section 4.9, "Opening balance").

**Code.** `min_dust()` in `bbe/attack.py` (the reference, used by tests and by the replays) and the vectorised `cost_vec()` in `scripts/05_run_experiments.py`, `08_sensitivity.py` and `09_robustness.py`: `share = max(1, ceil_div(p*B, q-p))`.

### Equation (4): the attacker's cost per victim

```
cost_R(V) = d_R(V) + c
```

**Meaning.** The attacker pays the dust plus one transfer fee. With `c = 0.05` dollars and δ = 100, every victim below 900 dollars costs the attacker 100.05 dollars under BBE, but only about 0.05 dollars under poison.

**Code.** Same functions as Equation (3); the fee is `c_tx = to_u(cost_per_transfer_usd)`.

### Equation (5): visibility of tainted value at arrival

```
vis(δ) = ( Σ_j τ_j · 1[ T_j >= max(δ, 1) ] ) / ( Σ_j τ_j )
```

**Meaning.** The *price* of the floor. A launderer wants to avoid being seen. `τ_j` is the tainted value delivered by withdrawal `j`; `T_j` is the tainted amount the receiving account holds just after the delivery. The formula is the share of delivered tainted value that sits at an account holding at least `δ` of taint. Its complement `1 − vis(δ)` is the *evadable mass*: the tainted value that the floor lets through. This is **not** classifier recall against labelled illicit accounts; it describes the moment of arrival only.

**Example** (δ = 100). Three arrivals: `τ = 500` at an account with `T = 500`; `τ = 50` at an account with `T = 50`; `τ = 450` at an account with `T = 1,000`. Visible value = 500 + 450 = 950 out of 1,000, so `vis = 95%`, and 5% escapes.

**Full-rule version.** The paper also reports the share of arriving value held at an account that BBE would *actually flag*: `T >= δ` **and** `T x q >= p x B` (the share condition too). In the code this is `visibility_full_rule`; the floor-only version is `visibility_floor`.

**Code.** The arrival list is produced by `seeded_replay` in `bbe/replay.py` (it records `(τ, T[a], bal[a])` at every tainted arrival). The sums are in `scripts/05_run_experiments.py` (E4) and `scripts/09_robustness.py` (R1).

### Equation (6): candidate withdrawals of a deposit

```
C_i = { j : token_j = token_i,  chain_j = chain_i,  t_i <= t'_j <= t_i + Δ,  (1 − φ)·x_i <= y_j <= x_i },    k_i = |C_i|
```

**Meaning.** A withdrawal `j` could belong to deposit `i` if it has the same token and the same destination chain, happens within the window `Δ` after the deposit, and pays out an amount that equals the deposit minus a fee of at most a fraction `φ`. The number of candidates `k_i` is the *ambiguity*: `k = 1` means the match is certain under the rule, and a large `k` means it is close to a guess.

**Example.** A deposit of 1,000 USDC at 12:00 to chain 22. With `Δ` = 1 hour and `φ` = 2%, every USDC withdrawal on chain 22 between 12:00 and 13:00 that pays between 980 and 1,000 is a candidate. If there are 4, then `k = 4`.

**Code.** `candidates()` in `bbe/linking.py`. Withdrawals are grouped by `(token, destination chain)` and sorted by time and index, so the time range is found by binary search (`searchsorted`); the amount bounds are evaluated in floating point. The sort is stable, so the result does not depend on the input order. `link_stats()` in the same file computes mean `k`, the share with exactly one candidate, and the recall and precision of the candidate sets.

**Used by.** E1 (against the full pool of 250,527 withdrawals), E4, S4, R1.

### The conserving weights (Section 3.5 and Algorithm 2)

A **copying** linker would give the whole tainted amount `m` to every one of the `k` candidates, which multiplies taint by `k` and breaks the bound. A **conserving** linker gives each candidate `floor(m / k)`. The remainder (fewer than `k` units) is not delivered. The weight `1/k` is an *allocation rule*, not a probability that the candidate is the true recipient. A link is followed only if `1/k >= π`.

**Example.** A deposit carries `m = 300` tainted. With `k = 4`: each candidate gets 75. With `k = 7`: each gets floor(300/7) = 42 and 6 units remain. With `π = 0.5` the link with `k = 7` is not followed at all (1/7 < 0.5) and the 300 are recorded as *not followed*.

**Code.** The `WEIGHTS` step is inside `seeded_replay` in `bbe/replay.py`: `sh = m // k`, `remainder += m - sh*k`, `if k >= 1 and 1.0/k >= pi`.

### Equation (7): the accounting identity

```
m_dep = m_del + m_nf + m_rem + m_cap + m_pend          and          T_ledger = T_seed − m_dep + m_del
```

**Meaning.** When tainted value enters a bridge, it leaves the source ledger and nothing is credited on the bridge side, so taint is never counted twice. Every unit of that tainted value must end in exactly one of five categories: **delivered** to a receiver (`m_del`), **not followed** because there was no candidate or `1/k < π` (`m_nf`), **floor remainder** of a followed link (`m_rem`), **capped** because several deposits allocated taint to the same withdrawal and the withdrawal can deliver at most the amount it actually pays out (`m_cap`), or **pending** at the end of the data (`m_pend`). The second part says that the taint still on the ledger equals what was seeded, minus what was deposited, plus what was delivered.

**Example.** A run deposits `m_dep = 1,000` units of tainted value: 800 delivered, 150 not followed, 6 remainder, 44 capped, 0 pending. 800 + 150 + 6 + 44 + 0 = 1,000.

**Code.** The `acc` dictionary and the final `assert` lines of `seeded_replay` in `bbe/replay.py`. The assertions run on every replay, so a run that breaks the identity stops with an error instead of producing numbers. The shares are written to `E4_conservation.csv` and `R1_conservation.csv`.

---

## 4. Theorem 1 in plain words

> **(a)** `f <= D / δ`, whoever moves the tainted value.
> **(b)** If every transfer that moves the attacker's taint is made and paid for by the attacker, and the budget `B` covers both the injected value `D` and the fees (`D + n·c <= B` for `n` transfers), then `f <= B / (δ + c)`, whatever the victims' balances and however the attacker splits, routes or times its transfers.

**Why it holds.**

1. *Value.* Conserving propagation never creates taint, so the taint in the whole system never exceeds `D`. Every flagged account holds at least `δ` of it. So `f·δ <= D`. That is (a).
2. *Transfers.* An account can only receive taint through a transfer, and each transfer has one recipient. To put taint on `f` flagged accounts the attacker needs at least `f` transfers (`n >= f`). Routing through middlemen only adds transfers and fees.
3. *Budget.* `f·(δ + c) <= D + n·c <= B`, so `f <= B/(δ + c)`.

Nothing in this argument depends on the victims' balances, on how many victims exist, or on timing. It does **not** hold for the poison rule, which creates taint.

**Example.** `B = 1,000`, `δ = 100`, `c = 0.05`: the bound is 1,000 / 100.05 = 9.995, so at most **9** accounts. The experiments found exactly 9 (Table 3). With `B = 10,000` the bound is 99.95, so at most 99; found 99.

**When the bound is reached (equality).** Only if the attacker finds `floor(B/(δ+c))` victims that each cost exactly `δ + c`: victims with no earlier taint and balance `V <= δ(q−p)/p` (900 dollars here), paid directly with one transfer. The Wormhole data has many such low-balance accounts, which is why the bound is tight there. If victims hold more, the share condition binds and the count falls below the bound (Section 4.9, "Opening balance"; R3).

**Where it is tested.** `tests/test_theorem.py` (random strategies with fees, equality conditions, heterogeneous fees); S1 checks the bound in 84 configurations; R3 checks it with chain-dependent fees; E2 reports the bound next to every BBE count.

---

## 5. The algorithms, one by one

Each algorithm is in the paper as pseudocode (Section 3.6; Word versions in `algorithms_word.docx`). Here is what each one does and where the code is.

### Algorithm 1: policy engine

**Purpose.** Keep each account's balance and taint, move taint when money moves, and decide whether an account is flagged.

**State.** Two maps `bal` and `T` (default 0). For FIFO, a queue of lots `(amount, tainted)` per account.

**FUND(a, x, tainted).** Money enters account `a` from outside (for example from the dataset). Add `x` to the balance; if it is tainted, add it to `T`; for FIFO, append a lot. *Code:* `Ledger.fund`.

**TRANSFER(s, r, x).** Move `x` units from sender `s` to receiver `r` and return the taint moved.
1. Nothing to do if `x <= 0` or `s = r`.
2. If the sender's tracked balance is below `x`, top it up with *clean* money. The real data do not show opening balances, and treating the missing part as clean can only make an account look *less* tainted, so it can never create a false flag. *Code:* `Ledger._topup`.
3. Haircut: moved = `floor(x·T_s / bal_s)` (Equation 1).
4. Poison: the whole transfer is tainted if the sender has any taint.
5. FIFO: take `x` units from the oldest lots; the tainted lots taken are the taint moved; append them to the receiver's queue with their status.
6. Update both balances.
7 and 8. Update `T`: for poison, the receiver's `T` becomes its whole balance; otherwise the sender loses and the receiver gains the moved taint.
9. Return the moved taint.
*Code:* `Ledger.transfer`.

**LOCK(s, x).** A bridge deposit: the debit half of TRANSFER. The sender is debited, **no account is credited** (the value leaves this chain), and the tainted amount that left is returned so that it can be accounted for. *Code:* `Ledger.lock` calls `transfer(s, None, x)`.

**FLAG(a).** Equation (2) and its two baselines, in integers. *Code:* `Ledger.flagged`.

**Cost.** Constant work per transfer for poison and haircut, amortised constant for FIFO. Memory grows with the number of accounts (and lots), not with the number of transfers.

### Algorithm 2: conserving bridge linker

**Purpose.** For a bridge deposit, find the candidate withdrawals and the share of taint each should receive.

**CANDIDATES(i).** Equation (6). *Code:* `linking.candidates`.
**WEIGHTS(i, m).** Compute `C` and `k`. If `k >= 1` and `1/k >= π`, return `floor(m/k)` for each candidate; otherwise return nothing (no link is followed). *Code:* inside `replay.seeded_replay`.

The full set of withdrawals is always used. Matching against a thinned sample would understate the ambiguity.

### Algorithm 3: greedy attacker

**Purpose.** Compute the largest number of victims an attacker with budget `B` can flag.

1. For each victim compute `cost = d_R(V) + c` (Equations 3 and 4).
2. Sort the costs in ascending order.
3. Buy flags from the cheapest until the budget runs out.

**Why it is optimal.** Every victim costs a fixed amount, independent of which others are chosen, so buying in ascending order maximises the count that fits. *Code:* `attack.greedy_leverage` is the readable reference; the experiments use the equivalent "sort once, cumulative sum, find where the sum passes the budget" (`lev()` with `np.searchsorted`), and `tests/test_attack.py` checks that the two agree.

### Algorithm 4: replay of the bridged ledger

**Purpose.** Replay all 250,527 real transfers in time order through Algorithm 1, in one of two modes.

**Events.** Each transfer creates two events: the deposit at time `t_i` and the withdrawal at time `t'_i`. They are sorted by time; at equal times deposits come first.

**Injection mode (E3, E5, S3, S6).** The real flows carry no taint. At the first receipt of each sampled victim, the attacker injects the cheapest dust of Equation (3) (`FUND` the attacker account with tainted money, then `TRANSFER` it to the victim), and the engine's flag decision is compared with the closed form. They must agree for every victim: this is the *mismatch* count in `E3_replay.csv` (it is 0). *Code:* the E3 loop in `scripts/05_run_experiments.py` and the loops in `scripts/08_sensitivity.py`.

**Seeded mode (E4, S4, R1).** A set `S` of assumed illicit senders. When a seed sends a deposit, its money is funded as tainted; `LOCK` removes the tainted amount from the source ledger; then the taint waits in a pending map until the matching withdrawal is processed. With the *true link* the whole amount goes to the true withdrawal. With the *linker*, `WEIGHTS` spreads it over the candidates. At a withdrawal, at most the amount that the withdrawal pays out can be delivered (`τ = min(pending, y)`); the excess is *capped*. Each tainted arrival `(τ, T[a])` is recorded for Equation (5). At the end Equation (7) is asserted. *Code:* `replay.seeded_replay`.

---

## 6. The scripts, one by one

Run them in this order. "Reads" and "Writes" are relative to the repository root.

| # | Script | What it does | Reads | Writes | Paper |
|---|---|---|---|---|---|
| 00 | `00_setup_env.sh` | Creates the virtual environment, installs packages, records versions | `requirements.txt` | `.venv/`, `outputs/env_report.txt` | reproducibility |
| 04 | `04_run_verification.sh` | Runs the 17 synthetic tests | `tests/` | `outputs/verification_tests.txt` | Section 3.8 ("All 17 tests pass") |
| 01 | `01_download_data.sh` | Downloads the Zenodo files and the OFAC list; checks md5 sums | the internet | `data/raw/*`, `outputs/download_integrity.txt` | Section 3.9 ("all files matched") |
| 02 | `02_verify_and_inspect.py` | Prints schema, row counts, null rates | `data/raw/*.parquet` | `outputs/schema_report.txt` | Section 3.9 (fields and files) |
| 03 | `03_build_ledger.py` | Maps the raw file to the standard integer ledger; filters invalid rows; reports what the filters removed | `data/raw`, `config.yaml` | `data/processed/ledger.parquet`, `outputs/ledger_build_report.txt`, `filter_*.csv` | Sections 3.9 and 4.1, Table S1 |
| 05 | `05_run_experiments.py` | Experiments E1 to E6 | `ledger.parquet`, OFAC list | `E1_*` to `E6_*`, `E4_conservation.csv`, `summary.json` | Sections 3.9, 4.1 to 4.8 |
| 08 | `08_sensitivity.py` | Sensitivity analyses S1 to S6 and Figure 12 | `ledger.parquet` | `S1_*` to `S6_*`, `sensitivity_summary.json`, `fig_sens_cost.png` | Section 4.9, Tables 9 and 10 |
| 09 | `09_robustness.py` | Robustness analyses R1 to R3 | `ledger.parquet` | `R1_*`, `R2_*`, `R3_*` | Section 4.9 (R1 to R3 paragraphs) |
| 11 | `11_pairing_check.py` | Checks the transaction-hash pairing; writes all chain pairs | raw parquet, ledger | `pairing_check.csv`, `E6_chain_pairs_all.csv`, `E6_chain_pairs_top_by_value.csv` | Section 3.9 (pairing), Table 7 |
| 06 | `06_make_figures.py` | Draws Figures 6 to 9 from E1, E2, E4 | `E1_*`, `E2_leverage.csv`, `E4_recall.csv` | `fig_ambiguity.png`, `fig_pi.png`, `fig_leverage.png`, `fig_recall.png` | Figures 6 to 9 |
| 10 | `10_make_new_figures.py` | Draws Figures 13 and 14 | `E4_conservation.csv`, `R1_interaction_grid.csv` | `fig_taint_accounting.png`, `fig_interaction_grid.png` | Figures 13 and 14 |
| 07 | `07_collect_outputs.sh` | Packs `outputs/` into `bbe_outputs.tar.gz` | `outputs/` | `bbe_outputs.tar.gz` | |

### What each experiment does in detail

**E1: link ambiguity (Section 4.2).** Draws 10,000 random deposits. For every combination of window (10 minutes to 2 hours) and fee tolerance (0.5% to 5%) it finds the candidate withdrawals in the *full* pool and records the mean `k`, the share with exactly one candidate, and the share whose true withdrawal is among the candidates. A second pass fixes the window at one hour and 2% and sweeps the confidence threshold `π` to show how many true links remain followed.

**E2: attacker leverage (Section 4.3).** Uses the balance of every non-hub destination account (a destination with more than 100 receipts is a hub or relayer, not a dusting target). For each budget and rule it applies Algorithm 3 with Equations (3) and (4), and reports the bound `B/(δ+c)` next to every BBE count. A bootstrap of 2,000 resamples of the victim population gives 95% intervals.

**E3: counterfactual replay (Section 4.4).** Algorithm 4 in injection mode for 5,000 random non-hub victims, for all nine combinations of propagation rule (poison, haircut, FIFO) and flag rule (poison, share, BBE). It records the cost of the dust, whether the engine and the closed form agree, whether taint was conserved, and how many victims are still flagged at the end of the data.

**E4: cost of protection (Section 4.5).** No sanctioned address appears in the ledger, so 200 senders with 1,000 to 1,000,000 dollars of bridged volume are *assumed* illicit. Algorithm 4 in seeded mode carries their taint across the bridge by the true link and by the conserving linker at `π = 0` and `π = 0.5`. For every floor it computes Equation (5) and its full-rule version.

**E5: case study (Section 4.8).** The non-hub account nearest the median balance among those with at least three receipts, followed through the four receipts under poison, share rule and BBE.

**E6: by chain (Section 4.6).** The leverage and ambiguity analysis repeated for each destination chain, plus the busiest chain pairs.

**S1 to S6 (Section 4.9).** One design choice at a time: transfer cost, hub threshold, random seed and sample size, E4 seed draw and volume range, assumed opening balance, share threshold.

**R1 to R3 (Section 4.9).** R1: visibility on the grid floor x share threshold x linker x window. R2: bootstrap by clusters of victims funded by one sender. R3: transfer cost that depends on the victim's chain, with Theorem 1 checked at the minimum fee.

---

## 7. Where each output appears in the paper

| Output file | What is in it | Where in the paper |
|---|---|---|
| `summary.json` | Counts, medians, hubs, OFAC overlap | Section 4.1 (dataset), Section 4.7 |
| `filter_steps_wormhole.csv` | Records left after each filter | Section 3.9, **Table S1** |
| `filter_retained_vs_excluded_wormhole.csv` | Value, date and chain coverage of kept and dropped records | Section 3.9, **Table S1** |
| `filter_retention_by_dst_chain_wormhole.csv` | Share of each destination chain retained | Section 3.9 (Celo 81%, Moonbeam 76%, Aptos 67%, Solana 31%) |
| `pairing_check.csv` | Transaction-hash pairing statistics | Section 3.9 (99.8% of hashes occur once; 250,269 distinct pairs) |
| `E1_linking.csv` | Mean `k`, share unique, recall, precision per window and tolerance | **Table 2**, **Figure 6**, Section 4.2 |
| `E1_pi_sweep.csv` | Link recall against `π` | **Figure 7**, Section 4.2 |
| `E1_k_hist.csv` | Histogram of `k` (capped at 20) | Section 4.2 ("4.6% have twenty or more") |
| `E2_leverage.csv` | Accounts flagged by rule, budget and floor, with the bound | **Table 3**, **Figure 8**, Sections 4.3 and 4.7, Abstract |
| `E2b_bootstrap.csv` | 95% intervals | **Table 3** (intervals) |
| `E3_replay.csv` | Nine-row replay grid | **Table 4**, Section 4.4 |
| `E4_recall.csv` | `visibility_floor`, `visibility_full_rule`, arrivals, value | **Table 5**, **Figure 9**, Section 4.5 |
| `E4_conservation.csv` | Where locked taint goes (delivered, not followed, capped, remainder) | **Figure 13**, Equation (7) |
| `E5_case_trace.csv` | Case-study trace | Section 4.8, **Figure 11** |
| `E6_by_dst_chain.csv` | Per-chain leverage and ambiguity | **Table 6**, **Figure 10**, Section 4.6 |
| `E6_chain_pairs.csv`, `E6_chain_pairs_all.csv`, `E6_chain_pairs_top_by_value.csv` | Chain pairs | **Table 7** (and the Sui to Ethereum note in its caption) |
| `S1_cost_sweep.csv` | Leverage against `c`, with the bound | **Table 9** (cost rows), **Figure 12**, "84 configurations" |
| `S2_hub_threshold.csv` | Leverage for four hub thresholds | **Table 9** (hub rows), paragraph "Hub threshold" |
| `S3_replay_stability.csv` | 14 replays: five seeds and three sample sizes | Paragraph "Seed and sample size" |
| `S4_e4_stability.csv` | Visibility for 15 seed draws | **Table 10**, Section 4.9, Discussion |
| `S5_opening_balance.csv` | Leverage with assumed opening balances | **Table 9** (opening balance), paragraph "Opening balance" |
| `S6_theta.csv` | Leverage and replay for four thresholds | Paragraph "Share threshold" |
| `sensitivity_summary.json` | Bound check and mismatch counts | Section 4.9 |
| `R1_interaction_grid.csv` | Visibility grid | Paragraph R1, **Figure 14** |
| `R1_conservation.csv` | Accounting identity for seven replays | Paragraph R1 ("held in all seven replays") |
| `R2_clustered_bootstrap.csv` | Cluster-bootstrap intervals | Paragraph R2 |
| `R3_heterogeneous_cost.csv` | Bound with the minimum fee | Paragraph R3 |
| `verification_tests.txt` | Test log | Section 3.8 |
| `download_integrity.txt` | md5 results | Section 3.9 |
| `schema_report.txt` | Raw schema | Section 3.9 |

---

## 8. Where each paper figure comes from

| Figure | Content | How it is made |
|---|---|---|
| 3 Flag rules compared | Which victims each rule flags; attacker cost | Closed-form formulas (Equations 2 to 4) at θ = 10%, δ = 100, `c` = 0.05, plus the median balance 29.50 USD typed in |
| 6, 7 | Ambiguity against window; recall against `π` | `E1_linking.csv`, `E1_pi_sweep.csv` |
| 8 | Accounts flagged against the floor | `E2_leverage.csv` |
| 9 | Visibility at arrival against the floor | `E4_recall.csv` |
| 10 | Per-chain leverage and ambiguity | `E6_by_dst_chain.csv` |
| 11 | The case-study account | The four real receipts (typed into the script, equal to `E5_case_trace.csv`) and the formulas |
| 12 | Leverage against `c` | `S1_cost_sweep.csv` |
| 13 | Fate of locked taint | `E4_conservation.csv` |
| 14 | Visibility grid | `R1_interaction_grid.csv` |

---

## 9. What each test proves

| Test | Claim in the paper it supports |
|---|---|
| `test_policies.py::test_conservation_haircut_fifo` | Haircut and FIFO conserve taint (Section 3.2) |
| `test_policies.py::test_poison_creates_taint` | Poison does not conserve (Section 3.2) |
| `test_policies.py::test_min_dust_matches_replay` | Equation (3): the minimal dust flags and one unit less does not |
| `test_policies.py::test_bbe_bound` | The flagged count never exceeds Theorem 1 |
| `test_reference.py` | The engine agrees with two *independent* models (Section 3.8, "Independent checks") |
| `test_theorem.py` | Theorem 1 under random strategies, equality conditions, minimum fee |
| `test_attack.py` | Algorithm 3: the fast and the readable versions agree |
| `test_linking.py` | Candidate sets on a hand-built example |
| `test_bridge_accounting.py` | Equation (7); overlapping candidate sets; deterministic linker |

All tests use small synthetic cases with known answers. They are never combined with the real-data pipeline.

---

## 10. How to check one number from the paper

**Example: the 9 accounts at a budget of 1,000 dollars (Table 3).**

1. Run steps 5 and 6 (`03_build_ledger.py`, `05_run_experiments.py`).
2. Open `outputs/E2_leverage.csv` and filter `pop = nonhub`, `budget_usd = 1000`, `rule = bbe`, `delta_usd = 100`. The `flagged` column is `9`, and the `bound` column is `9.995`.
3. Check by hand: each victim below 900 dollars costs 100 + 0.05 = 100.05 dollars, and 9 x 100.05 = 900.45 <= 1,000 < 10 x 100.05 = 1,000.50.
4. Check the replay: in `E3_replay.csv` the row `fifo, bbe` has `closed_form_mismatch = 0`, so the engine and the formula agree for all 5,000 sampled victims.

**Example: the share of tainted value above a 100-dollar floor (Table 5).** Open `E4_recall.csv`, filter `variant = oracle`, `delta_usd = 100`; `visibility_floor` is 0.999756, which the paper reports as 99.98%.
