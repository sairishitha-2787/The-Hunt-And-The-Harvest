"""Cleaning and definitions for The Harvest and the Hunt.

Pipeline: raw ISSP rows -> missing codes to NaN -> partnered sample
-> who does each task, from the woman's side -> shared household -> supporter
-> true egalitarian / unshared supporter -> weights normalised per country.
"""

import numpy as np
import pandas as pd

from harvest_hunt import config as C


def to_missing(df: pd.DataFrame, columns, missing_codes) -> pd.DataFrame:
    """Return a copy where ISSP missing codes in `columns` become NaN."""
    out = df.copy()
    for col in columns:
        out[col] = out[col].where(~out[col].isin(missing_codes))
    return out


def task_done_by(answer: pd.Series, respondent_sex: pd.Series,
                 male=C.MALE, female=C.FEMALE) -> pd.Series:
    """Translate "me / partner" answers into who does the task.

    Returns "woman", "man", "equal", "third" or NaN. Assumes a different-sex
    couple: when a man says "usually my partner", the woman does it.
    """
    me = answer.isin([C.ALWAYS_ME, C.USUALLY_ME])
    partner = answer.isin([C.USUALLY_PARTNER, C.ALWAYS_PARTNER])
    is_man = respondent_sex.eq(male)
    is_woman = respondent_sex.eq(female)

    result = pd.Series(np.nan, index=answer.index, dtype="object")
    result[answer.eq(C.EQUAL)] = "equal"
    result[answer.eq(C.THIRD_PERSON)] = "third"
    result[(me & is_woman) | (partner & is_man)] = "woman"
    result[(me & is_man) | (partner & is_woman)] = "man"
    return result


def shared_household(done_by: pd.DataFrame, threshold=C.SHARED_THRESHOLD,
                     min_tasks=C.MIN_TASKS_ANSWERED) -> pd.Series:
    """True if at least `threshold` of couple-done tasks are equal or done by the man.

    Tasks done by a third person (e.g. paid help) are left out of both the top
    and bottom of the share, because they tell us nothing about the couple.
    Fewer than `min_tasks` usable answers -> NaN (not enough information).
    """
    usable = done_by.isin(["woman", "man", "equal"])
    fair = done_by.isin(["man", "equal"])
    n_usable = usable.sum(axis=1)
    share = fair.sum(axis=1) / n_usable.replace(0, np.nan)
    result = (share >= threshold).astype("object")
    result[n_usable < min_tasks] = np.nan
    return result


def woman_hours_share(hours_self: pd.Series, hours_partner: pd.Series,
                      respondent_sex: pd.Series) -> pd.Series:
    """Woman's share of the couple's weekly household-work hours (0 to 1).

    NaN if either value is missing or both are 0.
    """
    total = hours_self + hours_partner
    woman = hours_self.where(respondent_sex.eq(C.FEMALE), hours_partner)
    return woman / total.replace(0, np.nan)


def supporter(item: pd.Series, codes=C.SUPPORTER_CODES) -> pd.Series:
    """True if the answer is one of `codes`; NaN if missing."""
    result = item.isin(codes).astype("object")
    result[item.isna()] = np.nan
    return result


def classify(is_supporter: pd.Series, is_shared: pd.Series) -> pd.Series:
    """Groups among supporters; non-supporters and missing answers get NaN."""
    result = pd.Series(np.nan, index=is_supporter.index, dtype="object")
    result[is_supporter.eq(True) & is_shared.eq(True)] = "true_egalitarian"
    result[is_supporter.eq(True) & is_shared.eq(False)] = "unshared_supporter"
    return result


def zero_hours_if_not_working(hours: pd.Series, work: pd.Series) -> pd.Series:
    """Paid-work hours are "not applicable" for people not in paid work: set them to 0.

    Without this, every non-working person would drop out of the model.
    """
    return hours.where(work.ne(2) & work.ne(3), 0.0)


def normalise_weights(weight: pd.Series, country: pd.Series) -> pd.Series:
    """Scale weights so they average 1 within each country.

    Countries that supplied no weights (all missing) get 1 for everyone.
    Rescaling doesn't change any within-country share; it keeps each
    country's total equal to its sample size when countries are pooled.
    """
    w = weight.astype(float).copy()
    no_weights = w.isna().groupby(country).transform("all")
    w[no_weights] = 1.0
    if w.isna().any() or (w <= 0).any():
        raise ValueError("Weights must be positive in countries that supply them.")
    return w / w.groupby(country).transform("mean")


def build_sample(raw: pd.DataFrame) -> pd.DataFrame:
    """Apply every step to the raw ISSP file, using the names in config."""
    task_cols = list(C.TASKS.values())
    numeric = (task_cols + list(C.COVARIATES.values())
               + [C.SEX, C.PARTNERED, C.SUPPORTER_ITEM, C.HOURS_SELF, C.HOURS_PARTNER])
    df = to_missing(raw, numeric, C.MISSING_CODES)

    df = df[df[C.PARTNERED].isin(C.PARTNERED_YES) & df[C.SEX].isin([C.MALE, C.FEMALE])]
    if C.PARTNER_SEX is not None:
        df = df[df[C.PARTNER_SEX].notna() & df[C.PARTNER_SEX].ne(df[C.SEX])]

    done_by = pd.DataFrame({name: task_done_by(df[col], df[C.SEX])
                            for name, col in C.TASKS.items()})
    out = pd.DataFrame({
        "country": df[C.COUNTRY].astype(str),
        "sex": df[C.SEX].map({C.MALE: "man", C.FEMALE: "woman"}),
        "weight": normalise_weights(df[C.WEIGHT], df[C.COUNTRY]),
    })
    out = out.join(done_by.add_prefix("task_"))
    out["shared"] = shared_household(done_by)
    out["woman_hours_share"] = woman_hours_share(df[C.HOURS_SELF], df[C.HOURS_PARTNER], df[C.SEX])
    out["supporter"] = supporter(df[C.SUPPORTER_ITEM])
    out["group"] = classify(out["supporter"], out["shared"])

    for name, col in C.COVARIATES.items():
        out[name] = df[col]
    out["work_hours"] = zero_hours_if_not_working(out["work_hours"], out["work"])
    out["partner_work_hours"] = zero_hours_if_not_working(out["partner_work_hours"],
                                                          out["partner_work"])
    return out


def sample_flow(raw: pd.DataFrame, sample: pd.DataFrame) -> pd.DataFrame:
    """Respondents per country at each step, for the README and definitions.md."""
    country = raw[C.COUNTRY].astype(str)
    steps = {
        "all_respondents": country,
        "partnered": sample["country"],
        "shared_known": sample.loc[sample["shared"].notna(), "country"],
        "supporter_known": sample.loc[sample["shared"].notna()
                                      & sample["supporter"].notna(), "country"],
        "supporters": sample.loc[sample["group"].notna(), "country"],
    }
    flow = pd.DataFrame({k: v.value_counts() for k, v in steps.items()}).fillna(0).astype(int)
    flow.loc["TOTAL"] = flow.sum()
    return flow
