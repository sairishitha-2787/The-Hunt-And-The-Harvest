"""Compute the say-do gap and the perception gap from the cleaned sample.

Usage (after scripts/build_sample.py has made data/processed/sample.csv):
    python scripts/say_do_gap.py

Writes:
    results/say_do_by_country.json   aggregate only (safe to commit)
    results/perception_gap.json      aggregate only (safe to commit)
Prints the rankings and a perception-gap summary so you can check them by eye.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from harvest_hunt.gap import MIN_GROUP, perception_gap, say_do_by_country

# Paths are relative to the repo root, so the script works from any folder
# (including VS Code's Run button, which may start in another directory).
ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "processed" / "sample.csv"
OUT = ROOT / "results" / "say_do_by_country.json"
OUT_PERCEPTION = ROOT / "results" / "perception_gap.json"


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
        sys.exit(f"{SAMPLE} not found. Run scripts/build_sample.py <path to .dta> "
                 "from the repo root first.")
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

    perc = perception_gap(sample)
    rounded = perc.copy()
    num = rounded.select_dtypes("float").columns
    rounded[num] = rounded[num].round(4)
    OUT_PERCEPTION.write_text(json.dumps({
        "description": "Per country and task, weighted share of partnered respondents saying "
                       "the woman does the task (third-person tasks excluded), reported by men "
                       "vs by women. gap = women's share - men's share; 95% CI by Newcombe's "
                       "method from Wilson intervals on Kish effective n. Different households: "
                       "a country-level comparison of reports, not within-couple disagreement.",
        "data": "ISSP 2022 ZA10000 v2.0.0",
        "computed": date.today().isoformat(),
        "min_group": MIN_GROUP,
        "rows": json.loads(rounded.to_json(orient="records")),
    }, indent=2))

    by_task = (perc.groupby("task")[["men_say_woman", "women_say_woman", "gap"]]
                   .mean().mul(100).round(1).sort_values("gap", ascending=False))
    print("\n=== PERCEPTION GAP: average over countries, % saying the woman does it ===")
    print(by_task.to_string())
    by_country = (perc.groupby("country")
                      .agg(gap=("gap", "mean"),
                           tasks_gap_clear=("gap_ci_low", lambda s: int((s > 0).sum())))
                      .assign(gap=lambda t: (t["gap"] * 100).round(1))
                      .sort_values("gap", ascending=False))
    print("\n=== PERCEPTION GAP by country (mean gap in points; tasks where CI > 0, of 6) ===")
    print(by_country.to_string())
    print(f"\nSaved {OUT_PERCEPTION}")


if __name__ == "__main__":
    main()