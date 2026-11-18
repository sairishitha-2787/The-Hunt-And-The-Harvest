"""The app export: percentages, small-group suppression, task order."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_app_data.py"
spec = importlib.util.spec_from_file_location("export_app_data", SCRIPT)
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def row(task, men_n=100, women_n=100, small=False, country="AT"):
    return {"country": country, "task": task, "men_say_woman": 0.4567,
            "women_say_woman": 0.71234, "men_n": men_n, "women_n": women_n,
            "small_group": small}


def results(rows):
    return {"data": "ISSP test", "computed": "2026-01-01", "min_group": 50, "rows": rows}


def test_percentages_and_task_order():
    rows = [row(t) for t in reversed(export.TASK_ORDER)]
    out = export.build_country_tasks(results(rows))
    at = out["countries"]["AT"]
    assert at["name"] == "Austria"
    assert list(at["tasks"]) == export.TASK_ORDER
    assert at["tasks"]["laundry"] == {"men_pct": 45.7, "women_pct": 71.2,
                                      "men_n": 100, "women_n": 100}


def test_small_group_is_null_but_keeps_n():
    rows = [row(t) for t in export.TASK_ORDER]
    rows[0] = row("laundry", men_n=49)          # below threshold, even if unflagged
    rows[1] = row("plan_activities", small=True)
    out = export.build_country_tasks(results(rows))
    tasks = out["countries"]["AT"]["tasks"]
    assert tasks["laundry"]["men_pct"] is None and tasks["laundry"]["women_pct"] is None
    assert tasks["laundry"]["men_n"] == 49
    assert tasks["plan_activities"]["men_pct"] is None
    assert tasks["care_sick"]["men_pct"] == 45.7


def test_missing_task_raises():
    with pytest.raises(ValueError):
        export.build_country_tasks(results([row("laundry")]))
