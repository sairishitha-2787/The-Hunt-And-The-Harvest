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


# --- Perception gap ----------------------------------------------------------------

TASK_COLUMNS = ["task_laundry", "task_plan_activities", "task_care_sick",
                "task_groceries", "task_cleaning", "task_meals"]


def newcombe_difference(p1, low1, high1, p2, low2, high2) -> tuple[float, float]:
    """95% CI for p1 - p2 from two independent Wilson intervals (Newcombe's method 10).

    It reuses the Wilson bounds, so it inherits their good behaviour near 0 and 1.
    """
    d = p1 - p2
    low = d - ((p1 - low1) ** 2 + (high2 - p2) ** 2) ** 0.5
    high = d + ((high1 - p1) ** 2 + (p2 - low2) ** 2) ** 0.5
    return (max(-1.0, low), min(1.0, high))


def perception_gap(sample: pd.DataFrame, tasks=TASK_COLUMNS,
                   min_group: int = MIN_GROUP) -> pd.DataFrame:
    """Per country and task: share saying "the woman does it", by men vs by women.

    All partnered respondents count, not only supporters: this is about how the
    two sexes describe the division of work. Tasks done by a third person and
    missing answers are left out, as in the shared-household definition.

    gap = women's share minus men's share. Positive means women more often
    report that the woman does the task. Men and women come from different
    households, so this is a country-level comparison of reports, not a
    within-couple disagreement.
    """
    rows = []
    for country, c in sample.groupby("country"):
        for task in tasks:
            est = {}
            for sex in ["man", "woman"]:
                g = c[(c["sex"] == sex) & c[task].isin(["woman", "man", "equal"])]
                est[sex] = weighted_share(g[task].eq("woman"), g["weight"])
            m, w = est["man"], est["woman"]
            low, high = newcombe_difference(w["share"], w["ci_low"], w["ci_high"],
                                            m["share"], m["ci_low"], m["ci_high"])
            rows.append({
                "country": country,
                "task": task.removeprefix("task_"),
                "men_say_woman": m["share"], "men_ci_low": m["ci_low"],
                "men_ci_high": m["ci_high"], "men_n": m["n"],
                "women_say_woman": w["share"], "women_ci_low": w["ci_low"],
                "women_ci_high": w["ci_high"], "women_n": w["n"],
                "gap": w["share"] - m["share"], "gap_ci_low": low, "gap_ci_high": high,
                "small_group": min(m["n"], w["n"]) < min_group,
            })
    return pd.DataFrame(rows)