"""Session 3c: do the say-do results hold under other definitions?

Usage:
    python scripts/sensitivity.py            # shares, verdicts and model check
    python scripts/sensitivity.py --no-model # shares and verdicts only (fast)

Reads data/processed/sample.csv. Writes (aggregate only):
    results/sensitivity_by_country.csv   share of supporters who are true egalitarians,
                                         per variant, country and sex, 95% Wilson CIs
    results/sensitivity_summary.csv      per variant and sex: sample size, countries with
                                         a clear majority / clear minority / unclear
    results/sensitivity_model.csv        couple's-hours MI logit (m = 5) under the main
                                         definition and outcome variants a and b

The main definition in definitions.md stays the reference; see
harvest_hunt.sensitivity for what each variant changes.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from harvest_hunt.gap import say_do_by_country
from harvest_hunt.model import build_model_table, fit_mi, odds_ratio_table
from harvest_hunt.sensitivity import VARIANTS, sample_sizes, variant_sample, verdict_counts

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "processed" / "sample.csv"
RESULTS = ROOT / "results"
MODEL_VARIANTS = ["main", "threshold_40", "threshold_60", "hours_40_60"]
MODEL_TERMS = ["woman", "age_10y", "educ_tertiary", "any_child", "couple_man_more"]


def main(run_model: bool = True) -> None:
    sample = pd.read_csv(SAMPLE)

    by_country, summary = [], []
    for variant in VARIANTS:
        vs = variant_sample(sample, variant)
        table = say_do_by_country(vs)
        by_country.append(table.assign(variant=variant))
        counts = verdict_counts(table)
        sizes = sample_sizes(vs)
        for sex in ["man", "woman"]:
            ranked = table[(table["sex"] == sex) & ~table["small_group"]]
            summary.append({"variant": variant, "sex": sex, "n_supporters": sizes[sex],
                            **counts.loc[sex].to_dict(),
                            "median_share": ranked["share"].median()})
    by_country = pd.concat(by_country)
    cols = ["variant", "country", "sex", "share", "ci_low", "ci_high", "n", "n_eff",
            "small_group", "clear_majority", "rank"]
    by_country[cols].to_csv(RESULTS / "sensitivity_by_country.csv", index=False)
    summary = pd.DataFrame(summary)
    summary.to_csv(RESULTS / "sensitivity_summary.csv", index=False)
    print(summary.round(3).to_string(index=False), "\n")

    if not run_model:
        return
    rows = []
    for variant in MODEL_VARIANTS:
        table = build_model_table(variant_sample(sample, variant))
        ors = odds_ratio_table(fit_mi(table, m=5, hours="couple", work_status=False))
        for term in MODEL_TERMS:
            r = ors.loc[term]
            rows.append({"variant": variant, "term": term, "n": len(table),
                         "or": r["or_mi"], "ci_low": r["ci_low_mi"],
                         "ci_high": r["ci_high_mi"], "p": r["p_mi"]})
    model = pd.DataFrame(rows)
    model.to_csv(RESULTS / "sensitivity_model.csv", index=False)
    print(model.round(3).to_string(index=False))


if __name__ == "__main__":
    main(run_model="--no-model" not in sys.argv)
