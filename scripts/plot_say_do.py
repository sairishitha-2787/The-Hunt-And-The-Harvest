"""Plot the say-do gap: ranked dot-and-CI chart, men and women side by side.

Usage (after scripts/say_do_gap.py has made results/say_do_by_country.json):
    python scripts/plot_say_do.py

Writes:
    results/figures/say_do_ranked.png
Each panel is ranked by its own share; sexes are never pooled. Groups below the
minimum size are left out of the ranking and listed in a footnote.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files only; no window needed
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

# Paths are relative to the repo root, so the script works from any folder.
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "say_do_by_country.json"
OUT = ROOT / "results" / "figures" / "say_do_ranked.png"

TITLE = "Among people who reject 'man earns, woman keeps house', how many actually share housework?"
PANELS = [("man", "Men"), ("woman", "Women")]
STRONG = "#1f5f99"  # clear majority: CI lower bound above 50%
MUTED = "#a6a6a6"   # everything else


def draw_panel(ax, rows, label):
    """Dot at the share, horizontal 95% CI bar, highest share at the top."""
    rows = sorted(rows, key=lambda r: r["share"])  # ascending, so the top row is the highest
    for y, r in enumerate(rows):
        colour = STRONG if r["clear_majority"] else MUTED
        ax.hlines(y, r["ci_low"], r["ci_high"], color=colour, linewidth=2)
        ax.plot(r["share"], y, "o", color=colour, markersize=6)
    ax.axvline(0.5, color="black", linestyle="--", linewidth=1)
    ax.set_yticks(range(len(rows)), [r["country"] for r in rows])
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1))
    ax.set_xlabel("Share of supporters whose household shares housework")
    ax.set_title(f"{label} ({len(rows)} countries ranked)")
    ax.grid(axis="x", color="#e5e5e5", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def main() -> None:
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    rows = results["rows"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 9))
    for ax, (sex, label) in zip(axes, PANELS):
        draw_panel(ax, [r for r in rows if r["sex"] == sex and not r["small_group"]], label)

    small = [r for r in rows if r["small_group"]]
    footnote = (
        "Dot = weighted share; bar = 95% Wilson CI (Kish effective n). "
        "Blue = clear majority (CI entirely above 50%); grey = not.\n"
        f"Not ranked (fewer than {results['min_group']} supporters): "
        + ", ".join(f"{r['country']} {'men' if r['sex'] == 'man' else 'women'} (n = {r['n']})" for r in small)
        + f".\nSource: {results['data']}. Each panel ranked separately; sexes not pooled."
    )
    fig.suptitle(TITLE, fontsize=13, fontweight="bold")
    fig.text(0.01, 0.01, footnote, fontsize=8.5, color="#444444", va="bottom")
    fig.tight_layout(rect=(0, 0.07, 1, 0.96))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200)
    print(f"Saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
