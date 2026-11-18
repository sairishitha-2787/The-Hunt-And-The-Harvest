"""Export per-country, per-task figures for the household tool in app/.

Usage (after scripts/say_do_gap.py has made results/perception_gap.json):
    python scripts/export_app_data.py

Reads only results/perception_gap.json (aggregate results). Never reads data/.

Writes:
    app/data/country_tasks.json   aggregate only (safe to commit)

For each country and each of the 6 ISSP tasks: the weighted % of partnered men
and of partnered women saying the woman always or usually does it (third-person
answers excluded), plus the unweighted n per group. Rows flagged small_group in
Session 2 (fewer than MIN_GROUP respondents of one sex) get null percentages;
their n is kept so the app can say why.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "perception_gap.json"
OUT = ROOT / "app" / "data" / "country_tasks.json"

# Same order as definitions.md (v39-v44).
TASK_ORDER = ["laundry", "plan_activities", "care_sick", "groceries", "cleaning", "meals"]

COUNTRY_NAMES = {
    "AT": "Austria", "AU": "Australia", "BG": "Bulgaria", "CH": "Switzerland",
    "CZ": "Czechia", "DE": "Germany", "DK": "Denmark", "ES": "Spain",
    "FI": "Finland", "FR": "France", "GR": "Greece", "HR": "Croatia",
    "HU": "Hungary", "IL": "Israel", "IN": "India", "IS": "Iceland",
    "IT": "Italy", "JP": "Japan", "LT": "Lithuania", "NL": "Netherlands",
    "NO": "Norway", "NZ": "New Zealand", "PH": "Philippines", "PL": "Poland",
    "RU": "Russia", "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia",
    "TH": "Thailand", "TW": "Taiwan", "US": "United States", "ZA": "South Africa",
}


def pct(share: float) -> float:
    """Share (0-1) -> percent with one decimal."""
    return round(share * 100, 1)


def build_country_tasks(results: dict) -> dict:
    """Turn perception_gap.json into the app's per-country lookup."""
    min_group = results["min_group"]
    countries: dict[str, dict] = {}
    for r in results["rows"]:
        code = r["country"]
        if code not in COUNTRY_NAMES:
            raise KeyError(f"No display name for country code {code!r}")
        if r["task"] not in TASK_ORDER:
            raise KeyError(f"Unknown task {r['task']!r}")
        # Session 2's rule, unchanged: flagged if either sex has fewer than min_group.
        small = bool(r["small_group"]) or min(r["men_n"], r["women_n"]) < min_group
        entry = countries.setdefault(code, {"name": COUNTRY_NAMES[code], "tasks": {}})
        entry["tasks"][r["task"]] = {
            "men_pct": None if small else pct(r["men_say_woman"]),
            "women_pct": None if small else pct(r["women_say_woman"]),
            "men_n": int(r["men_n"]),
            "women_n": int(r["women_n"]),
        }
    for code, entry in countries.items():
        missing = set(TASK_ORDER) - set(entry["tasks"])
        if missing:
            raise ValueError(f"{code} is missing tasks: {sorted(missing)}")
        entry["tasks"] = {t: entry["tasks"][t] for t in TASK_ORDER}
    return {
        "description": (
            "Per country and ISSP task: weighted % of partnered men and of partnered "
            "women saying the woman always or usually does it (third-person answers "
            "excluded). n is unweighted. Percentages are null where either sex has "
            f"fewer than {min_group} respondents. Men and women come from different "
            "households: a comparison of reports, not of couples."
        ),
        "source": results["data"],
        "computed": results["computed"],
        "min_group": min_group,
        "tasks": TASK_ORDER,
        "countries": dict(sorted(countries.items(), key=lambda kv: kv[1]["name"])),
    }


def main() -> None:
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    out = build_country_tasks(results)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    nulls = sum(t["men_pct"] is None for c in out["countries"].values() for t in c["tasks"].values())
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(out['countries'])} countries x "
          f"{len(out['tasks'])} tasks, {nulls} suppressed (n < {out['min_group']}).")


if __name__ == "__main__":
    main()
