"""Sensitivity variants for Session 3c.

The main definition (definitions.md) stays the reference. Each variant changes
one thing and rebuilds the "group" column, so the Session 2 code
(gap.say_do_by_country) and the model table run on it unchanged:

    threshold_40, threshold_60  shared if at least 40% / 60% of couple-done tasks
                                are equal or done by the man (main: 50%)
    hours_40_60                 shared if the woman's share of the couple's
                                household-work hours (v34, v36) is 40-60%
    supporter_v20               supporter = mother and father should provide equally
    supporter_v10               supporter = woman should work full- or part-time
                                when the youngest child is at school
"""

import numpy as np
import pandas as pd

from harvest_hunt import config as C
from harvest_hunt.clean import classify, shared_household

VARIANTS = ["main", "threshold_40", "threshold_60", "hours_40_60",
            "supporter_v20", "supporter_v10"]
TASK_COLUMNS = ["task_" + t for t in C.TASKS]


def hours_shared(woman_share: pd.Series, low: float = 0.4, high: float = 0.6) -> pd.Series:
    """True if the woman does between `low` and `high` of the couple's housework hours.

    Both ends inclusive. Outside the band (including when the man does more
    than 60%) -> False. Missing share (either hours missing, or both 0) -> NaN.
    """
    result = woman_share.between(low, high).astype("object")
    result[woman_share.isna()] = np.nan
    return result


def variant_sample(sample: pd.DataFrame, variant: str) -> pd.DataFrame:
    """The cleaned sample with "shared", "supporter" and "group" set by `variant`."""
    out = sample.copy()
    if variant == "main":
        pass
    elif variant in ("threshold_40", "threshold_60"):
        threshold = int(variant[-2:]) / 100
        out["shared"] = shared_household(sample[TASK_COLUMNS], threshold=threshold)
    elif variant == "hours_40_60":
        out["shared"] = hours_shared(sample["woman_hours_share"])
    elif variant in ("supporter_v20", "supporter_v10"):
        out["supporter"] = sample[variant]
    else:
        raise ValueError(f"Unknown variant {variant!r}; choose from {VARIANTS}")
    out["group"] = classify(out["supporter"], out["shared"])
    return out


def sample_sizes(sample: pd.DataFrame) -> pd.Series:
    """Supporters with a known group, by sex and in total."""
    sup = sample[sample["group"].notna()]
    sizes = sup["sex"].value_counts().reindex(["man", "woman"], fill_value=0)
    sizes["total"] = len(sup)
    return sizes


def verdict_counts(table: pd.DataFrame) -> pd.DataFrame:
    """Countries per sex: clear majority, clear minority or unclear.

    clear majority: whole 95% CI above 50%; clear minority: whole CI below 50%;
    unclear: the CI includes 50%. Small groups are counted separately and left
    out of the three verdicts.
    """
    t = table.copy()
    t["verdict"] = "unclear"
    t.loc[t["ci_low"] > 0.5, "verdict"] = "clear_majority"
    t.loc[t["ci_high"] < 0.5, "verdict"] = "clear_minority"
    t.loc[t["small_group"], "verdict"] = "small_group"
    counts = (t.groupby("sex")["verdict"].value_counts().unstack(fill_value=0)
               .reindex(columns=["clear_majority", "clear_minority", "unclear", "small_group"],
                        fill_value=0))
    counts["ranked"] = counts[["clear_majority", "clear_minority", "unclear"]].sum(axis=1)
    return counts
