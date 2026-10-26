import numpy as np


def bootstrap_ci(x, stat=np.mean, n=2000, seed=12345, alpha=0.05):
    x = np.asarray(x)
    rng = np.random.default_rng(seed)
    s = [stat(x[rng.integers(0, len(x), len(x))]) for _ in range(n)]
    return float(stat(x)), float(np.quantile(s, alpha / 2)), float(np.quantile(s, 1 - alpha / 2))
