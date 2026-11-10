"""Modelling for Session 3: who among supporters is a true egalitarian?

build_model_table() turns the cleaned sample into one row per supporter with a
known shared/not-shared status: the outcome (1 = true egalitarian, 0 = unshared
supporter), the rescaled weight and the features, missing values left missing.

Household-work hours (v34, v36) and the task items (v39-v44) define the
outcome, so they must never be features. Neither must anything built from
them (task_*, shared, woman_hours_share, group) or the fairness item (v45),
which is the respondent's verdict on that same division of work.

The model is a weighted logistic regression with country fixed effects and
robust (sandwich) standard errors, fitted on m multiply imputed datasets and
pooled with Rubin's rules, plus a complete-case fit as a sensitivity check.

Session 3b compares it out of sample with gradient boosting (same features,
same weights, same folds), checks calibration, and explains the boosting
model with SHAP values.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as sps
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from harvest_hunt import config as C

# Feature name -> raw ISSP variable(s) it comes from. "country" is the fixed effect.
FEATURE_SOURCES = {
    "woman": [C.SEX],
    "age": [C.COVARIATES["age"]],
    "educ": [C.COVARIATES["educ"]],
    "in_work": [C.COVARIATES["work"]],
    "work_hours": [C.COVARIATES["work_hours"], C.COVARIATES["work"]],
    "partner_in_work": [C.COVARIATES["partner_work"]],
    "partner_work_hours": [C.COVARIATES["partner_work_hours"], C.COVARIATES["partner_work"]],
    "any_child": [C.COVARIATES["kids_school"], C.COVARIATES["kids_under_school"],
                  C.COVARIATES["household_size"], C.COVARIATES["adults"]],
    "country": [C.COUNTRY],
}
FEATURES = list(FEATURE_SOURCES)
OUTCOME = "true_egalitarian"

# Raw variables and sample columns that define the outcome (leakage if used).
LEAKAGE_RAW = [C.HOURS_SELF, C.HOURS_PARTNER, *C.TASKS.values(), C.COVARIATES["fair_share"]]
LEAKAGE_COLUMNS = (["task_" + t for t in C.TASKS]
                   + ["shared", "woman_hours_share", "group", "supporter", "fair_share"])

# Plausible ranges, used to keep imputed values inside the codebook.
BOUNDS = {"age": (15, 100), "educ": (0, 8), "work_hours": (0, 96),
          "partner_work_hours": (0, 96)}
BINARY = ["in_work", "partner_in_work", "any_child"]


def _paid_work(status: pd.Series) -> pd.Series:
    """WORK / SPWORK -> 1 currently in paid work, 0 not, NaN unknown."""
    return status.eq(1).astype(float).where(status.notna())


def build_model_table(sample: pd.DataFrame) -> pd.DataFrame:
    """Supporters with a known group, one row each, with outcome, weight and features."""
    sup = sample[sample["group"].isin(["true_egalitarian", "unshared_supporter"])]
    return pd.DataFrame({
        OUTCOME: sup["group"].eq("true_egalitarian").astype(int),
        "weight": sup["weight"].astype(float),
        "woman": sup["sex"].map({"man": 0, "woman": 1}),
        "age": sup["age"],
        "educ": sup["educ"],
        "in_work": _paid_work(sup["work"]),
        "work_hours": sup["work_hours"],
        "partner_in_work": _paid_work(sup["partner_work"]),
        "partner_work_hours": sup["partner_work_hours"],
        "any_child": sup["any_child"],
        "country": sup["country"].astype(str),
    }, index=sup.index)


def missingness(table: pd.DataFrame, features=FEATURES) -> pd.DataFrame:
    """Missing count and share per feature.

    The last row, "any_feature", counts rows missing at least one feature:
    the rows a complete-case model would drop.
    """
    miss = table[features].isna()
    out = pd.DataFrame({"missing": miss.sum(), "share_missing": miss.mean()})
    out.loc["any_feature"] = [miss.any(axis=1).sum(), miss.any(axis=1).mean()]
    out["missing"] = out["missing"].astype(int)
    return out


# --- Imputation ----------------------------------------------------------------------

NUMERIC_FEATURES = [f for f in FEATURES if f != "country"]


def _imputation_matrix(table: pd.DataFrame, columns, levels=None) -> pd.DataFrame:
    """Numeric columns plus country dummies (first level dropped), for the imputer.

    Passing `levels` fixes the dummy columns, so a training fold and a test
    fold get the same columns even if a country is missing from one of them.
    """
    levels = sorted(table["country"].unique()) if levels is None else levels
    country = pd.Categorical(table["country"], categories=levels)
    countries = pd.get_dummies(country, prefix="c", drop_first=True, dtype=float)
    countries.index = table.index
    return pd.concat([table[columns].astype(float), countries], axis=1)


def _fill(table: pd.DataFrame, filled: pd.DataFrame, columns) -> pd.DataFrame:
    """Put imputed values into the missing cells only, then make them valid.

    Binary features are rounded to 0/1, counts and hours rounded and kept in
    range, and paid hours forced to 0 for anyone imputed as not in paid work
    (and at least 1 for anyone in it).
    """
    out = table.copy()
    for col in columns:
        out[col] = out[col].where(out[col].notna(), filled[col])
    for col in BINARY:
        out[col] = out[col].clip(0, 1).round()
    for col, (low, high) in BOUNDS.items():
        out[col] = out[col].clip(low, high).round()
    for work, hours in [("in_work", "work_hours"), ("partner_in_work", "partner_work_hours")]:
        out[hours] = out[hours].where(out[work].eq(1), 0.0)
        out.loc[out[work].eq(1), hours] = out.loc[out[work].eq(1), hours].clip(lower=1)
    return out


def impute_once(table: pd.DataFrame, random_state: int) -> pd.DataFrame:
    """One imputed copy of the table (IterativeImputer, draws from the posterior).

    For inference (MI): the imputation model sees the outcome, sex, country
    dummies and every other feature, but not the weights.
    """
    columns = [OUTCOME] + NUMERIC_FEATURES
    X = _imputation_matrix(table, columns)
    imputer = IterativeImputer(sample_posterior=True, random_state=random_state, max_iter=10)
    filled = pd.DataFrame(imputer.fit_transform(X), index=X.index, columns=X.columns)
    return _fill(table, filled, columns)


def impute_train_test(train: pd.DataFrame, test: pd.DataFrame, levels,
                      random_state: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """For prediction: fit one imputation on the training rows, apply it to both.

    The outcome is left out of this imputation model: it is unknown for the
    rows being predicted, so using it would leak the answer into the features.
    """
    imputer = IterativeImputer(random_state=random_state, max_iter=10)
    imputer.fit(_imputation_matrix(train, NUMERIC_FEATURES, levels))

    def apply(t):
        X = _imputation_matrix(t, NUMERIC_FEATURES, levels)
        filled = pd.DataFrame(imputer.transform(X), index=X.index, columns=X.columns)
        return _fill(t, filled, NUMERIC_FEATURES)
    return apply(train), apply(test)


# --- Model ---------------------------------------------------------------------------

def own_paid_share(work_hours: pd.Series, partner_work_hours: pd.Series) -> pd.Series:
    """Respondent's share of the couple's paid-work hours; 0.5 if neither works for pay."""
    total = work_hours + partner_work_hours
    return (work_hours / total.replace(0, np.nan)).where(total.ne(0), 0.5)


def country_effects(country: pd.Series, levels=None) -> pd.DataFrame:
    """Sum-to-zero (effect) coding: one column per country except the last.

    A row from country c has 1 in column c; a row from the last country has -1
    in every column. Each coefficient is then that country's difference from
    the unweighted average of all country effects. The last country's effect
    is minus the sum of the others (see coefficients()). Pass `levels` to fix
    the columns (e.g. the same countries in every cross-validation fold).
    """
    levels = sorted(country.unique()) if levels is None else levels
    X = pd.DataFrame({f"country_{c}": country.eq(c).astype(float) for c in levels[:-1]},
                     index=country.index)
    X.loc[country.eq(levels[-1])] = -1.0
    return X


def design_matrix(table: pd.DataFrame, hours: str = "absolute", levels=None) -> pd.DataFrame:
    """Model columns. Reference: a man with education up to lower secondary.

    Countries are effect-coded, so the constant is the average country.
    Age is per 10 years and paid hours per 10 hours a week, so odds ratios
    describe a meaningful step rather than one year or one hour.
    hours="share" replaces the two hour variables with the respondent's share
    of the couple's paid hours, per 10 percentage points (robustness check).
    """
    educ = table["educ"]
    X = pd.DataFrame({
        "const": 1.0,
        "woman": table["woman"],
        "age_10y": table["age"] / 10,
        "educ_secondary": educ.between(3, 4).astype(float),   # upper / post-secondary
        "educ_tertiary": educ.ge(5).astype(float),            # short-cycle to PhD
        "in_work": table["in_work"],
        "partner_in_work": table["partner_in_work"],
        "any_child": table["any_child"],
    }, index=table.index)
    if hours == "absolute":
        X["work_hours_10"] = table["work_hours"] / 10
        X["partner_work_hours_10"] = table["partner_work_hours"] / 10
    elif hours == "share":
        X["own_paid_share_10pp"] = own_paid_share(table["work_hours"],
                                                  table["partner_work_hours"]) * 10
    else:
        raise ValueError(f"hours must be 'absolute' or 'share', not {hours!r}")
    return pd.concat([X.astype(float), country_effects(table["country"], levels)], axis=1)


def fit_logit(table: pd.DataFrame, hours: str = "absolute", levels=None):
    """Weighted logistic GLM with HC0 robust standard errors.

    Weights enter as var_weights: with HC0 this gives the usual survey
    ("pweight") sandwich. freq_weights would treat each weight as that many
    copies of the person and make the intervals too narrow.
    """
    X = design_matrix(table, hours, levels)
    return sm.GLM(table[OUTCOME].astype(float), X, family=sm.families.Binomial(),
                  var_weights=table["weight"]).fit(cov_type="HC0")


def coefficients(result, country: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Estimates and variances, with the left-out country added back.

    Under effect coding the last country's effect is minus the sum of the
    others; its variance is a'Va with a = -1 for every country column.
    """
    params, cov = result.params.copy(), result.cov_params()
    cols = [c for c in params.index if c.startswith("country_")]
    last = f"country_{sorted(country.unique())[-1]}"
    a = pd.Series(0.0, index=params.index)
    a[cols] = -1.0
    variances = pd.Series(np.diag(cov), index=params.index)
    params[last] = float(a @ result.params)
    variances[last] = float(a @ cov @ a)
    return params, variances


def pool_rubin(estimates: pd.DataFrame, variances: pd.DataFrame,
               level: float = 0.95) -> pd.DataFrame:
    """Combine m sets of estimates with Rubin's rules (Rubin 1987).

    estimates, variances: one row per imputation, one column per coefficient.
    Pooled estimate = mean; total variance T = W + (1 + 1/m) B, where W is the
    mean within-imputation variance and B the between-imputation variance.
    Degrees of freedom (m - 1)(1 + W / ((1 + 1/m) B))^2; infinite when B = 0.
    """
    m = len(estimates)
    q = estimates.mean()
    W = variances.mean()
    B = estimates.var(ddof=1)
    T = W + (1 + 1 / m) * B
    extra = (1 + 1 / m) * B
    with np.errstate(divide="ignore"):
        df = ((m - 1) * (1 + W / extra) ** 2).where(extra > 0, np.inf)
    se = np.sqrt(T)
    t = sps.t.ppf(0.5 + level / 2, df)
    return pd.DataFrame({
        "estimate": q, "se": se, "df": df,
        "ci_low": q - t * se, "ci_high": q + t * se,
        "p": 2 * sps.t.sf(np.abs(q / se), df),
        "fmi": (extra / T).fillna(0.0),  # rough fraction of information missing
    })


def fit_mi(table: pd.DataFrame, m: int = 20, seed: int = 0,
           hours: str = "absolute") -> pd.DataFrame:
    """Impute m times (random_state seed, seed+1, ...), fit each, pool with Rubin's rules."""
    estimates, variances = [], []
    for i in range(m):
        res = fit_logit(impute_once(table, random_state=seed + i), hours)
        est, var = coefficients(res, table["country"])
        estimates.append(est)
        variances.append(var)
    return pool_rubin(pd.DataFrame(estimates), pd.DataFrame(variances))


def complete_case(table: pd.DataFrame, hours: str = "absolute") -> pd.DataFrame:
    """Same model on rows with no missing feature, in the pool_rubin() layout."""
    cc = table.dropna(subset=FEATURES)
    est, var = coefficients(fit_logit(cc, hours), cc["country"])
    se = np.sqrt(var)
    z = sps.norm.ppf(0.975)
    return pd.DataFrame({"estimate": est, "se": se,
                         "ci_low": est - z * se, "ci_high": est + z * se,
                         "p": 2 * sps.norm.sf(np.abs(est / se))})


def odds_ratio_table(mi: pd.DataFrame, cc: pd.DataFrame | None = None) -> pd.DataFrame:
    """Odds ratios with 95% CIs, MI and complete-case side by side, countries last.

    Country odds ratios compare each country with the average country.
    """
    def as_or(est, tag):
        return pd.DataFrame({f"or_{tag}": np.exp(est["estimate"]),
                             f"ci_low_{tag}": np.exp(est["ci_low"]),
                             f"ci_high_{tag}": np.exp(est["ci_high"]),
                             f"p_{tag}": est["p"]})
    out = as_or(mi, "mi")
    if cc is not None:
        out = out.join(as_or(cc, "cc"))
    out = out.drop(index="const")
    is_country = out.index.str.startswith("country_")
    out = pd.concat([out[~is_country], out[is_country]])
    out.index.name = "term"
    return out


# --- Prediction: logistic vs gradient boosting (Session 3b) --------------------------

CV_SEED = 2026
BOOST_PARAMS = {  # modest fixed settings, no grid search
    "learning_rate": 0.05, "max_iter": 500, "max_leaf_nodes": 15,
    "min_samples_leaf": 50, "l2_regularization": 1.0,
    "early_stopping": True, "validation_fraction": 0.1, "n_iter_no_change": 20,
}


def cv_folds(y: pd.Series, k: int = 5, seed: int = CV_SEED) -> pd.Series:
    """Fold number (0 to k-1) for every row, stratified on the outcome.

    Computed once and shared by every model, so all models see identical folds.
    """
    folds = pd.Series(-1, index=y.index)
    splitter = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
    for i, (_, test) in enumerate(splitter.split(np.zeros(len(y)), y)):
        folds.iloc[test] = i
    return folds


def predict_logit(train: pd.DataFrame, test: pd.DataFrame, levels, seed: int = CV_SEED):
    """Logistic model: impute from the training fold only, fit, predict the test fold."""
    train, test = impute_train_test(train, test, levels, random_state=seed)
    res = fit_logit(train, levels=levels)
    return np.asarray(res.predict(design_matrix(test, levels=levels)))


def boost_matrix(table: pd.DataFrame, levels, one_hot: bool = False) -> pd.DataFrame:
    """Boosting features: as in the logistic model, missing values left in.

    Country is an integer code (native categorical) or, with one_hot, one 0/1
    column per country. SHAP's TreeExplainer is exact only for the one-hot
    version: it misreads scikit-learn's categorical splits.
    """
    X = table[NUMERIC_FEATURES].astype(float).copy()
    country = pd.Categorical(table["country"], categories=levels)
    if one_hot:
        dummies = pd.get_dummies(country, prefix="country", dtype=float)
        dummies.index = X.index
        return pd.concat([X, dummies], axis=1)
    X["country"] = country.codes.astype(float)
    return X


def fit_boost(train: pd.DataFrame, levels, seed: int = CV_SEED, one_hot: bool = False):
    """HistGradientBoostingClassifier with survey weights and early stopping.

    Native mode treats country and education as categorical; one-hot mode
    (for SHAP) keeps education as an ordered number.
    """
    X = boost_matrix(train, levels, one_hot)
    categorical = None if one_hot else ["country", "educ"]
    model = HistGradientBoostingClassifier(categorical_features=categorical,
                                           random_state=seed, **BOOST_PARAMS)
    return model.fit(X, train[OUTCOME], sample_weight=train["weight"])


def predict_boost(train, test, levels, seed: int = CV_SEED, one_hot: bool = False):
    model = fit_boost(train, levels, seed, one_hot)
    return model.predict_proba(boost_matrix(test, levels, one_hot))[:, 1]


def predict_boost_onehot(train, test, levels, seed: int = CV_SEED):
    return predict_boost(train, test, levels, seed, one_hot=True)


MODELS = {
    "logistic": predict_logit,
    "boosting": predict_boost,
    "boosting_onehot": predict_boost_onehot,  # the variant SHAP explains
}


def cross_validate(table: pd.DataFrame, k: int = 5, seed: int = CV_SEED,
                   models=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Out-of-fold predictions and per-fold weighted AUC and Brier score.

    Folds are computed once, so every model is trained and tested on exactly
    the same rows. Returns (oof: one row per respondent, metrics: one row per
    model and fold).
    """
    models = MODELS if models is None else models
    levels = sorted(table["country"].unique())
    folds = cv_folds(table[OUTCOME], k, seed)
    oof = pd.DataFrame({"fold": folds, OUTCOME: table[OUTCOME],
                        "weight": table["weight"]}, index=table.index)
    rows = []
    for fold in range(k):
        train, test = table[folds != fold], table[folds == fold]
        for name, predict in models.items():
            p = predict(train, test, levels, seed)
            oof.loc[test.index, name] = p
            y, w = test[OUTCOME], test["weight"]
            rows.append({"model": name, "fold": fold, "n": len(test),
                         "auc": roc_auc_score(y, p, sample_weight=w),
                         "brier": brier_score_loss(y, p, sample_weight=w)})
    return oof, pd.DataFrame(rows)


def summarise_cv(metrics: pd.DataFrame) -> pd.DataFrame:
    """Mean and SD across folds per model."""
    return metrics.groupby("model")[["auc", "brier"]].agg(["mean", "std"])


# --- Calibration ---------------------------------------------------------------------

def calibration_slope_intercept(y, p, w) -> dict:
    """Weighted calibration slope and calibration-in-the-large.

    slope: coefficient on logit(p) in a logistic regression of y on logit(p);
    1 is ideal, below 1 means predictions are too extreme.
    intercept: constant with logit(p) as a fixed offset (slope held at 1);
    0 is ideal, above 0 means predictions are too low on average.
    """
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    lp = np.log(p / (1 - p))
    y = np.asarray(y, dtype=float)
    fam = sm.families.Binomial()
    slope = sm.GLM(y, sm.add_constant(lp), family=fam, var_weights=w).fit().params[1]
    intercept = sm.GLM(y, np.ones_like(lp), family=fam, offset=lp,
                       var_weights=w).fit().params[0]
    return {"slope": float(slope), "intercept": float(intercept)}


def reliability_curve(y, p, w, bins: int = 10) -> pd.DataFrame:
    """Weighted mean prediction vs weighted observed rate in `bins` equal-count bins."""
    d = pd.DataFrame({"y": np.asarray(y, float), "p": np.asarray(p, float),
                      "w": np.asarray(w, float)})
    d["bin"] = pd.qcut(d["p"].rank(method="first"), bins, labels=False)
    rows = []
    for _, b in d.groupby("bin"):
        rows.append({"predicted": np.average(b["p"], weights=b["w"]),
                     "observed": np.average(b["y"], weights=b["w"]), "n": len(b)})
    return pd.DataFrame(rows)


# --- SHAP ----------------------------------------------------------------------------

def feature_of(column: str) -> str:
    """Model column -> the feature it belongs to (countries and education grouped)."""
    if column.startswith("country"):
        return "country"
    if column.startswith("educ"):
        return "educ"
    return {"age_10y": "age", "work_hours_10": "work_hours",
            "partner_work_hours_10": "partner_work_hours"}.get(column, column)


def group_columns(values: pd.DataFrame) -> pd.DataFrame:
    """Sum per-row contributions of columns that belong to one feature."""
    return values.T.groupby(values.columns.map(feature_of)).sum().T


def weighted_mean_abs(values: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """Survey-weighted mean |contribution| per column, largest first."""
    w = np.asarray(weights, float)
    return (values.abs().mul(w, axis=0).sum() / w.sum()).sort_values(ascending=False)


def boost_shap(table: pd.DataFrame, seed: int = CV_SEED) -> pd.DataFrame:
    """SHAP values (log-odds) from the one-hot boosting model fitted on all rows.

    Countries are summed into one "country" column. TreeExplainer's values add
    up exactly to the model's log-odds; this is checked before returning.
    """
    import shap

    levels = sorted(table["country"].unique())
    model = fit_boost(table, levels, seed, one_hot=True)
    X = boost_matrix(table, levels, one_hot=True)
    explainer = shap.TreeExplainer(model)
    values = pd.DataFrame(explainer.shap_values(X), index=X.index, columns=X.columns)
    gap = values.sum(axis=1) + explainer.expected_value - model.decision_function(X)
    if np.abs(gap).max() > 1e-6:
        raise RuntimeError("SHAP values do not add up to the model output.")
    return group_columns(values)


def logit_contributions(table: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """The logistic model's own per-row contributions, b * (x - weighted mean of x).

    For a linear model these are exactly its SHAP values, so they can be ranked
    side by side with the boosting SHAP values. Fitted on one imputation.
    """
    data = impute_once(table, random_state=seed)
    res = fit_logit(data)
    X = design_matrix(data).drop(columns="const")
    centred = X - np.average(X, axis=0, weights=data["weight"])
    return group_columns(centred * res.params[X.columns])
