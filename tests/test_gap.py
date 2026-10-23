import numpy as np
import pandas as pd
import pytest

from harvest_hunt import gap


def people(country, sex, n_true, n_unshared, n_non_supporters=0, weight=1.0):
    """Fake cleaned-sample rows: true egalitarians, unshared supporters, non-supporters."""
    groups = (["true_egalitarian"] * n_true + ["unshared_supporter"] * n_unshared
              + [np.nan] * n_non_supporters)
    return pd.DataFrame({"country": country, "sex": sex, "weight": weight,
                         "group": pd.Series(groups, dtype="object")})


@pytest.fixture
def sample():
    return pd.concat([
        people("AA", "man", 40, 20, n_non_supporters=30),  # 40/60 = 0.667
        people("BB", "man", 20, 40),                       # 20/60 = 0.333
        people("DD", "man", 33, 27),                       # 33/60 = 0.55
        people("CC", "man", 9, 1),                         # only 10 -> small group
        people("AA", "woman", 30, 30),                     # 30/60 = 0.5
        people("CC", "woman", 45, 15),                     # 45/60 = 0.75
    ], ignore_index=True)


def row(table, country, sex):
    return table[(table["country"] == country) & (table["sex"] == sex)].iloc[0]


def test_one_row_per_country_and_sex(sample):
    out = gap.say_do_by_country(sample)
    assert len(out) == 6


def test_shares_ignore_non_supporters(sample):
    out = gap.say_do_by_country(sample)
    r = row(out, "AA", "man")
    assert r["share"] == pytest.approx(40 / 60)
    assert r["n"] == 60  # the 30 non-supporters are not counted


def test_men_and_women_are_not_pooled(sample):
    out = gap.say_do_by_country(sample)
    assert row(out, "AA", "woman")["share"] == pytest.approx(0.5)


def test_small_group_flagged_and_unranked(sample):
    out = gap.say_do_by_country(sample)
    r = row(out, "CC", "man")
    assert bool(r["small_group"]) is True
    assert pd.isna(r["rank"])
    # CC's women are big enough, so they are still ranked.
    assert row(out, "CC", "woman")["rank"] == 1


def test_ranks_are_separate_per_sex(sample):
    out = gap.say_do_by_country(sample)
    assert row(out, "AA", "man")["rank"] == 1
    assert row(out, "DD", "man")["rank"] == 2
    assert row(out, "BB", "man")["rank"] == 3
    assert row(out, "AA", "woman")["rank"] == 2


def test_majority_flags(sample):
    out = gap.say_do_by_country(sample)
    aa_women = row(out, "AA", "woman")   # exactly 0.5 is not a majority
    assert bool(aa_women["majority"]) is False
    cc_women = row(out, "CC", "woman")   # 0.75 with n = 60: CI clears 0.5
    assert bool(cc_women["majority"]) and bool(cc_women["clear_majority"])
    aa_men = row(out, "AA", "man")       # 0.667, n = 60: CI (0.54, 0.77) clears 0.5
    assert bool(aa_men["clear_majority"])
    dd_men = row(out, "DD", "man")       # 0.55, n = 60: CI (0.42, 0.67) dips below 0.5
    assert bool(dd_men["majority"]) and not bool(dd_men["clear_majority"])


# --- perception gap ------------------------------------------------------------

def reports(country, sex, task_answers):
    return pd.DataFrame({"country": country, "sex": sex, "weight": 1.0,
                         "task_laundry": pd.Series(task_answers, dtype="object")})


def test_perception_gap_hand_checked():
    sample = pd.concat([
        # Men: 30 of 60 couple-done answers say the woman does it -> 0.5
        reports("AA", "man", ["woman"] * 30 + ["equal"] * 20 + ["man"] * 10),
        # Women: 48 of 60 -> 0.8; the 5 "third" answers are left out
        reports("AA", "woman", ["woman"] * 48 + ["equal"] * 12 + ["third"] * 5),
    ], ignore_index=True)
    out = gap.perception_gap(sample, tasks=["task_laundry"])
    r = out.iloc[0]
    assert r["task"] == "laundry"
    assert r["men_say_woman"] == pytest.approx(0.5)
    assert r["women_say_woman"] == pytest.approx(0.8)
    assert r["women_n"] == 60
    assert r["gap"] == pytest.approx(0.3)
    assert r["gap_ci_low"] < 0.3 < r["gap_ci_high"]
    assert r["gap_ci_low"] > 0  # a 30-point gap on 60 + 60 is clearly not zero
    assert bool(r["small_group"]) is False


def test_perception_gap_flags_small_groups():
    sample = pd.concat([
        reports("AA", "man", ["woman"] * 10 + ["equal"] * 10),   # only 20
        reports("AA", "woman", ["woman"] * 40 + ["equal"] * 20),
    ], ignore_index=True)
    out = gap.perception_gap(sample, tasks=["task_laundry"])
    assert bool(out.iloc[0]["small_group"]) is True


def test_newcombe_matches_published_example():
    # Newcombe (1998), example (a): 56/70 vs 48/80 -> difference 0.2000,
    # 95% CI 0.0524 to 0.3339 (method 10).
    from harvest_hunt.stats import wilson_interval
    p1, p2 = 56 / 70, 48 / 80
    l1, h1 = wilson_interval(p1, 70)
    l2, h2 = wilson_interval(p2, 80)
    low, high = gap.newcombe_difference(p1, l1, h1, p2, l2, h2)
    assert low == pytest.approx(0.0524, abs=1e-4)
    assert high == pytest.approx(0.3339, abs=1e-4)