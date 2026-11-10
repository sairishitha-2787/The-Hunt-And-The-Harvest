"""Logistic vs gradient boosting: cross-validated fit, calibration and SHAP.

Usage:
    python scripts/compare_models.py

Reads data/processed/sample.csv (from build_sample.py) and
results/logit_odds_ratios.csv (from fit_logit.py). Writes:
    results/model_comparison.csv        weighted AUC and Brier (mean, SD), calibration
    results/cv_folds.csv                AUC and Brier per model and fold
    results/shap_importance.csv         mean |SHAP| per feature, countries grouped
    results/importance_comparison.csv   SHAP ranking vs logistic rankings
    results/shap_dependence.csv         binned SHAP for age and paid-hours share
    results/figures/calibration.png
    results/figures/shap_importance.png
    results/figures/shap_dependence_age.png
    results/figures/shap_dependence_hours_share.png

Both models use the same features, survey weights and folds. "boosting" uses
native categorical country and education; "boosting_onehot" is the same model
with one-hot countries, which is the one SHAP explains (TreeExplainer is exact
only for it). All SHAP values and contributions are on the log-odds scale.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files only; no window needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from harvest_hunt.model import (OUTCOME, boost_shap, build_model_table,
                                calibration_slope_intercept, cross_validate,
                                logit_contributions, own_paid_share, reliability_curve,
                                summarise_cv, weighted_mean_abs, feature_of)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "processed" / "sample.csv"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
ODDS_RATIOS = RESULTS / "logit_odds_ratios.csv"

COLOURS = {"logistic": "#d95f02", "boosting": "#1f5f99", "boosting_onehot": "#7fa7cc"}
LABELS = {"logistic": "Logistic (imputed in fold)", "boosting": "Gradient boosting",
          "boosting_onehot": "Boosting, one-hot countries"}


def tidy(ax):
    ax.grid(color="#e5e5e5", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def plot_calibration(oof: pd.DataFrame, models) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "--", color="black", linewidth=1, label="Perfect calibration")
    for name in models:
        curve = reliability_curve(oof[OUTCOME], oof[name], oof["weight"], bins=10)
        ax.plot(curve["predicted"], curve["observed"], "o-", color=COLOURS[name],
                label=LABELS[name])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Predicted probability (out of fold, 10 equal-size bins)")
    ax.set_ylabel("Observed share of true egalitarians (weighted)")
    ax.set_title("Calibration, 5-fold cross-validation")
    ax.legend(frameon=False, loc="upper left")
    tidy(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "calibration.png", dpi=150)
    plt.close(fig)


def plot_importance(importance: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    order = importance.sort_values()
    ax.barh(order.index, order.values, color=COLOURS["boosting"])
    ax.set_xlabel("Mean |SHAP value| (log-odds, survey-weighted)")
    ax.set_title("What drives the boosting model's predictions\n(32 countries grouped into one bar)")
    tidy(ax)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(FIGURES / "shap_importance.png", dpi=150)
    plt.close(fig)


def binned(x: pd.Series, values: pd.Series, weights: pd.Series, edges) -> pd.DataFrame:
    """Weighted mean of `values` within bins of x, labelled by bin midpoint."""
    bins = pd.cut(x, edges, include_lowest=True)
    d = pd.DataFrame({"v": values, "w": weights, "bin": bins}).dropna()
    rows = [{"x": interval.mid, "mean": np.average(g["v"], weights=g["w"]), "n": len(g)}
            for interval, g in d.groupby("bin", observed=True)]
    return pd.DataFrame(rows)


def plot_dependence(x, shap_values, logit_values, weights, edges, xlabel, title, path):
    """SHAP cloud plus binned means for boosting and for the logistic model."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    jitter = np.random.default_rng(0).uniform(-0.3, 0.3, len(x)) * (edges[1] - edges[0]) * 0.2
    ax.scatter(x + jitter, shap_values, s=3, alpha=0.08, color=COLOURS["boosting"],
               rasterized=True)
    b = binned(x, shap_values, weights, edges)
    lg = binned(x, logit_values, weights, edges)
    ax.plot(b["x"], b["mean"], "o-", color=COLOURS["boosting"], label="Boosting (SHAP, binned mean)")
    ax.plot(lg["x"], lg["mean"], "s--", color=COLOURS["logistic"],
            label="Logistic (its contribution, binned mean)")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Effect on log-odds of being a true egalitarian")
    ax.set_title(title)
    ax.legend(frameon=False)
    tidy(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return b.assign(model="boosting"), lg.assign(model="logistic")


def importance_comparison(shap_imp: pd.Series, logit_imp: pd.Series) -> pd.DataFrame:
    """SHAP rank vs two logistic rankings: by contribution and by largest |log OR|."""
    ors = pd.read_csv(ODDS_RATIOS, index_col=0)
    log_or = np.log(ors["or_mi"]).abs()
    largest = log_or.groupby(log_or.index.map(feature_of)).max()
    out = pd.DataFrame({
        "shap_mean_abs": shap_imp,
        "shap_rank": shap_imp.rank(ascending=False).astype(int),
        "logit_contrib_mean_abs": logit_imp,
        "logit_contrib_rank": logit_imp.rank(ascending=False).astype(int),
        "largest_abs_log_or": largest,
        "or_rank": largest.rank(ascending=False).astype(int),
    })
    out.index.name = "feature"
    return out.sort_values("shap_rank")


def main() -> None:
    table = build_model_table(pd.read_csv(SAMPLE))
    FIGURES.mkdir(parents=True, exist_ok=True)

    # 1. Cross-validation
    oof, folds = cross_validate(table)
    folds.to_csv(RESULTS / "cv_folds.csv", index=False)
    summary = summarise_cv(folds)
    summary.columns = [f"{a}_{b}" for a, b in summary.columns]

    # 2. Calibration
    models = list(summary.index)
    calib = pd.DataFrame({m: calibration_slope_intercept(oof[OUTCOME], oof[m], oof["weight"])
                          for m in models}).T.add_prefix("calibration_")
    comparison = summary.join(calib)
    comparison.index.name = "model"
    comparison.to_csv(RESULTS / "model_comparison.csv")
    plot_calibration(oof, ["logistic", "boosting"])
    print(folds.round(4).to_string(index=False), "\n")
    print(comparison.round(4).to_string(), "\n")

    # 3. SHAP and the logistic model's own contributions
    shap_values = boost_shap(table)
    logit_values = logit_contributions(table)
    w = table["weight"]
    shap_imp = weighted_mean_abs(shap_values, w)
    shap_imp.rename("mean_abs_shap").rename_axis("feature").to_csv(RESULTS / "shap_importance.csv")
    plot_importance(shap_imp)
    ranks = importance_comparison(shap_imp, weighted_mean_abs(logit_values, w))
    ranks.to_csv(RESULTS / "importance_comparison.csv")
    print(ranks.round(4).to_string(), "\n")

    age = table["age"]
    age_parts = plot_dependence(
        age, shap_values["age"], logit_values["age"], w, np.arange(15, 95, 5),
        "Age", "Age: boosting vs the logistic model's straight line",
        FIGURES / "shap_dependence_age.png")

    share = own_paid_share(table["work_hours"], table["partner_work_hours"])
    hours_shap = shap_values["work_hours"] + shap_values["partner_work_hours"]
    hours_logit = logit_values["work_hours"] + logit_values["partner_work_hours"]
    known = share.notna()
    share_parts = plot_dependence(
        share[known], hours_shap[known], hours_logit[known], w[known],
        np.linspace(0, 1, 11),
        "Own share of the couple's paid-work hours (0.5 if neither works for pay)",
        "Paid hours: combined effect of own and partner's hours",
        FIGURES / "shap_dependence_hours_share.png")
    dependence = pd.concat([p.assign(feature=f) for f, parts in
                            [("age", age_parts), ("paid_hours_share", share_parts)]
                            for p in parts])
    dependence.to_csv(RESULTS / "shap_dependence.csv", index=False)
    print(dependence.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
