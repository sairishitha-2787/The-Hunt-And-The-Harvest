"""Clean the ISSP 2022 file and report sample sizes per country.

Usage:
    python scripts/build_sample.py data/raw/ZA10000_v2-0-0.dta

Writes:
    data/processed/sample.csv      respondent-level (gitignored: never commit)
    results/sample_flow.csv        counts per country (aggregate, safe to commit)
"""

import sys
from pathlib import Path

import pandas as pd

from harvest_hunt import config as C
from harvest_hunt.clean import build_sample, sample_flow


def main(path: str) -> None:
    cols = ([C.COUNTRY, C.SEX, C.PARTNERED, C.WEIGHT, C.SUPPORTER_ITEM,
             C.HOURS_SELF, C.HOURS_PARTNER]
            + list(C.TASKS.values()) + list(C.COVARIATES.values()))
    raw = pd.read_stata(path, columns=cols, convert_categoricals=False)
    sample = build_sample(raw)
    flow = sample_flow(raw, sample)

    Path("data/processed").mkdir(parents=True, exist_ok=True)
    Path("results").mkdir(exist_ok=True)
    sample.to_csv("data/processed/sample.csv", index=False)
    flow.to_csv("results/sample_flow.csv")
    print(flow.to_string())


if __name__ == "__main__":
    main(sys.argv[1])
