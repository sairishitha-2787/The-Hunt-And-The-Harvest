import numpy as np
import pandas as pd
import pytest

from harvest_hunt import clean, sensitivity
from harvest_hunt import config as C

M, F = C.MALE, C.FEMALE


def raw_rows() -> pd.DataFrame:
    """Four partnered respondents, all in one country.

    Fair share of usable tasks (equal or done by the man):
      0 man:   equal, woman, woman, man, man (one missing) -> 3/5 = 0.6
      1 woman: equal, equal, man, woman, woman, woman      -> 3/6 = 0.5
      2 woman: woman x3, equal (two missing)               -> 1/4 = 0.25
      3 man:   all equal                                   -> 1.0
    Supporter: v6 T, T, F, missing; v20 T, F, T, missing; v10 F, T, T, F (4 = TW only).
    Woman's share of household hours: 0.5, 0.75, 0.2 (man does most), both 0.
    """
    tasks = [
        [3, 4, 4, 2, 2, -8],
        [3, 3, 4, 1, 1, 1],
        [1, 1, 1, 3, -8, -9],
        [3, 3, 3, 3, 3, 3],
    ]
    raw = pd.DataFrame(tasks, columns=list(C.TASKS.values()))
    raw[C.COUNTRY] = "AT"
    raw[C.SEX] = [M, F, F, M]
    raw[C.PARTNERED] = 1
    raw[C.WEIGHT] = 1.0
    raw[C.SUPPORTER_ITEM] = [5, 4, 2, -8]
    raw["v20"] = [3, 1, 3, -8]
    raw["v10"] = [3, 1, 2, 4]
    raw[C.HOURS_SELF] = [10, 15, 2, 0]
    raw[C.HOURS_PARTNER] = [10, 5, 8, 0]
    for col in C.COVARIATES.values():
        raw[col] = 1
    return raw


def sample() -> pd.DataFrame:
    return clean.build_sample(raw_rows())


def test_fair_shares_of_the_fixture():
    # Guard the fixture itself, so the threshold tests below mean what they say.
    done_by = sample()[sensitivity.TASK_COLUMNS]
    fair = done_by.isin(["man", "equal"]).sum(axis=1)
    usable = done_by.isin(["man", "equal", "woman"]).sum(axis=1)
    assert (fair / usable).round(2).tolist() == [0.6, 0.5, 0.25, 1.0]


def test_threshold_variants_move_the_line():
    s = sample()
    at40 = sensitivity.variant_sample(s, "threshold_40")["shared"].tolist()
    at60 = sensitivity.variant_sample(s, "threshold_60")["shared"].tolist()
    main = sensitivity.variant_sample(s, "main")["shared"].tolist()
    assert main == [True, True, False, True]
    assert at40 == [True, True, False, True]
    assert at60 == [True, False, False, True]  # 0.5 drops out at 60%


def test_threshold_50_reproduces_main():
    s = sample()
    again = clean.shared_household(s[sensitivity.TASK_COLUMNS], threshold=0.5)
    assert again.tolist() == s["shared"].tolist()


def test_hours_shared_band_is_inclusive_and_strict_outside():
    share = pd.Series([0.4, 0.6, 0.39, 0.61, 0.2, np.nan])
    out = sensitivity.hours_shared(share)
    assert out.tolist()[:5] == [True, True, False, False, False]  # man doing most: not shared
    assert pd.isna(out.iloc[5])


def test_hours_variant_uses_household_hours():
    s = sensitivity.variant_sample(sample(), "hours_40_60")
    # Woman's share 0.5 -> shared; 0.75 -> not; 0.2 -> not; both 0 -> missing.
    assert s["shared"].tolist()[:3] == [True, False, False]
    assert pd.isna(s["shared"].iloc[3])


def test_supporter_variants():
    s = sample()
    assert s["supporter_v20"].tolist()[:3] == [True, False, True]
    assert pd.isna(s["supporter_v20"].iloc[3])          # can't choose -> missing
    assert s["supporter_v10"].tolist() == [False, True, True, False]  # 4 (TW) is not 1-2
    groups = sensitivity.variant_sample(s, "supporter_v20")["group"]
    assert groups.iloc[0] == "true_egalitarian"
    assert groups.iloc[2] == "unshared_supporter"
    assert groups.iloc[[1, 3]].isna().all()  # not a supporter; missing


def test_variant_changes_only_its_own_column():
    s = sample()
    v = sensitivity.variant_sample(s, "supporter_v10")
    pd.testing.assert_series_equal(v["shared"], s["shared"])
    t = sensitivity.variant_sample(s, "threshold_60")
    pd.testing.assert_series_equal(t["supporter"], s["supporter"])
    with pytest.raises(ValueError):
        sensitivity.variant_sample(s, "threshold_55")


def test_sample_sizes_count_known_groups():
    sizes = sensitivity.sample_sizes(sensitivity.variant_sample(sample(), "main"))
    # v6 supporters: rows 0 (man) and 1 (woman); row 3 is missing on v6.
    assert sizes.to_dict() == {"man": 1, "woman": 1, "total": 2}


def test_verdict_counts():
    table = pd.DataFrame({
        "sex": ["man", "man", "man", "man", "woman"],
        "ci_low": [0.55, 0.30, 0.45, 0.60, 0.51],
        "ci_high": [0.70, 0.45, 0.58, 0.90, 0.80],
        "small_group": [False, False, False, True, False],
    })
    counts = sensitivity.verdict_counts(table)
    assert counts.loc["man"].to_dict() == {"clear_majority": 1, "clear_minority": 1,
                                           "unclear": 1, "small_group": 1, "ranked": 3}
    assert counts.loc["woman", "clear_majority"] == 1
