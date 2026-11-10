"""Who among supporters is a true egalitarian? Weighted logit, MI and complete-case.

Usage:
    python scripts/fit_logit.py

Reads data/processed/sample.csv (from build_sample.py). Writes:
    results/logit_odds_ratios.csv               odds ratios with 95% CIs, MI and complete-case
    results/logit_odds_ratios_hours_share.csv   MI, own share of paid hours instead of hours

Country odds ratios are against the average country (effect coding).
"""

from pathlib import Path

import pandas as pd

from harvest_hunt.model import (build_model_table, complete_case, fit_mi, missingness,
                                odds_ratio_table)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "processed" / "sample.csv"
RESULTS = ROOT / "results"
EXPECTED_ROWS = 16_300  # supporters with a known status, definitions.md


def main() -> None:
    table = build_model_table(pd.read_csv(SAMPLE))
    if len(table) != EXPECTED_ROWS:
        raise SystemExit(f"Expected {EXPECTED_ROWS} supporters, got {len(table)}.")
    print(missingness(table).round(4).to_string(), "\n")

    ors = odds_ratio_table(fit_mi(table, m=20), complete_case(table))
    RESULTS.mkdir(exist_ok=True)
    ors.to_csv(RESULTS / "logit_odds_ratios.csv")
    print(ors.round(3).to_string(), "\n")

    # Robustness: own share of the couple's paid hours instead of absolute hours.
    share = odds_ratio_table(fit_mi(table, m=20, hours="share"))
    share.to_csv(RESULTS / "logit_odds_ratios_hours_share.csv")
    print(share.round(3).to_string())


if __name__ == "__main__":
    main()
