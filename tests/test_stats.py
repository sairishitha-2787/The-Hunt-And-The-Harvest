import numpy as np
import pandas as pd
import pytest

from harvest_hunt import stats


# --- effective_n ---------------------------------------------------------------

def test_effective_n_equal_weights_is_plain_count():
    # The 8 unweighted countries (all weights 1) must get their real sample size.
    assert stats.effective_n(pd.Series([1.0] * 50)) == pytest.approx(50)


def test_effective_n_hand_checked():
    # Weights 1, 1, 2: (1+1+2)^2 / (1+1+4) = 16 / 6 = 2.667
    assert stats.effective_n(pd.Series([1, 1, 2])) == pytest.approx(16 / 6)


def test_effective_n_ignores_rescaling():
    # normalise_weights() rescales per country; that must not change n_eff.
    w = pd.Series([0.5, 1.2, 3.0, 0.8])
    assert stats.effective_n(w) == pytest.approx(stats.effective_n(w * 7.3))


# --- wilson_interval -----------------------------------------------------------

def test_wilson_textbook_value():
    # p = 0.5, n = 100 -> about (0.404, 0.596)
    low, high = stats.wilson_interval(0.5, 100)
    assert low == pytest.approx(0.4038, abs=1e-4)
    assert high == pytest.approx(0.5962, abs=1e-4)


def test_wilson_zero_successes_stays_in_range():
    # 0 of 10: the simple interval would be (0, 0); Wilson gives (0, 0.278).
    low, high = stats.wilson_interval(0.0, 10)
    assert low == 0.0
    assert high == pytest.approx(0.2775, abs=1e-4)


def test_wilson_smaller_n_is_wider():
    low50, high50 = stats.wilson_interval(0.4, 50)
    low500, high500 = stats.wilson_interval(0.4, 500)
    assert (high50 - low50) > (high500 - low500)


# --- weighted_share ------------------------------------------------------------

def test_weighted_share_hand_checked():
    # Flags T, F, T, F with weights 3, 1, 1, 1:
    # share = (3 + 1) / 6 = 0.667; n_eff = 6^2 / (9+1+1+1) = 3
    out = stats.weighted_share(pd.Series([True, False, True, False]),
                               pd.Series([3.0, 1.0, 1.0, 1.0]))
    assert out["share"] == pytest.approx(4 / 6)
    assert out["n"] == 4
    assert out["n_eff"] == pytest.approx(3.0)
    assert out["ci_low"] < out["share"] < out["ci_high"]


def test_weighted_share_drops_missing_flags():
    flag = pd.Series([True, np.nan, False], dtype="object")
    out = stats.weighted_share(flag, pd.Series([1.0, 100.0, 1.0]))
    assert out["n"] == 2
    assert out["share"] == pytest.approx(0.5)  # the weight-100 row is ignored


def test_weighted_share_empty_group():
    out = stats.weighted_share(pd.Series([], dtype="object"), pd.Series([], dtype=float))
    assert out["n"] == 0 and np.isnan(out["share"])
