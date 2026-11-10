import re

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from scipy import stats

from harvest_hunt import clean, model
from harvest_hunt import config as C

M, F = C.MALE, C.FEMALE


def synthetic_raw() -> pd.DataFrame:
    """Six raw ISSP rows covering each path into or out of the model table.

    Tasks per row (v39-v44), from the respondent's side:
      0 man, supporter, 3 of 6 equal -> shared         -> true egalitarian (1)
      1 woman, supporter, all "always me" -> not shared -> unshared supporter (0)
      2 woman, not a supporter (v6 = 3), shared        -> excluded
      3 man, supporter, only 2 usable tasks            -> shared missing, excluded
      4 woman, supporter, partner lives elsewhere      -> excluded
      5 woman, supporter, partner does all tasks       -> true egalitarian (1)
    """
    tasks = [
        [3, 3, 3, 4, 4, 4],
        [1, 1, 1, 1, 1, 1],
        [3, 3, 3, 3, 3, 3],
        [3, 4, -8, -8, -9, 6],
        [3, 3, 3, 3, 3, 3],
        [5, 5, 5, 5, 5, 5],
    ]
    raw = pd.DataFrame(tasks, columns=list(C.TASKS.values()))
    raw[C.COUNTRY] = ["AT", "AT", "AT", "DE", "DE", "DE"]
    raw[C.SEX] = [M, F, F, M, F, F]
    raw[C.PARTNERED] = [1, 1, 1, 1, 2, 1]
    raw[C.WEIGHT] = [1.0, 2.0, 1.0, 1.0, 1.0, 3.0]
    raw[C.SUPPORTER_ITEM] = [5, 4, 3, 4, 5, 4]
    raw["v20"] = [3, 3, 3, 1, 3, 2]
    raw["v10"] = [1, 2, 3, 1, 1, 4]
    raw[C.HOURS_SELF] = [10, 20, 10, 5, 10, 2]
    raw[C.HOURS_PARTNER] = [10, 2, 10, 5, 10, 20]
    cov = C.COVARIATES
    raw[cov["age"]] = [40, 35, 50, 60, 30, -9]
    raw[cov["educ"]] = [3, 6, 2, 5, 4, 7]
    raw[cov["work"]] = [1, 2, 1, 1, 1, 1]
    raw[cov["partner_work"]] = [1, 1, 3, 1, 1, 2]
    raw[cov["work_hours"]] = [40, -4, 38, 45, 20, 30]
    raw[cov["partner_work_hours"]] = [40, 50, -4, 40, 40, -4]
    raw[cov["kids_school"]] = [1, 0, 0, 2, 0, 1]
    raw[cov["kids_under_school"]] = [0, 1, 0, 0, 0, -9]
    # Row 5: kids items unknown, but 3 persons and 2 adults -> a child lives there.
    raw[cov["household_size"]] = [3, 3, 2, 4, 2, 3]
    raw[cov["adults"]] = [2, 2, 2, 2, 2, 2]
    raw[cov["fair_share"]] = [3, 1, 3, 3, 3, 5]
    return raw


def table() -> pd.DataFrame:
    return model.build_model_table(clean.build_sample(synthetic_raw()))


def test_table_shape():
    t = table()
    # Only rows 0, 1 and 5 are supporters with a known shared status.
    assert t.shape == (3, len(model.FEATURES) + 2)
    assert list(t.columns) == ["true_egalitarian", "weight", *model.FEATURES]


def test_outcome_matches_definition():
    # Recompute "supporter and shared" by hand from the raw answers.
    t = table()
    assert t["true_egalitarian"].tolist() == [1, 0, 1]
    assert set(t["true_egalitarian"].unique()) <= {0, 1}


def test_outcome_follows_group_column():
    sample = clean.build_sample(synthetic_raw())
    t = model.build_model_table(sample)
    expected = sample.loc[t.index, "group"].eq("true_egalitarian").astype(int)
    pd.testing.assert_series_equal(t["true_egalitarian"], expected, check_names=False)


def test_no_leakage_in_features():
    # Household-work hours (v34, v36) and the task items (v39-v44) define the
    # outcome. Neither they nor anything derived from them may be a feature.
    forbidden_raw = {"v34", "v36", *(f"v{i}" for i in range(39, 45))}
    assert forbidden_raw <= set(model.LEAKAGE_RAW)
    sources = {v for vs in model.FEATURE_SOURCES.values() for v in vs}
    assert not sources & forbidden_raw
    assert not set(model.FEATURES) & forbidden_raw
    assert not set(model.FEATURES) & set(model.LEAKAGE_COLUMNS)
    assert not any(re.match(r"task_", f) for f in model.FEATURES)


def test_no_leakage_columns_in_table():
    t = table()
    assert not set(t.columns) & set(model.LEAKAGE_COLUMNS)
    assert not set(t.columns) & set(model.LEAKAGE_RAW)


def test_work_status_and_hours_coding():
    t = table()
    # Row 1: woman not in paid work -> in_work 0 and 0 hours, not missing.
    assert t.loc[1, "in_work"] == 0 and t.loc[1, "work_hours"] == 0
    # Row 5: partner not in paid work -> partner hours 0.
    assert t.loc[5, "partner_in_work"] == 0 and t.loc[5, "partner_work_hours"] == 0
    assert t.loc[0, "woman"] == 0 and t.loc[1, "woman"] == 1


def test_missing_features_stay_missing_and_are_counted():
    t = table()
    assert np.isnan(t.loc[5, "age"])
    assert t["any_child"].tolist() == [1, 1, 1]  # row 5 from household size
    miss = model.missingness(t)
    assert miss.loc["age", "missing"] == 1
    assert miss.loc["any_feature", "missing"] == 1  # only row 5 is incomplete


# --- Rubin's rules ---------------------------------------------------------------

def test_rubin_hand_checked():
    # m = 3 estimates 1, 2, 3, each with variance 0.5.
    # mean = 2; W = 0.5; B = 1; T = 0.5 + (4/3)(1) = 11/6
    # df = 2 (1 + 0.5 / (4/3))^2 = 2 (1.375)^2 = 3.78125
    est = pd.DataFrame({"b": [1.0, 2.0, 3.0]})
    var = pd.DataFrame({"b": [0.5, 0.5, 0.5]})
    out = model.pool_rubin(est, var).loc["b"]
    assert out["estimate"] == pytest.approx(2.0)
    assert out["se"] == pytest.approx((11 / 6) ** 0.5)
    assert out["df"] == pytest.approx(3.78125)
    half = stats.t.ppf(0.975, 3.78125) * (11 / 6) ** 0.5
    assert out["ci_low"] == pytest.approx(2.0 - half)
    assert out["ci_high"] == pytest.approx(2.0 + half)


def test_rubin_identical_imputations_reduce_to_one_fit():
    # No between-imputation spread: the pooled result is the single fit, normal CI.
    est = pd.DataFrame({"b": [0.7] * 5})
    var = pd.DataFrame({"b": [0.04] * 5})
    out = model.pool_rubin(est, var).loc["b"]
    assert out["se"] == pytest.approx(0.2)
    assert np.isinf(out["df"])
    assert out["ci_low"] == pytest.approx(0.7 - 1.959964 * 0.2, abs=1e-6)
    assert out["fmi"] == 0


def test_rubin_unequal_variances_use_their_mean():
    est = pd.DataFrame({"b": [1.0, 1.0]})
    var = pd.DataFrame({"b": [0.1, 0.3]})
    assert model.pool_rubin(est, var).loc["b", "se"] == pytest.approx(0.2 ** 0.5)


# --- Imputation and model ----------------------------------------------------------

def big_table(n=400, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    in_work = rng.integers(0, 2, n).astype(float)
    t = pd.DataFrame({
        model.OUTCOME: rng.integers(0, 2, n),
        "weight": rng.uniform(0.5, 2, n),
        "woman": rng.integers(0, 2, n),
        "age": rng.integers(20, 80, n).astype(float),
        "educ": rng.integers(0, 9, n).astype(float),
        "in_work": in_work,
        "work_hours": in_work * rng.integers(10, 60, n),
        "partner_in_work": rng.integers(0, 2, n).astype(float),
        "partner_work_hours": 0.0,
        "any_child": rng.integers(0, 2, n).astype(float),
        "country": rng.choice(["AT", "DE", "NL"], n),
    })
    t["partner_work_hours"] = t["partner_in_work"] * rng.integers(10, 60, n)
    for col in ["age", "educ", "in_work", "work_hours", "any_child"]:
        t.loc[rng.random(n) < 0.1, col] = np.nan
    return t


def test_imputation_fills_with_valid_values():
    t = big_table()
    out = model.impute_once(t, random_state=0)
    assert not out[model.FEATURES].isna().any().any()
    observed = t["age"].notna()
    pd.testing.assert_series_equal(out.loc[observed, "age"], t.loc[observed, "age"])
    for col in model.BINARY:
        assert set(out[col].unique()) <= {0.0, 1.0}
    assert out["educ"].between(0, 8).all()
    assert (out.loc[out["in_work"].eq(0), "work_hours"] == 0).all()
    assert (out.loc[out["in_work"].eq(1), "work_hours"] >= 1).all()
    assert out[model.OUTCOME].equals(t[model.OUTCOME])  # outcome never changes


def test_imputations_differ_by_random_state():
    t = big_table()
    a, b = model.impute_once(t, 0), model.impute_once(t, 1)
    missing = t["age"].isna()
    assert not a.loc[missing, "age"].equals(b.loc[missing, "age"])


def test_design_matrix_has_no_leakage_and_countries_are_fixed_effects():
    X = model.design_matrix(model.impute_once(big_table(), 0))
    # Effect coding: one column per country except the last (NL).
    assert [c for c in X.columns if c.startswith("country_")] == ["country_AT", "country_DE"]
    assert not any(c.startswith("task_") or c in model.LEAKAGE_COLUMNS for c in X.columns)


def test_effect_coding_rows():
    X = model.country_effects(pd.Series(["AT", "DE", "NL"]))
    assert X.values.tolist() == [[1, 0], [0, 1], [-1, -1]]


def test_effect_coded_countries_sum_to_zero():
    # Every country gets an odds ratio, and the effects average out to 0.
    t = big_table()
    res = model.fit_logit(model.impute_once(t, 0))
    est, var = model.coefficients(res, t["country"])
    countries = est[est.index.str.startswith("country_")]
    assert sorted(countries.index) == ["country_AT", "country_DE", "country_NL"]
    assert countries.sum() == pytest.approx(0, abs=1e-10)
    # Variance of -(b_AT + b_DE) = V_AT + V_DE + 2 Cov(AT, DE)
    cov = res.cov_params()
    expected = (cov.loc["country_AT", "country_AT"] + cov.loc["country_DE", "country_DE"]
                + 2 * cov.loc["country_AT", "country_DE"])
    assert var["country_NL"] == pytest.approx(expected)


def test_effect_coding_matches_dummy_coding_for_other_terms():
    # Changing the country coding must not move any non-country coefficient.
    t = model.impute_once(big_table(), 0)
    effect = model.fit_logit(t).params
    X = model.design_matrix(t).drop(columns=["country_AT", "country_DE"])
    X = X.join(pd.get_dummies(t["country"], prefix="d", drop_first=True, dtype=float))
    dummy = sm.GLM(t[model.OUTCOME].astype(float), X, family=sm.families.Binomial(),
                   var_weights=t["weight"]).fit().params
    for term in ["woman", "age_10y", "any_child", "work_hours_10"]:
        assert effect[term] == pytest.approx(dummy[term], rel=1e-6)


def test_own_paid_share():
    out = model.own_paid_share(pd.Series([40.0, 0.0, 0.0, 30.0]),
                               pd.Series([40.0, 50.0, 0.0, 10.0]))
    assert out.tolist() == [0.5, 0.0, 0.5, 0.75]  # neither works -> 0.5


def test_hours_share_design_replaces_hour_columns():
    X = model.design_matrix(model.impute_once(big_table(), 0), hours="share")
    assert "own_paid_share_10pp" in X.columns
    assert "work_hours_10" not in X.columns and "partner_work_hours_10" not in X.columns
    with pytest.raises(ValueError):
        model.design_matrix(big_table(), hours="hourly")


def test_odds_ratio_table_puts_countries_last():
    t = big_table()
    ors = model.odds_ratio_table(model.fit_mi(t, m=2), model.complete_case(t))
    is_country = ors.index.str.startswith("country_")
    assert is_country[-3:].all() and not is_country[:-3].any()
    assert "const" not in ors.index
    assert (ors["ci_low_mi"] < ors["or_mi"]).all() and (ors["or_mi"] < ors["ci_high_mi"]).all()
    assert (ors["ci_low_cc"] < ors["or_cc"]).all() and (ors["or_cc"] < ors["ci_high_cc"]).all()


# --- Session 3b: cross-validation, calibration, SHAP ----------------------------------

def test_imputation_is_fitted_on_training_rows_only():
    t = big_table()
    levels = sorted(t["country"].unique())
    train, test = t.iloc[:300].copy(), t.iloc[300:].copy()
    target = test.index[test["age"].isna()][0]
    others = test.index.drop(target)

    _, before = model.impute_train_test(train, test, levels)
    # Wildly change every other test row. An imputer fitted on training rows
    # only cannot see this, so the target row's imputed age must not move.
    shifted = test.copy()
    shifted.loc[others, "age"] = shifted.loc[others, "age"] * 10 + 500
    shifted.loc[others, "educ"] = 8
    _, after = model.impute_train_test(train, shifted, levels)
    assert after.loc[target, "age"] == before.loc[target, "age"]


def test_leaky_imputation_would_be_caught():
    # The deliberately leaky version (fitting on train + test) does move the
    # imputed value, so the test above would fail if the code leaked.
    t = big_table()
    levels = sorted(t["country"].unique())
    train, test = t.iloc[:300].copy(), t.iloc[300:].copy()
    target = test.index[test["age"].isna()][0]
    shifted = test.copy()
    others = test.index.drop(target)
    shifted.loc[others, "age"] = shifted.loc[others, "age"] * 10 + 500
    _, honest = model.impute_train_test(pd.concat([train, test]), test, levels)
    _, leaky = model.impute_train_test(pd.concat([train, shifted]), shifted, levels)
    assert leaky.loc[target, "age"] != honest.loc[target, "age"]


def test_folds_identical_across_models():
    t = big_table()
    seen = {}

    def recorder(name):
        def predict(train, test, levels, seed):
            seen.setdefault(name, []).append((tuple(train.index), tuple(test.index)))
            return np.full(len(test), 0.5)
        return predict

    oof, metrics = model.cross_validate(t, k=5, models={"a": recorder("a"), "b": recorder("b")})
    assert seen["a"] == seen["b"]
    assert len(seen["a"]) == 5
    tested = [i for _, test in seen["a"] for i in test]
    assert sorted(tested) == sorted(t.index)  # every row tested exactly once
    for train, test in seen["a"]:
        assert not set(train) & set(test)
    assert oof["fold"].between(0, 4).all()


def test_cv_folds_are_fixed_and_stratified():
    y = pd.Series([0] * 60 + [1] * 40)
    a, b = model.cv_folds(y, k=5, seed=1), model.cv_folds(y, k=5, seed=1)
    assert a.equals(b)
    assert (y.groupby(a).mean() == 0.4).all()


def test_cross_validate_runs_both_real_models():
    t = big_table()
    oof, metrics = model.cross_validate(t, k=3, models={k: model.MODELS[k]
                                                         for k in ["logistic", "boosting"]})
    assert oof[["logistic", "boosting"]].notna().all().all()
    assert oof[["logistic", "boosting"]].stack().between(0, 1).all()
    assert len(metrics) == 6 and metrics["auc"].between(0, 1).all()


def test_calibration_of_true_probabilities():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, 20000)
    y = (rng.random(20000) < p).astype(int)
    w = np.ones(20000)
    good = model.calibration_slope_intercept(y, p, w)
    assert good["slope"] == pytest.approx(1, abs=0.05)
    assert good["intercept"] == pytest.approx(0, abs=0.05)
    # Doubling the log-odds makes predictions too extreme: slope near 0.5.
    lp = np.log(p / (1 - p))
    extreme = model.calibration_slope_intercept(y, 1 / (1 + np.exp(-2 * lp)), w)
    assert extreme["slope"] == pytest.approx(0.5, abs=0.05)


def test_reliability_curve_hand_checked():
    y = [0, 1, 1, 1]
    p = [0.2, 0.4, 0.6, 0.8]
    w = [1, 3, 1, 1]
    curve = model.reliability_curve(y, p, w, bins=2)
    # Bin 1: p 0.2 (w 1), 0.4 (w 3) -> predicted 0.35, observed 0.75
    assert curve.loc[0, "predicted"] == pytest.approx(0.35)
    assert curve.loc[0, "observed"] == pytest.approx(0.75)
    assert curve.loc[1, "predicted"] == pytest.approx(0.7)


def test_boost_shap_groups_countries_and_adds_up():
    values = model.boost_shap(big_table())  # raises if SHAP doesn't add up
    assert "country" in values.columns
    assert not any(c.startswith("country_") for c in values.columns)
    assert set(values.columns) == set(model.FEATURES)


def test_logit_contributions_are_centred_linear_terms():
    t = big_table()
    contrib = model.logit_contributions(t)
    data = model.impute_once(t, random_state=0)
    res = model.fit_logit(data)
    lp = model.design_matrix(data) @ res.params
    expected = lp - np.average(lp, weights=data["weight"])
    np.testing.assert_allclose(contrib.sum(axis=1), expected, atol=1e-10)
    assert set(contrib.columns) == set(model.FEATURES)


# --- Exploratory: couple's paid hours (added after 3b) --------------------------------

def test_couple_paid_hours_from_the_womans_side():
    t = pd.DataFrame({
        # man 40 / partner 40 -> woman 0.5; man 40 / partner 10 -> woman 0.2;
        # woman 10 / partner 40 -> 0.2; woman 40 / partner 10 -> 0.8;
        # both 0 -> neither; woman 0 / partner 40 -> 0.0; missing -> NaN
        "woman": [0, 0, 1, 1, 1, 1, 0],
        "work_hours": [40, 40, 10, 40, 0, 0, np.nan],
        "partner_work_hours": [40, 10, 40, 10, 0, 40, 20],
    }, dtype=float)
    out = model.couple_paid_hours(t)
    assert out.tolist()[:6] == ["equal", "man_more", "man_more", "woman_more",
                                "neither", "man_more"]
    assert pd.isna(out.iloc[6])


def test_couple_paid_hours_cutoffs_are_inclusive_for_equal():
    # Woman's share exactly 0.4 and 0.6 -> equal; 0.45/0.55 cut-offs -> not.
    t = pd.DataFrame({"woman": [1.0, 1.0], "work_hours": [40.0, 60.0],
                      "partner_work_hours": [60.0, 40.0]})
    assert model.couple_paid_hours(t).tolist() == ["equal", "equal"]
    assert model.couple_paid_hours(t, (0.45, 0.55)).tolist() == ["man_more", "woman_more"]


def test_couple_design_has_equal_as_reference():
    X = model.design_matrix(model.impute_once(big_table(), 0), hours="couple")
    couple = [c for c in X.columns if c.startswith("couple_")]
    assert couple == ["couple_man_more", "couple_woman_more", "couple_neither"]
    assert "work_hours_10" not in X.columns and "partner_work_hours_10" not in X.columns
    assert {"in_work", "partner_in_work"} <= set(X.columns)


def test_couple_design_without_work_status():
    X = model.design_matrix(model.impute_once(big_table(), 0), hours="couple",
                            work_status=False)
    assert not {"in_work", "partner_in_work"} & set(X.columns)
    assert "couple_neither" in X.columns
