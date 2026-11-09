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

# Paths are relative to the repo root, so the script works from any folder
# (including VS Code's Run button, which may start in another directory).
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"


def main(path: str) -> None:
    cols = ([C.COUNTRY, C.SEX, C.PARTNERED, C.WEIGHT, C.SUPPORTER_ITEM,
             C.HOURS_SELF, C.HOURS_PARTNER]
            + list(C.TASKS.values()) + list(C.COVARIATES.values()))
    raw = pd.read_stata(path, columns=cols, convert_categoricals=False)
    sample = build_sample(raw)
    flow = sample_flow(raw, sample)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    sample.to_csv(PROCESSED / "sample.csv", index=False)
    flow.to_csv(RESULTS / "sample_flow.csv")
    print(flow.to_string())


if __name__ == "__main__":
    main(sys.argv[1])
