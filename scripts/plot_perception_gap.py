"""Plot the perception gap: dumbbell chart of men's vs women's reports per task.

Usage (after the perception gap script has made results/perception_gap.json):
    python scripts/plot_perception_gap.py

Writes:
    results/figures/perception_gap.png
For each task, the share saying "the woman does it" as reported by men and by
women, averaged across countries (unweighted mean of country values). Rows are
sorted by gap, biggest at the top. The 6 averages are also printed.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files only; no window needed
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

# Paths are relative to the repo root, so the script works from any folder.
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "perception_gap.json"
OUT = ROOT / "results" / "figures" / "perception_gap.png"

TITLE = "For every task, women are more likely than men to say the woman does it"
NOTE = "Men and women are different households: this is a difference in reports, not proof partners disagree."
TASK_LABELS = {
    "laundry": "Laundry",
    "plan_activities": "Planning family activities",
    "care_sick": "Caring for sick family members",
    "cleaning": "Cleaning",
    "groceries": "Grocery shopping",
    "meals": "Preparing meals",
}
MEN = "#2a78d6"    # categorical slot 1
WOMEN = "#eb6834"  # categorical slot 2
LINE = "#c3c2b7"   # connector, recessive


def task_means(rows):
    """Unweighted mean across countries of each sex's share, per task."""
    out = {}
    for task in sorted({r["task"] for r in rows}):
        group = [r for r in rows if r["task"] == task]
        men = sum(r["men_say_woman"] for r in group) / len(group)
        women = sum(r["women_say_woman"] for r in group) / len(group)
        out[task] = {"men": men, "women": women, "gap": women - men, "countries": len(group)}
    return out


def main() -> None:
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    rows = [r for r in results["rows"] if not r["small_group"]]
    means = task_means(rows)
    n_countries = len({r["country"] for r in rows})

    order = sorted(means, key=lambda t: means[t]["gap"])  # ascending, so the top row is the biggest gap
    fig, ax = plt.subplots(figsize=(10, 5.2))
    for y, task in enumerate(order):
        m = means[task]
        ax.hlines(y, m["men"], m["women"], color=LINE, linewidth=2, zorder=1)
        ax.plot(m["men"], y, "o", color=MEN, markersize=9, markeredgecolor="white", markeredgewidth=1.5, zorder=2)
        ax.plot(m["women"], y, "o", color=WOMEN, markersize=9, markeredgecolor="white", markeredgewidth=1.5, zorder=2)
        right = max(m["men"], m["women"])
        ax.text(right + 0.02, y, f"{m['gap'] * 100:+.1f} pts", va="center", fontsize=10, color="#333333")

    # Direct labels on the top row, so identity is not colour alone.
    top = means[order[-1]]
    ax.text(top["men"], len(order) - 1 + 0.32, "Men", ha="center", fontsize=9, color="#333333")
    ax.text(top["women"], len(order) - 1 + 0.32, "Women", ha="center", fontsize=9, color="#333333")

    ax.set_yticks(range(len(order)), [TASK_LABELS.get(t, t) for t in order])
    ax.set_ylim(-0.6, len(order) - 0.2)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1))
    ax.set_xlabel(f"Share saying the woman does it (unweighted mean of {n_countries} countries)")
    ax.grid(axis="x", color="#e5e5e5", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(
        handles=[
            plt.Line2D([], [], marker="o", linestyle="", color=MEN, markersize=8, label="Reported by men"),
            plt.Line2D([], [], marker="o", linestyle="", color=WOMEN, markersize=8, label="Reported by women"),
        ],
        loc="upper right", frameon=False, fontsize=9,
    )

    fig.suptitle(TITLE, fontsize=13, fontweight="bold")
    footnote = (
        f"{NOTE}\nGap = women's share - men's share, in percentage points. "
        f"Partnered respondents. Source: {results['data']}."
    )
    fig.text(0.01, 0.01, footnote, fontsize=8.5, color="#444444", va="bottom")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200)

    print(f"Task averages across {n_countries} countries (unweighted), biggest gap first:")
    print(f"  {'task':<32}{'men':>7}{'women':>8}{'gap':>9}")
    for task in reversed(order):
        m = means[task]
        print(f"  {TASK_LABELS.get(task, task):<32}{m['men']:>7.1%}{m['women']:>8.1%}{m['gap'] * 100:>+7.1f} pts")
    print(f"Saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
