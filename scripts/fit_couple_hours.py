"""Exploratory (added after 3b, not pre-registered): couple's paid hours.

Usage:
    python scripts/fit_couple_hours.py

Refits the MI logistic model with a 4-level "couple's paid hours" variable
(woman's share of the couple's paid hours: man works more / roughly equal /
woman works more / neither works for pay; reference = roughly equal) in place
of own and partner paid hours. Cut-offs 0.4/0.6, sensitivity 0.45/0.55; see
definitions.md, "Exploratory".

Main version: without own and partner work status, which the couple's-hours
variable replaces (with them in, "neither works for pay" was unstable). The
version with work status is kept for comparison (column suffix "_ws").

Reads data/processed/sample.csv. Writes:
    results/logit_odds_ratios_couple_hours.csv   MI odds ratios, both cut-off pairs,
                                                 without and with work status
"""

from pathlib import Path

import pandas as pd

from harvest_hunt.model import (build_model_table, couple_paid_hours, fit_mi,
                                impute_once, odds_ratio_table)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "processed" / "sample.csv"
RESULTS = ROOT / "results"
CUTOFFS = {"040_060": (0.4, 0.6), "045_055": (0.45, 0.55)}


def main() -> None:
    table = build_model_table(pd.read_csv(SAMPLE))

    # How many fall in each level (first imputation, weighted share), for context.
    first = impute_once(table, random_state=0)
    for tag, cutoffs in CUTOFFS.items():
        levels = couple_paid_hours(first, cutoffs)
        share = first["weight"].groupby(levels).sum() / first["weight"].sum()
        print(tag, pd.DataFrame({"n": levels.value_counts(), "weighted_share": share})
              .round(3).to_string(), sep="\n", end="\n\n")

    parts = []
    for work_status, suffix in [(False, ""), (True, "_ws")]:
        for tag, cutoffs in CUTOFFS.items():
            ors = odds_ratio_table(fit_mi(table, m=20, hours="couple", cutoffs=cutoffs,
                                          work_status=work_status))
            parts.append(ors.rename(columns=lambda c: c.replace("_mi", f"_{tag}{suffix}")))
    out = pd.concat(parts, axis=1)  # work-status rows are empty for the main version
    out = pd.concat([out[~out.index.str.startswith("country_")],
                     out[out.index.str.startswith("country_")]])
    out.to_csv(RESULTS / "logit_odds_ratios_couple_hours.csv")
    print(out.round(3).to_string())


if __name__ == "__main__":
    main()
