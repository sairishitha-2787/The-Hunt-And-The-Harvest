"""The say-do gap per country, for men and women separately.

Input: the cleaned sample from clean.build_sample() (one row per partnered
respondent). Output: one row per country and sex with the weighted share of
supporters who are true egalitarians, its 95% CI, and a rank within that sex.

Men and women are never pooled: men describe their own share of the housework,
women describe their partner's, so the two answers measure different things.
"""

import pandas as pd

from harvest_hunt.stats import weighted_share

MIN_GROUP = 50  # fewer supporters of one sex in a country -> flagged, not ranked


def say_do_by_country(sample: pd.DataFrame, min_group: int = MIN_GROUP) -> pd.DataFrame:
    """Share of supporters who are true egalitarians, per country and sex.

    Only supporters with a known group (true_egalitarian or unshared_supporter)
    are counted. Ranks run separately for men and women, 1 = highest share,
    and skip flagged small groups.
    """
    supporters = sample[sample["group"].notna()]
    rows = []
    for (country, sex), g in supporters.groupby(["country", "sex"]):
        est = weighted_share(g["group"].eq("true_egalitarian"), g["weight"])
        rows.append({"country": country, "sex": sex, **est})
    out = pd.DataFrame(rows)

    out["small_group"] = out["n"] < min_group
    # Majority by the point estimate, and "clearly" a majority when the whole
    # interval sits above 50%. Both are reported; the README says which is which.
    out["majority"] = out["share"] > 0.5
    out["clear_majority"] = out["ci_low"] > 0.5

    ranked = ~out["small_group"]
    out["rank"] = pd.NA
    out.loc[ranked, "rank"] = (out[ranked].groupby("sex")["share"]
                               .rank(ascending=False, method="min"))
    out["rank"] = out["rank"].astype("Int64")

    return (out.sort_values(["sex", "rank", "country"], na_position="last")
               .reset_index(drop=True))
