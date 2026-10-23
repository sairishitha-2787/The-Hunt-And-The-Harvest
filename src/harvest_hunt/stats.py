"""Weighted shares with confidence intervals for The Harvest and the Hunt.

Every estimate in Session 2 is a share: "of these supporters, what fraction are
true egalitarians?" This module turns a column of True/False flags plus survey
weights into that share, its effective sample size, and a 95% Wilson interval.

CIs assume simple random sampling within each country, adjusted for weighting
through Kish's effective sample size. ISSP publishes no clusters or strata, so
the intervals are probably somewhat too narrow (see definitions.md, "Weights").
"""

import numpy as np
import pandas as pd

Z_95 = 1.959963984540054  # standard normal quantile for a two-sided 95% interval


def effective_n(weights: pd.Series) -> float:
    """Kish's effective sample size: (sum of w)^2 / (sum of w^2).

    Equals the plain count when every weight is equal, and shrinks as weights
    become more uneven, because a few heavily weighted people carry more of the
    estimate. Rescaling all weights by a constant doesn't change it.
    """
    w = pd.Series(weights, dtype=float)
    if w.empty:
        return 0.0
    return float(w.sum() ** 2 / (w ** 2).sum())


def wilson_interval(p: float, n: float, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a proportion p from n observations.

    Unlike the simple "p plus or minus 1.96 standard errors", it never goes
    below 0 or above 1 and stays sensible for small n or p near 0 or 1.
    n may be fractional (an effective sample size).
    """
    if n <= 0:
        return (np.nan, np.nan)
    z2 = z * z
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = (z / (1 + z2 / n)) * np.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def weighted_share(flag: pd.Series, weights: pd.Series, z: float = Z_95) -> dict:
    """Weighted share of True in `flag`, with n, effective n and a Wilson CI.

    Rows where `flag` is missing are dropped first. Returns a dict so results
    can go straight into a DataFrame row or a JSON file.
    """
    keep = pd.Series(flag).notna()
    f = pd.Series(flag)[keep].astype(bool).to_numpy()
    w = pd.Series(weights, dtype=float)[keep].to_numpy()
    n = int(len(f))
    if n == 0:
        return {"share": np.nan, "n": 0, "n_eff": 0.0, "ci_low": np.nan, "ci_high": np.nan}
    share = float((w * f).sum() / w.sum())
    n_eff = effective_n(w)
    low, high = wilson_interval(share, n_eff, z)
    return {"share": share, "n": n, "n_eff": n_eff, "ci_low": low, "ci_high": high}
