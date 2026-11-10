# Hypothesis verdict: do most supporters live in a shared household?

*Session 3c, Nov 10, 2026. ISSP 2022 (ZA10000 v2.0.0). Numbers from `sensitivity_summary.csv` and `sensitivity_by_country.csv`; definitions in `definitions.md`.*

For each country and sex, we ask whether the share of supporters who live in a shared household is clearly above 50% (the whole 95% interval above 50%), clearly below 50% (the whole interval below), or unclear. Groups with fewer than 50 supporters are left out. Men and women are never pooled: men describe their own share of the housework, women describe their partner's.

## Main definition

| | Clear majority | Clear minority | Unclear | Countries counted |
|---|---|---|---|---|
| Men | **22** | 1 | 5 | 28 |
| Women | 6 | **8** | **16** | 30 |

- **Men's reports:** in 22 of 28 countries, a clear majority of male supporters say their household shares the housework. The exception is Japan, where it is a clear minority. The typical country is at 68%.
- **Women's reports:** a clear majority only in the five Nordic countries (Denmark, Finland, Iceland, Norway, Sweden) and Poland. It is a clear minority in eight countries and unclear in sixteen. The typical country is at 46%.
- **So the answer depends on who you ask.** By men's account most supporters share the housework. By women's account, in most countries they don't, or not clearly. Men and women answer about different households, so this is a gap between their reports, not a measured disagreement within couples.

## How each variant changes this

| Variant | Men: majority / minority / unclear | Women: majority / minority / unclear | Reversals vs main |
|---|---|---|---|
| Main (≥ 50% of tasks shared) | 22 / 1 / 5 | 6 / 8 / 16 | – |
| a. Threshold 40% | 25 / 1 / 2 | 9 / 4 / 17 | none |
| a. Threshold 60% | 9 / 5 / 14 | **0 / 28 / 2** | women IS, NO, PL, SE |
| b. Hours: woman does 40–60% of housework hours | 8 / 6 / 14 | 1 / 21 / 8 | men SI, TW; women FI, NO |
| c. Supporter = parents should provide equally (v20) | 23 / 0 / 7 | 8 / 6 / 18 | none |
| c. Supporter = woman should work when children are at school (v10) | 21 / 3 / 8 | 5 / 21 / 6 | none |

A reversal is a country that moves from clear majority to clear minority, or the reverse.

- **Easier threshold (40%):** the same picture, a little more positive. No country changes sides.
- **Stricter threshold (60%), meaning at least 4 of 6 tasks shared:** men become mixed: 9 clear majorities and 5 clear minorities. For women there is no country at all where a clear majority of supporters report this much sharing. Four countries flip for women from clear majority to clear minority, including Norway and Sweden.
- **Hours instead of tasks:** close to the 60% picture. Men are mixed (8 clear majorities, 6 clear minorities); women are a clear minority in 21 of 30 countries. Four reversals, among them Norway and Finland for women.
  - This variant counts a household where the man does more than 60% of the housework hours as "not shared". About 7% of supporters are in that position.
- **Different supporter item:**
  - v20 (parents should provide equally) changes almost nothing.
  - v10 is a very low bar that almost everyone passes (22,355 supporters). It leaves men's verdict about the same, but women's moves clearly toward "minority": 21 of 30 countries. Reaching beyond committed supporters means fewer of them live in shared households, by women's account.

## What holds and what doesn't

- **Holds under every variant:**
  - Men's reports are more favourable than women's: the typical country is higher for men in all six versions.
  - The same countries stay at the top for men: Denmark, Finland, Greece, India, Iceland, Norway, Spain and Sweden are clear majorities every time.
  - Japan stays at the bottom: a clear minority for women in every version.
- **Depends on the definition:** "most male supporters share" holds at 40% and 50%, but not at 60% or by hours. "Women in the Nordic countries report a clear majority" holds at 40% and 50% only. Every reversal in the table comes from a stricter outcome definition; none comes from changing who counts as a supporter.
- **Model:** in the couple's-hours logistic model, sex, age, tertiary education, children at home and "man works more" keep their direction and stay significant under thresholds of 40% and 60% and under the hours outcome (`sensitivity_model.csv`). With the hours outcome, the sex gap shrinks (odds ratio 0.55 instead of 0.37) and age matters less (0.88 per 10 years instead of 0.76).

*Intervals assume simple random sampling within each country and are probably somewhat too narrow (see definitions.md, "Weights"). All results are associations.*
