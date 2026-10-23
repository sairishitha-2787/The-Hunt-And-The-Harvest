"""Compute the say-do gap per country and sex from the cleaned sample.

Usage (after scripts/build_sample.py has made data/processed/sample.csv):
    python scripts/say_do_gap.py

Writes:
    results/say_do_by_country.json   aggregate only (safe to commit)
Prints the men's and women's rankings so you can check them by eye.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from harvest_hunt.gap import MIN_GROUP, say_do_by_country

SAMPLE = Path("data/processed/sample.csv")
OUT = Path("results/say_do_by_country.json")


def to_records(table: pd.DataFrame) -> list[dict]:
    """Round for readability and turn pandas types into plain JSON values."""
    records = []
    for r in table.itertuples(index=False):
        records.append({
            "country": r.country,
            "sex": r.sex,
            "share": round(float(r.share), 4),
            "ci_low": round(float(r.ci_low), 4),
            "ci_high": round(float(r.ci_high), 4),
            "n": int(r.n),
            "n_eff": round(float(r.n_eff), 1),
            "small_group": bool(r.small_group),
            "majority": bool(r.majority),
            "clear_majority": bool(r.clear_majority),
            "rank": None if pd.isna(r.rank) else int(r.rank),
        })
    return records


def main() -> None:
    if not SAMPLE.exists():
        sys.exit(f"{SAMPLE} not found. Run scripts/build_sample.py first.")
    sample = pd.read_csv(SAMPLE)
    table = say_do_by_country(sample)

    OUT.parent.mkdir(exist_ok=True)
    payload = {
        "description": "Share of supporters (disagree with v6) whose household is shared "
                       "(true egalitarians), per country and sex. Weighted; 95% Wilson CIs "
                       "on Kish effective n, assuming simple random sampling within country.",
        "data": "ISSP 2022 ZA10000 v2.0.0",
        "computed": date.today().isoformat(),
        "min_group": MIN_GROUP,
        "rows": to_records(table),
    }
    OUT.write_text(json.dumps(payload, indent=2))

    show = table.assign(share=(table["share"] * 100).round(1),
                        ci=lambda t: ((t["ci_low"] * 100).round(1).astype(str) + "–"
                                      + (t["ci_high"] * 100).round(1).astype(str)))
    cols = ["rank", "country", "share", "ci", "n", "small_group", "clear_majority"]
    for sex in ["man", "woman"]:
        print(f"\n=== {sex.upper()} (share %, 95% CI) ===")
        print(show[show["sex"] == sex][cols].to_string(index=False))
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
