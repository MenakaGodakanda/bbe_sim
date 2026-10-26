# Budget-Bounded Exposure (BBE): simulation

Code, configuration and result files for the paper **"Budget-Bounded Exposure (BBE): Protecting Innocent Users from Dusting in Cross-Chain Anti-Money Laundering (AML)"** (MDPI *Information*, Special Issue "Blockchain Security and Smart Contract").

BBE is a taint-flagging policy for cross-chain anti-money-laundering (AML) screening. An account is flagged only if its tainted exposure `T` satisfies `T >= delta` and `T >= theta * B`, where `B` is the account's balance. Under a conserving taint policy, an attacker who sends dust to victims gains at most `B_attack / (delta + c)` flagged accounts, regardless of the victims' balances (Theorem 1 in the paper). This repository reproduces every number, table and figure in the paper's Results section.

---

## 1. What is real and what is synthetic

| Item | Source | Used for |
|---|---|---|
| Cross-chain transfers | Real: Zenodo record 15354599, Wormhole file (`wormhole_data.parquet`) | All reported results (E1-E6) |
| OFAC sanctioned addresses | Real: US Treasury SDN list via the 0xB10C mirror | E4 overlap check (no overlap with the ledger was found) |
| E4 "seed" addresses | Hypothetical addresses chosen at random from real flows | E4 only. Labelled hypothetical in the paper |
| Dust injection | In-memory counterfactual in the E3 replay | E3 only. Nothing is written to any dataset |
| Synthetic fixtures | `tests/` only | Code-correctness tests only. Never written to `data/`, never used for results |

---

## 2. Requirements

- Ubuntu 22.04 or later (tested on Ubuntu; other Linux distributions should work)
- Python 3.10 or later, `pip`, `venv`, `wget`, `curl`, `md5sum`
- About 5 GB of free disk space (the raw Wormhole file dominates) and 8 GB of RAM or more
- Internet access for step 3 only. After the download, everything runs offline
- Runtime: setup and tests take a few minutes; the download depends on your connection; the experiment step (step 7) is the longest and takes longer on a small VM

Python packages (pinned minimums in `requirements.txt`): numpy, pandas, pyarrow, pyyaml, matplotlib, pytest, requests.

---

## 3. Repository layout

```
bbe_sim/
├── README.md                 this file
├── requirements.txt          Python dependencies
├── config.yaml               every parameter and the column mapping
├── bbe/                      library code
│   ├── units.py              exact integer micro-USD arithmetic
│   ├── engine.py             Ledger class: poison, haircut and FIFO taint policies, BBE flag rule
│   ├── attack.py             minimal-dust computation and greedy attacker leverage
│   ├── linking.py            bridge deposit-to-withdrawal link inference and ambiguity statistics
│   ├── adapters.py           maps the raw parquet schema to the standard ledger
│   └── stats.py              bootstrap confidence intervals
├── scripts/                  numbered scripts, run in order
├── tests/                    synthetic unit tests (verification only)
├── data/raw/                 downloaded real data
├── data/processed/           ledger.parquet
└── outputs/                  all result files (CSV, JSON, TXT, PNG)
```

---

## 4. Quick start (all commands)

```bash
git clone https://github.com/MenakaGodakanda/bbe_sim.git
cd bbe_sim
bash scripts/00_setup_env.sh
source .venv/bin/activate
bash scripts/04_run_verification.sh
bash scripts/01_download_data.sh
python3 scripts/02_verify_and_inspect.py
python3 scripts/03_build_ledger.py
python3 scripts/05_run_experiments.py
python3 scripts/06_make_figures.py
python3 scripts/08_sensitivity.py
bash scripts/07_collect_outputs.sh
```

The fixed random seed (`seed: 20261030` in `config.yaml`) and the integer arithmetic make a re-run produce identical CSV files.

---
## 5. Step-by-step guide

Each step lists what it does, the command, and what you should see.

### Step 1. Set up the environment

```bash
bash scripts/00_setup_env.sh
source .venv/bin/activate
```

**What it does.** Installs system packages (Python, venv, pip, curl, wget), creates a virtual environment in `.venv/`, installs `requirements.txt`, and records the Python version and installed package versions.

**Expected output.** A final line `Setup complete. Activate with: source .venv/bin/activate`. The file `outputs/env_report.txt` contains the Python version and the output of `pip freeze`.

```
(.venv) menaka@ubuntu-test:~/bbe_sim$ bash scripts/04_run_verification.sh 
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.1.1, pluggy-1.7.0 -- /home/menaka/bbe_sim/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /home/menaka/bbe_sim
collecting ... collected 17 items

tests/test_attack.py::test_vectorised_equals_greedy PASSED               [  5%]
tests/test_attack.py::test_zero_balance_costs_one_unit_under_share PASSED [ 11%]
tests/test_bridge_accounting.py::test_accounting_identity_and_no_duplication PASSED [ 17%]
tests/test_bridge_accounting.py::test_overlap_cap_is_reported_not_silently_lost PASSED [ 23%]
tests/test_bridge_accounting.py::test_linker_is_deterministic_under_input_order PASSED [ 29%]
tests/test_linking.py::test_unique_and_ambiguous PASSED                  [ 35%]
tests/test_policies.py::test_conservation_haircut_fifo PASSED            [ 41%]
tests/test_policies.py::test_poison_creates_taint PASSED                 [ 47%]
tests/test_policies.py::test_min_dust_matches_replay PASSED              [ 52%]
tests/test_policies.py::test_bbe_bound PASSED                            [ 58%]
tests/test_reference.py::test_fifo_matches_unit_level_reference PASSED   [ 64%]
tests/test_reference.py::test_haircut_matches_exact_rational_reference PASSED [ 70%]
tests/test_reference.py::test_lock_removes_value_without_crediting PASSED [ 76%]
tests/test_theorem.py::test_bound_with_fees_random_strategies PASSED     [ 82%]
tests/test_theorem.py::test_tainted_value_only_bound_when_fees_paid_separately PASSED [ 88%]
tests/test_theorem.py::test_equality_conditions PASSED                   [ 94%]
tests/test_theorem.py::test_heterogeneous_fees_use_minimum_fee PASSED    [100%]

============================== 17 passed in 0.50s ==============================
```

### Step 2. Run the verification tests

```bash
bash scripts/04_run_verification.sh
```

**What it does.** Runs `pytest` on `tests/test_policies.py` and `tests/test_linking.py`. The tests use small synthetic examples to check that the code is correct: that poison, haircut and FIFO conserve or do not conserve taint as defined, that the BBE flag rule fires exactly at the thresholds, that the minimal-dust formula is right, and that the linker finds known links. These tests do not touch the real data and do not produce any result in the paper.

**Expected output.** `5 passed` (or more, if you add tests) and no failures. The log is saved to `outputs/verification_tests.txt`. **Do not continue if any test fails.**

### Step 3. Download the real data

```bash
bash scripts/01_download_data.sh
```

**What it does.** Downloads the Zenodo record 15354599 files (`allBridge`, `connext`, `orbitChain`, `wormhole`, `block` parquet files and the dataset readme) into `data/raw/`, and checks each file against the md5 sum published by Zenodo. It also downloads the OFAC sanctioned-address list (ETH) from the 0xB10C mirror. Only the Wormhole file is used in the experiments; the other files are downloaded so the integrity check covers the whole record. Files that already exist are not downloaded again.

**Expected output.** One line per file, each starting with `OK`:

```
(.venv) menaka@ubuntu-test:~/bbe_sim$ bash scripts/01_download_data.sh
data/raw/wormhole_dat 100%[=======================>] 146.96M   717KB/s    in 4m 17s  
OK   wormhole_data.parquet
data/raw/readme.md    100%[=======================>]   1.05K  --.-KB/s    in 0.06s   
OK   readme.md
data/raw/block_data.p 100%[=======================>]  13.43M   327KB/s    in 48s     
OK   block_data.parquet
data/raw/allBridge_da 100%[=======================>]  40.81M  1.21MB/s    in 87s     
OK   allBridge_data.parquet
data/raw/orbitChain_d 100%[=======================>]  77.41M  1.07MB/s    in 82s     
OK   orbitChain_data.parquet
data/raw/connext_data 100%[=======================>]  95.84M  1.08MB/s    in 4m 59s  
OK   connext_data.parquet
120 data/raw/sanctioned_addresses_ETH.txt
Done. If any file says FAIL, re-run or re-download that file.
```

followed by the line count of the sanctioned-address list. The same text is saved to `outputs/download_integrity.txt`. A `FAIL` line means the file is corrupted or incomplete: delete it from `data/raw/` and run the step again. If the OFAC download fails, the script prints a notice; this list is optional (E4 falls back to hypothetical seeds).

### Step 4. Inspect the real data schema

```bash
python3 scripts/02_verify_and_inspect.py
```

**What it does.** For every parquet file, prints the row count, the column names and types, five sample rows, and the null rate of each column.

**Expected output.** A report in the terminal and in `outputs/schema_report.txt`. Use it to confirm that the columns named in the `columns:` section of `config.yaml` exist (`fromAddress`, `toAddress`, `fromTokenAddress`, `srcUSD`, `dstUSD`, `createTime`, `completeTime`, `fromChainRaw`, `toChainRaw`, `_id`). If the dataset version changes, edit the mapping in `config.yaml`; do not edit the code.

```
(.venv) menaka@ubuntu-test:~/bbe_sim$ python3 scripts/02_verify_and_inspect.py
================================================================================
allBridge_data.parquet rows: 146210
_id: string
bridge: int64
fromChainRaw: string
toChainRaw: string
fromChain: string
toChain: string
srcAmount: double
dstAmount: double
srcTxhash: string
dstTxhash: string
fromTokenAddress: string
toTokenAddress: string
fromAddress: string
toAddress: string
srcUSD: double
dstUSD: double
createTime: timestamp[ns]
completeTime: timestamp[ns]
profit: double
isProfit: int64
profitRatio: double
__index_level_0__: int64
-- schema metadata --
pandas: '{"index_columns": ["__index_level_0__"], "column_indexes": [{"na' + 2831
                                                                                   0                                                                   1                                                                                         2                                                                                         3                                                                                        4
_id                                                         65cbd840b080ec1e9227fe09                                            65cbd840b080ec1e9227fe0a                                                                  65cbd840b080ec1e9227fe0b                                                                  65cbd840b080ec1e9227fe0c                                                                 65cbd840b080ec1e9227fe0d
bridge                                                                             0                                                                   0                                                                                         0                                                                                         0                                                                                        0
fromChainRaw                                                                     POL                                                                 ARB                                                                                       SOL                                                                                       ETH                                                                                      SOL
toChainRaw                                                                       BSC                                                                 POL                                                                                       POL                                                                                       SOL                                                                                      ETH
fromChain                                                                        pol                                                                 arb                                                                                       NaN                                                                                       eth                                                                                      NaN
toChain                                                                          bsc                                                                 pol                                                                                       pol                                                                                       NaN                                                                                      eth
srcAmount                                                                 109.426936                                                                31.4                                                                                255.583375                                                                                      10.0                                                                              5000.000666
dstAmount                                                                 108.730659                                                           31.328936                                                                                252.603526                                                                                  9.951051                                                                              4948.131653
srcTxhash         0xa674f8edf808651e78e5335a7baa5a6f636ffdf38ac6cfe719379f927085b01c  0x2ce40d18fab3b029d7d34f8da2343ed60c81976c5c87a28ca50f8599a32d68fb  2fzb4XigJZ9M24zxrBhE8jVtA9CLuqcSweHAzMGrHyMYbdgUhELZnodenqvQvxN1jqq9SEbb7HPLaY5S1vHoVcWC                        0x93ce4205a6f222b393a5ccb87ad5a10133c532beb3cd9726c310176f4577b928  ZxhgZYNSvyo1RP9DWYwpNbDdintb8ca5rVnR1Jb2wAZKrVScRuvuZnMTwipiapgGmdW9EiLEjcx6n2Vkq8TpGma
dstTxhash         0xe6d0d4c118e4a46b2b79134a81fd084a12f92a741c78d9fa8bd50781a042d70e  0x9fc0898a94356b9f0c12171fce347b93a19f6454109a677aac74985cec4d17a8                        0x9180e120017042f58ea0fb7dad256b0a6406266c7e306f1f886646e10a906e5c  3xTvYQtK5zbWBPc1gFbvTVFRs36esDFgPqG6VCnpHnwH6JgyeiqAdTmh4bs4zFfLvRA5v4nbUDifoLQ8kdbTea28                       0xbdc48ad269b334563fda1894ca24f591495a5d1a8c80091ab7e82cf27318cb68
fromTokenAddress                          0x3c499c542cef5e3811e1192ce70d8cc03d5c3359                          0xaf88d065e77c8cc2239327c5edb3a432268e5831                                              EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v                                                0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48                                             EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
toTokenAddress                            0x55d398326f99059ff775485246999027b3197955                          0x3c499c542cef5e3811e1192ce70d8cc03d5c3359                                                0x3c499c542cef5e3811e1192ce70d8cc03d5c3359                                              EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v                                               0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
fromAddress                               0x3296cd3b8e8cf56beb06cef32277a34332f2d99f                          0x32ead9e698b7b56d9ecede8b01ce9f372d7cc699                                              hah8wzc2boccihdzjavkcg7r2hsgw5ccztyabhad385q                                                0xb8cfbee2169e232223d8443d79829a2ac526f333                                             dvnddjnaqlygoyhcxf2nmnegfcc7clqbuvsrmhvhjrbq
toAddress                                 0x3fbd53973b39ac983a47404911e93c1dcd6551fb                          0x32ead9e698b7b56d9ecede8b01ce9f372d7cc699                                                0x63c73c74ee20efbb792f061c9703a2b264915951                                              6ttjncdsll1hmzv5xqdkzgpmtlosvrdgk34uefudb9q4                                               0xc2bb8abe8b47a5d3fb74f377ec36bc7b61b87e26
srcUSD                                                                    109.426936                                                                31.4                                                                                255.583375                                                                                      10.0                                                                              5000.000666
dstUSD                                                                    108.730659                                                           31.328936                                                                                252.603526                                                                                  9.951051                                                                              4948.131653
createTime                                                       2023-12-11 14:57:24                                                 2023-12-05 14:11:51                                                                       2023-12-13 12:03:31                                                                       2023-12-24 16:14:47                                                                      2023-12-30 21:20:34
completeTime                                                                     NaT                                                                 NaT                                                                                       NaT                                                                                       NaT                                                                                      NaT
profit                                                                     -0.696277                                                           -0.071064                                                                                 -2.979849                                                                                 -0.048949                                                                               -51.869013
isProfit                                                                           0                                                                   0                                                                                         0                                                                                         0                                                                                        0
profitRatio                                                                 0.993637                                                            0.997737                                                                                  0.988341                                                                                  0.995105                                                                                 0.989626
null rate (first 200 rows):
_id                 0.000
bridge              0.000
fromChainRaw        0.000
toChainRaw          0.000
fromChain           0.330
toChain             0.455
srcAmount           0.000
dstAmount           0.000
srcTxhash           0.000
dstTxhash           0.000
fromTokenAddress    0.000
toTokenAddress      0.000
fromAddress         0.000
toAddress           0.000
srcUSD              0.000
dstUSD              0.000
createTime          0.000
completeTime        1.000
profit              0.000
isProfit            0.000
profitRatio         0.000
================================================================================
block_data.parquet rows: 1345382
_id: int64
timestamp: string
chain: string
-- schema metadata --
pandas: '{"index_columns": [{"kind": "range", "name": null, "start": 0, "' + 596
                    0           1           2           3           4
_id          39845890    42991618    39845891    39845892    39845894
timestamp  1677683326  1684709704  1677683328  1677683330  1677683334
chain             pol         pol         pol         pol         pol
null rate (first 200 rows):
_id          0.0
timestamp    0.0
chain        0.0
================================================================================
connext_data.parquet rows: 464542
_id: string
bridge: int64
fromChainRaw: string
toChainRaw: string
fromChain: string
toChain: string
srcAmount: double
dstAmount: double
srcTxhash: string
dstTxhash: string
fromTokenAddress: string
toTokenAddress: string
fromAddress: string
toAddress: string
srcUSD: double
dstUSD: double
createTime: timestamp[ns]
completeTime: timestamp[ns]
profit: double
isProfit: int64
profitRatio: double
__index_level_0__: int64
-- schema metadata --
pandas: '{"index_columns": ["__index_level_0__"], "column_indexes": [{"na' + 2831
                                                                                   0                                                                   1                                                                   2                                                                   3                                                                   4
_id                                                         65ea5d7059d1b4f5eb684a53                                            65ea5d7059d1b4f5eb684a54                                            65ea5d7059d1b4f5eb684a55                                            65ea5d7059d1b4f5eb684a56                                            65ea5d7059d1b4f5eb684a57
bridge                                                                             1                                                                   1                                                                   1                                                                   1                                                                   1
fromChainRaw                                                                      10                                                               42161                                                               42161                                                                 100                                                                  56
toChainRaw                                                                     42161                                                                  56                                                                 137                                                                  56                                                               42161
fromChain                                                                         op                                                                 arb                                                                 arb                                                              gnosis                                                                 bsc
toChain                                                                          arb                                                                 bsc                                                                 pol                                                                 bsc                                                                 arb
srcAmount                                                                     4796.0                                                          39807741.0                                                               767.0                                                          20385518.0                                                             16587.0
dstAmount                                                                     4801.0                                                          39870387.0                                                               766.0                                                          20351793.0                                                             16522.0
srcTxhash         0x18b8d9e8043b66b96cd12b93a59cfab137ff1dda8709c1e5420136499f9161d9  0xd7761b91d34a6058bacf7848d6a5e87e65259289a8ca8c72a61683b27cb65797  0xbda77e65a75833fd2a6d8669afa5918511e0b4196453c5522c13d30c0e8f7f76  0x81cf2155e51755d202ed2f52bf7d72515ac011b52373a2e0c253057730d15bcb  0x59ab48010c466b42105d3b942534002934110942eb757d95b7816910e3e846ac
dstTxhash         0xeb5c6fcc385eed3f197b49cd11d0eb7af7923ed5f5b6813edc7f793b048c2cc6  0x58de0463789ff57638c7fe7ed02230cd97a4d725c6810990ec49ed000d7f62b6  0x6b09bff4a3fe2ac301b280562a2e3b3fbd2b7fdf7779fbc63b99e8a30c1e4600  0xbf59b6867d6f8eb7f868ea005a2034b4c23bb3881a756fa8299e9ca12a420938  0x51f92428e49d590995b5925afc2ed6a6b9bc61d0583c5e005594997780d92b24
fromTokenAddress                          0xbad5b3c68f855eaece68203312fd88ad3d365e50                          0x2fd7e61033b3904c65aa9a9b83dcd344fa19ffd2                          0x2983bf5c334743aa6657ad70a55041d720d225db                          0x44cf74238d840a5febb0eaa089d05b763b73fab8                          0xa9cb51c666d2af451d87442be50747b31bb7d805
toTokenAddress                            0x2983bf5c334743aa6657ad70a55041d720d225db                          0xd609f26b5547d5e31562b29150769cb7c774b97a                          0x4b8bac8dd1caa52e32c07755c17efaded6a0bbd0                          0x5e7d83da751f4c9694b13af351b30ac108f32c38                          0x2983bf5c334743aa6657ad70a55041d720d225db
fromAddress                               0xb0eef3e1de973d045c3858e072c540299585252d                          0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae                          0x38b93e8c22497b06a40500666bfcb01469f26e43                          0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae                          0x3a23f943181408eac424116af7b7790c94cb97a5
toAddress                                 0x429b9eb01362b2799131efcc44319689b662999d                          0x050e198e36a73a1e32f15c3afc58c4506d82f657                          0x89f423567c2648bb828c3997f60c47b54f57fa6e                          0x3ccccdacab1537c0e5dacee72931937e742b232b                          0x429b9eb01362b2799131efcc44319689b662999d
srcUSD                                                                           NaN                                                                 NaN                                                                 NaN                                                                 NaN                                                                 NaN
dstUSD                                                                           NaN                                                                 NaN                                                                 NaN                                                                 NaN                                                                 NaN
createTime                                                       2023-12-23 13:04:49                                                 2023-12-21 06:58:20                                                 2023-12-30 20:55:12                                                 2023-12-23 03:31:25                                                 2023-12-15 10:33:39
completeTime                                                     2023-12-23 14:54:12                                                 2023-12-21 09:09:57                                                 2023-12-30 23:24:34                                                 2023-12-23 06:04:09                                                 2023-12-15 15:14:31
profit                                                                           5.0                                                             62646.0                                                                -1.0                                                            -33725.0                                                               -65.0
isProfit                                                                           1                                                                   1                                                                   0                                                                   0                                                                   0
profitRatio                                                                 1.001043                                                            1.001574                                                            0.998696                                                            0.998346                                                            0.996081
null rate (first 200 rows):
_id                 0.000
bridge              0.000
fromChainRaw        0.000
toChainRaw          0.000
fromChain           0.000
toChain             0.000
srcAmount           0.000
dstAmount           0.000
srcTxhash           0.000
dstTxhash           0.225
fromTokenAddress    0.000
toTokenAddress      0.000
fromAddress         0.000
toAddress           0.000
srcUSD              1.000
dstUSD              1.000
createTime          0.000
completeTime        0.000
profit              0.000
isProfit            0.000
profitRatio         0.000
================================================================================
orbitChain_data.parquet rows: 458055
_id: string
bridge: int64
fromChainRaw: string
toChainRaw: string
fromChain: string
toChain: string
srcAmount: double
dstAmount: double
srcTxhash: string
dstTxhash: string
fromTokenAddress: string
toTokenAddress: string
fromAddress: string
toAddress: string
srcUSD: double
dstUSD: double
createTime: timestamp[ns]
completeTime: timestamp[ns]
profit: double
isProfit: int64
profitRatio: double
-- schema metadata --
pandas: '{"index_columns": [{"kind": "range", "name": null, "start": 0, "' + 2766
                                                                                   0                                                                   1                                                                   2                                                                   3                                                                   4
_id                                                         65cbd94b133904639a4f2ec0                                            65cbd94b133904639a4f2ec1                                            65cbd94b133904639a4f2ec2                                            65cbd94b133904639a4f2ec3                                            65cbd94b133904639a4f2ec4
bridge                                                                             2                                                                   2                                                                   2                                                                   2                                                                   2
fromChainRaw                                                                  KLAYTN                                                              KLAYTN                                                              KLAYTN                                                              KLAYTN                                                              KLAYTN
toChainRaw                                                                     ORBIT                                                               ORBIT                                                               WEMIX                                                               WEMIX                                                               ORBIT
fromChain                                                                        NaN                                                                 NaN                                                                 NaN                                                                 NaN                                                                 NaN
toChain                                                                          NaN                                                                 NaN                                                               wemix                                                               wemix                                                                 NaN
srcAmount                                                                  4540000.0                                                 90000000000000000.0                                                 70829100000000000.0                                                        6993000000.0                                                   218635594828420.0
dstAmount                                                                  4540000.0                                                 90000000000000000.0                                                 70829100000000000.0                                                        6993000000.0                                                   218635594828420.0
srcTxhash         0x6c7c2ce843e2f6fc1c4b4db2f4a0bcaf5e06dea1c506151c68e1fe7708266b3f  0xf297e631d7bef009eafab6238b884b845c56f211ce234a8e0493c67d3ca15a85  0x0792036e39b5a37336da0ba019429ff3ca8465dfc41d220cf52e8be92d415d3c  0x0f6734416614e816754b219a64ae99732efb3e1ff7f22569e488871bead22a25  0x34d02de8058d92fbcc66dcc122735bb03d7647a3b71b8cc9405f0f2a6b256287
dstTxhash         0x39c4a7dd38d2a859068eb0ffa4108ee69fa15fc8cd2f3c6a8100a7d45ba590b8  0xb27d2a606d2edb6a2961050fc54716288acb9c0afabeeb78e73e6fa0133717b0  0x09985e2e59b7cb9c4cb01f4e6cb1b4baa273061bdde1bea40cf5c41eebdda4c1  0x4389623fcf6f65ededf244c1974cbc835a4d812a518fd494b1cfade3760425f2  0x2f68bf4ce7d25e3e8b0f3e14cc446d9330952e87479f2f95a61dfdc4df1d67c7
fromTokenAddress                          0x4b96dbf8f42c8c296573933a6616dcafb80ca461                          0x67cb285790bb9f5dce728f80a3104a2297df2bb2                          0x67cb285790bb9f5dce728f80a3104a2297df2bb2                          0x754288077d0ff82af7a5317c7cb8c444d421d103                          0x67cb285790bb9f5dce728f80a3104a2297df2bb2
toTokenAddress                            0x4b96dbf8f42c8c296573933a6616dcafb80ca461                          0xad60de287c03f50bc45b8f7737c79e8586a12494                          0x0000000000000000000000000000000000000000                          0xe4c2b5db9de5da0a17ed7ec7176602ad99e52624                          0xad60de287c03f50bc45b8f7737c79e8586a12494
fromAddress                               0x906b53fe1f4ab3320a48a3460a92c51f0c5fdda0                          0x461f2023e1c2837880ea37851cc5d212ce6222f5                          0xe88476b0601b043f0c9647972d729c87d2b3bf08                          0x911fc48da3f6e38d195c6bbfb4fda31bd9b313c5                          0x1db85d231479b9d0e428c3192e32f1426d70d999
toAddress                                 0xe9f3604b85c9672728eeecf689cf1f0cf7dd03f2                          0xe9f3604b85c9672728eeecf689cf1f0cf7dd03f2                          0xe88476b0601b043f0c9647972d729c87d2b3bf08                          0x911fc48da3f6e38d195c6bbfb4fda31bd9b313c5                          0xe9f3604b85c9672728eeecf689cf1f0cf7dd03f2
srcUSD                                                                           NaN                                                                 NaN                                                                 NaN                                                                 NaN                                                                 NaN
dstUSD                                                                           NaN                                                                 NaN                                                                 NaN                                                                 NaN                                                                 NaN
createTime                                                       2023-12-15 10:04:46                                                 2023-12-05 19:03:22                                                 2023-12-12 10:40:38                                                 2023-12-12 15:07:51                                                 2023-12-19 17:04:09
completeTime                                                     2023-12-15 10:06:00                                                 2023-12-05 19:04:30                                                 2023-12-12 10:41:51                                                 2023-12-12 15:09:30                                                 2023-12-20 05:40:10
profit                                                                           0.0                                                                 0.0                                                                 0.0                                                                 0.0                                                                 0.0
isProfit                                                                           0                                                                   0                                                                   0                                                                   0                                                                   0
profitRatio                                                                      1.0                                                                 1.0                                                                 1.0                                                                 1.0                                                                 1.0
null rate (first 200 rows):
_id                 0.000
bridge              0.000
fromChainRaw        0.000
toChainRaw          0.000
fromChain           0.650
toChain             0.665
srcAmount           0.000
dstAmount           0.000
srcTxhash           0.000
dstTxhash           0.000
fromTokenAddress    0.000
toTokenAddress      0.000
fromAddress         0.000
toAddress           0.000
srcUSD              1.000
dstUSD              1.000
createTime          0.000
completeTime        0.000
profit              0.000
isProfit            0.000
profitRatio         0.000
================================================================================
wormhole_data.parquet rows: 699474
_id: string
bridge: int64
fromChainRaw: int64
toChainRaw: double
fromChain: string
toChain: string
srcAmount: double
dstAmount: double
srcTxhash: string
dstTxhash: string
fromTokenAddress: string
toTokenAddress: string
fromAddress: string
toAddress: string
srcUSD: double
dstUSD: double
createTime: timestamp[ns, tz=UTC]
completeTime: timestamp[ns, tz=UTC]
profit: double
isProfit: int64
profitRatio: double
__index_level_0__: int64
-- schema metadata --
pandas: '{"index_columns": ["__index_level_0__"], "column_indexes": [{"na' + 2863
                                                                                     1                                                                   2                                                                                         3                                                                                           4                                                                                         5
_id                                                           65cbda8b6595a18bd8428ccd                                            65cbda8b6595a18bd8428cce                                                                  65cbda8b6595a18bd8428ccf                                                                    65cbda8b6595a18bd8428cd0                                                                  65cbda8b6595a18bd8428cd1
bridge                                                                               3                                                                   3                                                                                         3                                                                                           3                                                                                         3
fromChainRaw                                                                         5                                                                  23                                                                                         1                                                                                           2                                                                                         1
toChainRaw                                                                        22.0                                                                 1.0                                                                                      23.0                                                                                         1.0                                                                                      22.0
fromChain                                                                          pol                                                                 arb                                                                                       NaN                                                                                         eth                                                                                       NaN
toChain                                                                            NaN                                                                 NaN                                                                                       arb                                                                                         NaN                                                                                       NaN
srcAmount                                                                   31000000.0                                                          10000000.0                                                                               210000000.0                                                                                  10000000.0                                                                                10000000.0
dstAmount                                                                   31000000.0                                                          10000000.0                                                                               210000000.0                                                                                  10000000.0                                                                                10000000.0
srcTxhash           0x9b17b666897e1e1f81fd7de17bd517eb6e725c2469a320653eb55688e4960457  0x99bd595f9eca6c828dc4cee225a0df42689bb54d6008ccb674cb54770e0fd76e  225c5KrkC6QN9ncXFs3wgTErnSNVv9SWhrCT2JuypV1twsL9P5anKKWv52GXM83mvqajcqaQxTLmxMTqwqEqjUVy                          0x09256a01f09061bd9cc9298e29d293ceb1d61d256f374186e27efc9b71a9d2c6  2D3iNkjutZgypkWjWxhYeXf3CdjdfTLGgvfcwB8hkRwQ4zqK5meTcb8m1zD9z9HnmmyaLdejUVjTBKPhv5iw2Gri
dstTxhash         0x0x1173860374ae088170f5ddb0f881ca71a97de8bc17836a4b72c151f4017d80a7                                                                 NaN                                                                                       NaN  0x4eNbP6Kx1zNawjxfTELtxcwxNKGL1o5r99j5jrordYLGK4wbJTdLKZLYHwVo3o8SNgyD1uFk5xFt232kGkDxtQ3i                      0x0x3905c003d22ce86caee29c63ae2a65903ae67564b43e32cfb87d560ff82cbb82
fromTokenAddress                            0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270                          0x82af49447d8a07e3bd95bd0d56f35241523fbab1                                               So11111111111111111111111111111111111111112                                                  0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2                                              EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
toTokenAddress                              0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270                          0x82af49447d8a07e3bd95bd0d56f35241523fbab1                                               So11111111111111111111111111111111111111112                                                  0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2                                              EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
fromAddress                                 0x4522a2130fb830f4f9a601fc6e6d5645f6291b5c                          0xca74d2f75aab40de4f3ad8d034f6bbcad530f48a                                              97pxvewfnbuxlmkmjdwyhgkxrhvlxsgrnwklyywxywer                                                  0xf5bae291a28c61f5137bb8ab6ec224e315bf6134                                              1417ary7djms6pnxztzw9yg26tsujfckruj9fhmmvhdq
toAddress           0x8b47fa4b2f8839bdc673b4ccbcd5b2ba6214f1f3a4af55251b0654eb697cc1df                         zekdezapa2a8gsok7a7mgafen7jmgeflgwwbcjdtfbm                                                0x99870f09efcf74a36e467a191395bfa6df00e53f                                                4rrfmky3a5zwdizt61px222qmstjqnvszdebzznsoah6                        0x2625274deea90cdd3fae44758b33116094b2e7b0207b9b87325be52509b8d55e
srcUSD                                                                         0.31062                                                              208.61                                                                                   203.217                                                                                     223.776                                                                                  0.099941
dstUSD                                                                         0.31062                                                              208.61                                                                                   203.217                                                                                     223.776                                                                                  0.099941
createTime                                                   2023-12-31 11:56:24+00:00                                           2023-12-01 23:34:24+00:00                                                                 2023-12-23 14:01:21+00:00                                                                   2023-12-11 07:08:47+00:00                                                                 2023-12-10 19:26:16+00:00
completeTime                                          2023-12-31 14:06:13.174000+00:00                                                                 NaT                                                                                       NaT                                                            2023-12-11 07:26:27.751000+00:00                                                          2023-12-10 19:27:07.113000+00:00
profit                                                                             0.0                                                                 0.0                                                                                       0.0                                                                                         0.0                                                                                       0.0
isProfit                                                                             0                                                                   0                                                                                         0                                                                                           0                                                                                         0
profitRatio                                                                        1.0                                                                 1.0                                                                                       1.0                                                                                         1.0                                                                                       1.0
null rate (first 200 rows):
_id                 0.000
bridge              0.000
fromChainRaw        0.000
toChainRaw          0.000
fromChain           0.495
toChain             0.620
srcAmount           0.000
dstAmount           0.000
srcTxhash           0.000
dstTxhash           0.540
fromTokenAddress    0.000
toTokenAddress      0.000
fromAddress         0.000
toAddress           0.000
srcUSD              0.000
dstUSD              0.000
createTime          0.000
completeTime        0.540
profit              0.000
isProfit            0.000
profitRatio         0.000
```

### Step 5. Build the standard ledger

```bash
python3 scripts/03_build_ledger.py
```

**What it does.** Reads the Wormhole file listed under `bridges:` in `config.yaml` and converts it to a standard ledger through `bbe/adapters.py`. The adapter maps the columns, converts timestamps (missing completion times become missing values, not numbers), normalises chain ids (for example `"1.0"` becomes `"1"`), converts USD amounts to integer micro-USD, and keeps only rows with a completion time at or after the deposit time and positive amounts. Accounts are (chain, address) pairs, so the same address on two chains is two accounts (`chain_qualified: true`).

**Expected output.** A line such as `wormhole: raw=<N> kept=<M> mapping={...}` followed by a summary table of the ledger. `kept` is smaller than `raw` because incomplete or invalid transfers are removed. The files are `data/processed/ledger.parquet` and `outputs/ledger_build_report.txt`. If the script reports unmapped columns, return to step 4 and fix `config.yaml`.

```
(.venv) menaka@ubuntu-test:~/bbe_sim$ python3 scripts/03_build_ledger.py
wormhole: raw=699474 kept=250527 mapping={'src_addr': 'fromAddress', 'dst_addr': 'toAddress', 'token': 'fromTokenAddress', 'amt_in': 'srcUSD', 'amt_out': 'dstUSD', 't_dep': 'createTime', 't_wd': 'completeTime', 'src_chain': 'fromChainRaw', 'dst_chain': 'toChainRaw', 'fee': None, 'pair_id': '_id'}
              count  unique                                           top    freq               mean                 std           min           25%           50%           75%               max
src_addr     250527  133695    0x4cb6f0ef0eeb503f8065af1a6e6d5dd46197d3d9    1630                NaN                 NaN           NaN           NaN           NaN           NaN               NaN
dst_addr     250527   73047  gytw6attsqjwjsbqdtsmxtkd1797zsfspdawg64ryo1y   17487                NaN                 NaN           NaN           NaN           NaN           NaN               NaN
token        250527     344    0x82af49447d8a07e3bd95bd0d56f35241523fbab1   21037                NaN                 NaN           NaN           NaN           NaN           NaN               NaN
amt_in_u   250527.0    <NA>                                          <NA>    <NA>  3478475199.379564  57178977188.414429           1.0     4374997.5    82955209.0   522767571.5  20532943417800.0
amt_out_u  250527.0    <NA>                                          <NA>    <NA>  3478475199.379564  57178977188.414429           1.0     4374997.5    82955209.0   522767571.5  20532943417800.0
t_dep      250527.0     NaN                                           NaN     NaN  1701433959.887146      3377425.727042  1684568100.0  1701775681.5  1702418651.0  1703293646.0      1704067191.0
t_wd       250527.0     NaN                                           NaN     NaN  1701464868.806141      3349655.015498  1684568306.0  1701780913.5  1702432064.0  1703317341.0      1705774211.0
src_chain    250527      23                                             1   51952                NaN                 NaN           NaN           NaN           NaN           NaN               NaN
dst_chain    250527      15                                           1.0   58862                NaN                 NaN           NaN           NaN           NaN           NaN               NaN
fee_u      250527.0    <NA>                                          <NA>    <NA>                0.0                 0.0           0.0           0.0           0.0           0.0               0.0
pair_id      250527  250527                      65cbda8b6595a18bd8428ccd       1                NaN                 NaN           NaN           NaN           NaN           NaN               NaN
bridge       250527       1                                      wormhole  250527                NaN                 NaN           NaN           NaN           NaN           NaN               NaN
```

### Step 6. (Optional) Check parameters

Open `config.yaml`. The values used in the paper are:

| Parameter | Value | Meaning |
|---|---|---|
| `theta` | `[1, 10]` | Balance-share thresholds as percentages (1% and 10%); see the paper's Section 3 for the exact definition |
| `delta_usd` | `[1, 5, 10, 50, 100, 500, 1000]` | Floor values for BBE |
| `budgets_usd` | `[100, 1000, 10000]` | Attacker budgets |
| `cost_per_transfer_usd` | `0.05` | Attacker cost `c` per dust transfer |
| `link_window_s` | `[600, 1800, 3600, 7200]` | Linking time windows |
| `link_fee_tol` | `[0.005, 0.01, 0.02, 0.05]` | Linking fee tolerances |
| `link_sample` | `10000` | Number of deposits sampled for E1 |
| `hub_receipt_threshold` | `100` | A destination with more receipts than this is a hub or relayer |
| `e4_seed_count` | `200` | Hypothetical seeds for E4 (volume between 1,000 and 1,000,000 USD) |
| `linker_pi_variants` | `[0.0, 0.5]` | Confidence thresholds for the conserving linker in E4 |
| `victim_sample` | `5000` | Victims replayed in E3 |
| `bootstrap_n` | `2000` | Bootstrap resamples |
| `chain_qualified` | `true` | Accounts are (chain, address) |

Changing any value changes the results. Keep a copy of the configuration you used.

### Step 7. Run the experiments

```bash
python3 scripts/05_run_experiments.py
```

**What it does.** Runs six experiments and writes the CSV files below. All amounts are integer micro-USD; the haircut replay uses Python integers because 64-bit arrays overflowed on large amounts.

| Experiment | Question | What the script does | Output files |
|---|---|---|---|
| **E1** Linking | How ambiguous is bridge-link inference on real data? | For a sample of deposits, finds the withdrawals in the full pool that match on time window, fee tolerance, token and destination chain. Records the number of candidates `k`, the precision and recall of the link, and how recall changes with the confidence threshold `pi` | `E1_linking.csv`, `E1_pi_sweep.csv`, `E1_k_hist.csv` |
| **E2** Leverage | How many victims can an attacker flag with a given budget under each rule? | Computes the closed-form leverage for poison, share-only and BBE on all destinations and on non-hub destinations, with 95% bootstrap confidence intervals | `E2_leverage.csv`, `E2b_bootstrap.csv` |
| **E3** Replay | Does the closed form match an actual ledger replay? | Takes 5,000 victims, injects the attacker's minimal dust in memory, replays the ledger under each policy, and counts how many results differ from the closed form | `E3_replay.csv` |
| **E4** Visibility | How much real tainted value stays visible after crossing a bridge? | Seeds hypothetical addresses on real flows, carries taint across the bridge using the true link and using the conserving linker, and measures how much tainted value is visible at arrival for each floor `delta` | `E4_recall.csv` |
| **E5** Case trace | What does one tainted path look like? | Writes the hop-by-hop trace of one seeded flow | `E5_case_trace.csv` |
| **E6** Chains | Does the result depend on the destination chain? | Reports leverage and ambiguity per destination chain and the 25 busiest chain pairs | `E6_by_dst_chain.csv`, `E6_chain_pairs.csv` |

All headline numbers (counts, medians, the mismatch counter, the number of non-hub addresses, and so on) are also written to `outputs/summary.json`.

**Expected output.** Progress lines for E1 to E6, then `summary.json` written. Check these:

- In `E3_replay.csv`, the closed-form and replay values must agree: the mismatch count must be **0**. A non-zero count means the code or the data have changed since the paper.
- In `E1_linking.csv`, the mean `k` at a 1-hour window and 2% fee tolerance is about 4.59 in the paper's run.
- In `summary.json`, the median victim balance in USD must be plausible. If it is not, check the amount columns in `config.yaml`.
- E4 does not use a sanctioned-address overlap, because the OFAC list has no overlap with the ledger. The output is labelled as hypothetical seeds.

The script may take longer on a small VM because E1 searches the full withdrawal pool and E3 replays 5,000 victims three times.

```
(.venv) menaka@ubuntu-test:~/bbe_sim$ python3 scripts/05_run_experiments.py
{
  "n_transfers": 250527,
  "chain_qualified": true,
  "n_dst_addresses_unqualified": 73047,
  "n_src_chains": 23,
  "n_dst_chains": 15,
  "n_dst_addresses": 103022,
  "n_hubs_removed": 80,
  "hub_share_of_value": 0.2429257140877416,
  "victims_all": 103022,
  "median_balance_usd_all": 29.70022,
  "victims_nonhub": 102942,
  "median_balance_usd_nonhub": 29.5,
  "ofac_overlap_src": 0,
  "ofac_overlap_dst": 0,
  "e4_seed_type": "hypothetical_seeds_on_real_flows",
  "e4_n_seeds": 200,
  "case_address": "22:0x2aa1798ebefa3be924c6c630d453146a6e865755be0dde784c69925982d5436a",
  "E1_mean_k_central": 4.5946
}
```

### Step 8. Make the figures

```bash
python3 scripts/06_make_figures.py
```

**What it does.** Reads the CSV files from step 7 and draws the figures.

**Expected output.** `figures written to outputs/`, and these files in `outputs/`:

- `fig_leverage.png`: victims flagged versus the floor `delta`, for each budget, comparing BBE with the share rule and poison (non-hub population)
- `fig_ambiguity.png`: mean number of candidates per deposit versus the time window, one line per fee tolerance
- `fig_pi.png`: link recall versus the confidence threshold `pi`
- `fig_recall.png`: tainted value visible at arrival versus `delta` (only if E4 produced results)

### Step 8b. Run the sensitivity analyses

```bash
python3 scripts/08_sensitivity.py
```

**What it does.** Repeats parts of E2-E4 while varying one design choice at a time (values in the `sensitivity:` block of `config.yaml`). It reads the same real ledger and changes nothing in it.

| Analysis | Varies | Output file |
|---|---|---|
| S1 | Attacker cost per transfer `c` (0.01, 0.05, 0.25, 1 USD); checks flagged <= bound `B/(delta+c)` | `S1_cost_sweep.csv` |
| S2 | Hub-exclusion threshold (10, 50, 100, 500 receipts) | `S2_hub_threshold.csv` |
| S3 | Random seed (5 values) and victim sample size (1,000, 5,000, 10,000) in the E3 replay | `S3_replay_stability.csv` |
| S4 | Draw and volume range of the hypothetical E4 seeds | `S4_e4_stability.csv` |
| S5 | Assumed opening balance of every victim (0, 100, 1,000 USD) | `S5_opening_balance.csv` |
| S6 | Share threshold theta (1%, 5%, 10%, 20%): closed-form leverage and a replay check for each | `S6_theta.csv` |

**Expected output.** `sensitivity_summary.json` and `fig_sens_cost.png` (two panels, floors of 1 and 10 USD, with the bound as dashed lines). Check these: `S1_bound_holds_all` is `true`; `S3_max_mismatch` and `S6_max_mismatch` are `0`; and, if `E3_replay.csv` exists, `S3_reproduces_E3` is `true` (seed offset 0 at 5,000 victims reproduces E3). The S3 and S6 steps replay the ledger 18 times, so it is the slowest part. Run it after step 7.

```
(.venv) menaka@ubuntu-test:~/bbe_sim$ python3 scripts/08_sensitivity.py
{
  "n_transfers": 250527,
  "S1_bound_holds_all": true,
  "S3_max_mismatch": 0,
  "S3_runs": 14,
  "S3_reproduces_E3": true,
  "S5_bbe_floor100_max": 99,
  "S6_max_mismatch": 0,
  "S3_bbe_flagged_fraction_range": [
    1.0,
    1.0
  ],
  "S4_recall_delta100_range": [
    0.9981178203213243,
    0.9998719598955612
  ]
}
sensitivity outputs written to /home/menaka/bbe_sim/scripts/../outputs
```

### Step 9. Collect the outputs

```bash
bash scripts/07_collect_outputs.sh
```

**What it does.** Packs the whole `outputs/` folder into `bbe_outputs.tar.gz` and lists the files.

**Expected output.** A file listing and the archive `bbe_outputs.tar.gz`. To compare with the paper, open the CSV files listed in step 7 and `summary.json`.

---

## 6. Output files

| File | Content |
|---|---|
| `env_report.txt` | Python and package versions |
| `verification_tests.txt` | Unit test log |
| `download_integrity.txt` | md5 check of each downloaded file |
| `schema_report.txt` | Raw data schema, row counts and null rates |
| `ledger_build_report.txt` | Rows read and kept, column mapping, ledger summary |
| `E1_linking.csv`, `E1_pi_sweep.csv`, `E1_k_hist.csv` | Linking ambiguity, recall versus `pi`, histogram of `k` |
| `E2_leverage.csv`, `E2b_bootstrap.csv` | Attacker leverage by rule, with 95% confidence intervals |
| `E3_replay.csv` | Replay versus closed form, and the mismatch count |
| `E4_recall.csv` | Taint visibility after the bridge (hypothetical seeds on real flows) |
| `E5_case_trace.csv` | Case study trace |
| `E6_by_dst_chain.csv`, `E6_chain_pairs.csv` | Per-chain and chain-pair breakdown |
| `S1_cost_sweep.csv` ... `S6_theta.csv`, `sensitivity_summary.json`, `fig_sens_cost.png` | Sensitivity analyses (step 8b) |
| `summary.json` | All headline numbers |
| `fig_*.png` | Figures used in the paper |

A small set of the result files used in the paper is stored in `results/` (if included in this repository) so reviewers can check the numbers without re-running the experiments.

```
(.venv) menaka@ubuntu-test:~/bbe_sim$ bash scripts/07_collect_outputs.sh
total 560
drwxr-xr-x  2 menaka menaka   4096 Oct 25 03:58 .
drwxrwxr-x 10 menaka menaka   4096 Oct 25 03:49 ..
-rw-rw-r--  1 menaka menaka    129 Oct 25 03:56 E1_k_hist.csv
-rw-rw-r--  1 menaka menaka    936 Oct 25 03:56 E1_linking.csv
-rw-rw-r--  1 menaka menaka    334 Oct 25 03:56 E1_pi_sweep.csv
-rw-rw-r--  1 menaka menaka   1987 Oct 25 03:57 E2_leverage.csv
-rw-rw-r--  1 menaka menaka    754 Oct 25 03:57 E2b_bootstrap.csv
-rw-rw-r--  1 menaka menaka    715 Oct 25 03:57 E3_replay.csv
-rw-rw-r--  1 menaka menaka    301 Oct 25 03:57 E4_conservation.csv
-rw-rw-r--  1 menaka menaka   3851 Oct 25 03:57 E4_recall.csv
-rw-rw-r--  1 menaka menaka    747 Oct 25 03:57 E5_case_trace.csv
-rw-rw-r--  1 menaka menaka   1224 Oct 25 03:57 E6_by_dst_chain.csv
-rw-rw-r--  1 menaka menaka    658 Oct 25 03:57 E6_chain_pairs.csv
-rw-rw-r--  1 menaka menaka   4224 Oct 25 03:58 S1_cost_sweep.csv
-rw-rw-r--  1 menaka menaka   1079 Oct 25 03:58 S2_hub_threshold.csv
-rw-rw-r--  1 menaka menaka   1010 Oct 25 03:58 S3_replay_stability.csv
-rw-rw-r--  1 menaka menaka   4484 Oct 25 03:58 S4_e4_stability.csv
-rw-rw-r--  1 menaka menaka    423 Oct 25 03:58 S5_opening_balance.csv
-rw-rw-r--  1 menaka menaka   1146 Oct 25 03:58 S6_theta.csv
-rw-rw-r--  1 menaka menaka 101416 Oct 25 03:57 fig_ambiguity.png
-rw-rw-r--  1 menaka menaka  84589 Oct 25 03:57 fig_leverage.png
-rw-rw-r--  1 menaka menaka  50315 Oct 25 03:57 fig_pi.png
-rw-rw-r--  1 menaka menaka  79732 Oct 25 03:57 fig_recall.png
-rw-rw-r--  1 menaka menaka  90678 Oct 25 03:58 fig_sens_cost.png
-rw-rw-r--  1 menaka menaka    332 Oct 25 03:53 filter_retained_vs_excluded_wormhole.csv
-rw-rw-r--  1 menaka menaka    611 Oct 25 03:53 filter_retention_by_dst_chain_wormhole.csv
-rw-rw-r--  1 menaka menaka    319 Oct 25 03:53 filter_steps_wormhole.csv
-rw-rw-r--  1 menaka menaka   3799 Oct 25 03:53 ledger_build_report.txt
-rw-rw-r--  1 menaka menaka  39845 Oct 25 03:53 schema_report.txt
-rw-rw-r--  1 menaka menaka    322 Oct 25 03:58 sensitivity_summary.json
-rw-rw-r--  1 menaka menaka    610 Oct 25 03:57 summary.json
-rw-rw-r--  1 menaka menaka   1773 Oct 25 03:55 verification_tests.txt
Send me bbe_outputs.tar.gz (or paste the CSV/TXT/JSON contents).
(.venv) menaka@ubuntu-test:~/bbe_sim$ 
```
---

## 7. Method summary and how the code maps to the paper

| Paper component | Code |
|---|---|
| Taint policies (poison, haircut, FIFO) and the BBE flag rule | `bbe/engine.py` |
| Minimal dust and attacker leverage (Theorem 1) | `bbe/attack.py` |
| Bridge-link inference, ambiguity `k`, confidence threshold `pi` | `bbe/linking.py` |
| Data schema mapping and filters | `bbe/adapters.py`, `config.yaml` |
| Bootstrap confidence intervals | `bbe/stats.py` |
| Experiments E1-E6 | `scripts/05_run_experiments.py` |

---

## 8. Limitations (the same as in the paper)

- The results use one bridge (Wormhole). The other Zenodo bridges are not used because their completion times or USD amounts are missing or incomplete.
- Opening balances are not observed. A victim's balance is the sum of bridge-observed receipts, so leverage for the non-BBE policies is an upper bound.
- E4 uses hypothetical seed addresses on real flows, because no sanctioned address appears in the ledger.
- The collision (framing) attack on the bridge linker is shown as an arithmetic example and is not tested on the data.
- Accounts are (chain, address) pairs and are not clustered across chains.
- The dataset's USD values come from the dataset authors and were not audited.

---

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `FAIL` in `download_integrity.txt` | Delete that file from `data/raw/` and run step 3 again |
| `KeyError` or "unmapped column" in step 5 | Compare `schema_report.txt` with the `columns:` section of `config.yaml` |
| `MemoryError` or the process is killed | Use a machine with more RAM, or lower `link_sample` and `victim_sample` (this changes the results) |
| Tests fail | Do not continue; send `outputs/verification_tests.txt` and `outputs/env_report.txt` |
| Results differ from the paper | Check that `config.yaml` and `seed` are unchanged and that the dataset md5 sums match |

---

## 10. Data licences, citation and contact

- Cross-chain data: Zenodo record 15354599. Follow the licence and citation request on that record. [Add the dataset citation and DOI here.]
- OFAC list: US Treasury Office of Foreign Assets Control, via https://github.com/0xB10C/ofac-sanctioned-digital-currency-addresses
- Code licence: [add a licence, for example MIT, and a `LICENSE` file]

