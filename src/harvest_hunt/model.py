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
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as sps
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer

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

def impute_once(table: pd.DataFrame, random_state: int) -> pd.DataFrame:
    """One imputed copy of the table (IterativeImputer, draws from the posterior).

    The imputation model sees the outcome, sex, country dummies and every other
    feature, but not the weights. Imputed values are then made valid: binary
    features rounded to 0/1, counts and hours rounded and kept in range, and
    paid hours forced to 0 for anyone imputed as not in paid work (and at least
    1 for anyone in it).
    """
    numeric = [OUTCOME] + [f for f in FEATURES if f != "country"]
    countries = pd.get_dummies(table["country"], prefix="c", drop_first=True, dtype=float)
    X = pd.concat([table[numeric].astype(float), countries], axis=1)
    imputer = IterativeImputer(sample_posterior=True, random_state=random_state, max_iter=10)
    filled = pd.DataFrame(imputer.fit_transform(X), index=X.index, columns=X.columns)

    out = table.copy()
    for col in numeric:
        out[col] = out[col].where(out[col].notna(), filled[col])
    for col in BINARY:
        out[col] = out[col].clip(0, 1).round()
    for col, (low, high) in BOUNDS.items():
        out[col] = out[col].clip(low, high).round()
    for work, hours in [("in_work", "work_hours"), ("partner_in_work", "partner_work_hours")]:
        out[hours] = out[hours].where(out[work].eq(1), 0.0)
        out.loc[out[work].eq(1), hours] = out.loc[out[work].eq(1), hours].clip(lower=1)
    return out


# --- Model ---------------------------------------------------------------------------

def own_paid_share(work_hours: pd.Series, partner_work_hours: pd.Series) -> pd.Series:
    """Respondent's share of the couple's paid-work hours; 0.5 if neither works for pay."""
    total = work_hours + partner_work_hours
    return (work_hours / total.replace(0, np.nan)).where(total.ne(0), 0.5)


def country_effects(country: pd.Series) -> pd.DataFrame:
    """Sum-to-zero (effect) coding: one column per country except the last.

    A row from country c has 1 in column c; a row from the last country has -1
    in every column. Each coefficient is then that country's difference from
    the unweighted average of all country effects. The last country's effect
    is minus the sum of the others (see coefficients()).
    """
    levels = sorted(country.unique())
    X = pd.DataFrame({f"country_{c}": country.eq(c).astype(float) for c in levels[:-1]},
                     index=country.index)
    X.loc[country.eq(levels[-1])] = -1.0
    return X


def design_matrix(table: pd.DataFrame, hours: str = "absolute") -> pd.DataFrame:
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
    return pd.concat([X.astype(float), country_effects(table["country"])], axis=1)


def fit_logit(table: pd.DataFrame, hours: str = "absolute"):
    """Weighted logistic GLM with HC0 robust standard errors.

    Weights enter as var_weights: with HC0 this gives the usual survey
    ("pweight") sandwich. freq_weights would treat each weight as that many
    copies of the person and make the intervals too narrow.
    """
    X = design_matrix(table, hours)
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
