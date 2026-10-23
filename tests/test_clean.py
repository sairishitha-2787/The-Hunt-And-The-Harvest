import numpy as np
import pandas as pd
import pytest

from harvest_hunt import clean
from harvest_hunt import config as C

M, F = C.MALE, C.FEMALE


def test_missing_codes_become_nan():
    df = pd.DataFrame({"q": [1, -8, 3, -9]})
    out = clean.to_missing(df, ["q"], [-8, -9])
    assert out["q"].isna().tolist() == [False, True, False, True]
    assert df["q"].tolist() == [1, -8, 3, -9]  # original untouched


def test_me_and_partner_flip_with_respondent_sex():
    answers = pd.Series([C.ALWAYS_ME, C.ALWAYS_ME, C.USUALLY_PARTNER, C.USUALLY_PARTNER])
    sex = pd.Series([F, M, F, M])
    assert clean.task_done_by(answers, sex).tolist() == ["woman", "man", "man", "woman"]


def test_equal_third_person_and_missing():
    answers = pd.Series([C.EQUAL, C.THIRD_PERSON, np.nan])
    out = clean.task_done_by(answers, pd.Series([M, F, M]))
    assert out.tolist()[:2] == ["equal", "third"]
    assert pd.isna(out.iloc[2])


def test_shared_threshold_is_inclusive():
    done_by = pd.DataFrame([["equal", "man", "woman", "woman"]])  # 2 of 4 = 0.5
    assert clean.shared_household(done_by, threshold=0.5, min_tasks=3).iloc[0] is True
    assert clean.shared_household(done_by, threshold=0.6, min_tasks=3).iloc[0] is False


def test_third_person_tasks_are_left_out():
    # Paid help does laundry; of the 3 remaining tasks 2 are fair -> 0.67.
    done_by = pd.DataFrame([["third", "equal", "equal", "woman"]])
    assert clean.shared_household(done_by, threshold=0.6, min_tasks=3).iloc[0] is True


def test_too_few_answered_tasks_is_missing():
    done_by = pd.DataFrame([["equal", "third", np.nan, np.nan]])
    assert pd.isna(clean.shared_household(done_by, min_tasks=3).iloc[0])


def test_classify_only_supporters():
    sup = pd.Series([True, True, False, np.nan], dtype="object")
    shared = pd.Series([True, False, True, True], dtype="object")
    out = clean.classify(sup, shared)
    assert out.tolist()[:2] == ["true_egalitarian", "unshared_supporter"]
    assert out.iloc[2:].isna().all()


def test_supporter_missing_stays_missing():
    out = clean.supporter(pd.Series([4, 5, 3, np.nan]), codes=[4, 5])
    assert out.tolist()[:3] == [True, True, False]
    assert pd.isna(out.iloc[3])


def test_weights_average_one_per_country_and_unweighted_country_gets_one():
    w = pd.Series([2.0, 1.0, 1.0, np.nan, np.nan])
    country = pd.Series(["IN", "IN", "IN", "IS", "IS"])
    out = clean.normalise_weights(w, country)
    assert out[country == "IN"].mean() == pytest.approx(1.0)
    assert out[country == "IS"].tolist() == [1.0, 1.0]


def test_partly_missing_weights_raise():
    with pytest.raises(ValueError):
        clean.normalise_weights(pd.Series([1.0, np.nan]), pd.Series(["IN", "IN"]))


def test_woman_hours_share_flips_with_sex():
    own = pd.Series([30.0, 10.0, 0.0, np.nan])
    partner = pd.Series([10.0, 30.0, 0.0, 5.0])
    sex = pd.Series([F, M, F, F])
    out = clean.woman_hours_share(own, partner, sex)
    assert out.iloc[0] == pytest.approx(0.75)   # she says 30 vs his 10
    assert out.iloc[1] == pytest.approx(0.75)   # he says 10 vs her 30
    assert out.iloc[2:].isna().all()            # 0 + 0, and missing


def test_not_working_means_zero_paid_hours():
    hours = pd.Series([40.0, np.nan, np.nan, np.nan])
    work = pd.Series([1, 2, 3, np.nan])        # working, past, never, unknown
    out = clean.zero_hours_if_not_working(hours, work)
    assert out.tolist()[:3] == [40.0, 0.0, 0.0]
    assert pd.isna(out.iloc[3])


def make_raw():
    """Three respondents in the real file's layout."""
    return pd.DataFrame({
        "c_alphan": ["IN", "IN", "IN"],
        "SEX": [M, F, M],
        "PARTLIV": [1, 1, 3],                  # third person has no partner -> dropped
        "WEIGHT_COM": [1.0, 3.0, 1.0],
        "v39": [C.EQUAL, C.ALWAYS_ME, -4],
        "v40": [C.ALWAYS_ME, C.ALWAYS_ME, -4],
        "v41": [C.USUALLY_PARTNER, -8, -4],     # -8 = can't choose
        "v42": [-9, -9, -4], "v43": [-9, -9, -4], "v44": [-9, -9, -4],
        "v34": [10, 25, 5], "v36": [10, -9, -4],
        "v6": [5, 4, 1],                        # first two disagree -> supporters
        "AGE": [40, 35, 60], "EDULEVEL": [6, 3, 1],
        "WORK": [1, 2, 1], "SPWORK": [1, 1, -4],
        "WRKHRS": [45, -4, 40], "SPWRKHRS": [30, 50, -4],
        "HHCHILDR": [1, 0, 0], "HHTODD": [0, 0, 0], "v45": [3, 1, -4],
    })


def test_build_sample_end_to_end():
    out = clean.build_sample(make_raw())
    assert len(out) == 2
    # Man: equal, he does it, she does it -> 2/3 fair -> true egalitarian.
    assert out["group"].iloc[0] == "true_egalitarian"
    # Woman: only 1 usable task -> shared unknown -> no group.
    assert pd.isna(out["group"].iloc[1])
    assert out["woman_hours_share"].iloc[0] == pytest.approx(0.5)
    assert out["work_hours"].tolist() == [45, 0]     # she is not working -> 0
    assert out["weight"].mean() == pytest.approx(1.0)


def test_sample_flow_counts_each_step():
    raw = make_raw()
    flow = clean.sample_flow(raw, clean.build_sample(raw))
    assert flow.loc["IN"].tolist() == [3, 2, 1, 1, 1]
    assert flow.loc["TOTAL", "all_respondents"] == 3
