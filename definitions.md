# Definitions

*The Harvest and the Hunt. Fixed on Oct 23, 2026, before any say–do result was computed. Variable names are confirmed against ISSP 2022 v2.0.0; see `variables.md` for the full list and `src/harvest_hunt/config.py` for the codes.*

This file says exactly who is counted and what each label means, so every number in the project can be checked. Changing anything here after results exist must be recorded in the changelog at the bottom, with the reason.

## Data

- **ISSP 2022 "Family and Changing Gender Roles V"**, study ZA10000, data file **v2.0.0**, doi:10.4232/5.ZA10000.2.0.0. ISSP Research Group (2025), GESIS Data Archive, Cologne.
- 32 countries, 45,762 respondents. Great Britain is not in the integrated file (published separately as ZA8980).
- **Interviews took place from 2021 to 2025**, not only in 2022 (`DATEYR`): Philippines 2021; India 2024; Spain 2025. Results describe each country at its own fieldwork date.
- The data may not be redistributed. The repo contains code and aggregate results only.

## Sample

Respondents who:

1. **live with a partner** (`PARTLIV` = 1, "have partner; live in same household"). The household-task questions only apply to them. People with a partner living elsewhere (`PARTLIV` = 2) are excluded;
2. have sex recorded as male or female (`SEX`).

**Partner's sex is not in the file**, so "who does it" is translated into "the woman" or "the man" by assuming a different-sex couple. Same-sex couples, a small share in most countries, are therefore misclassified rather than excluded. This is a stated limitation.

Sample sizes per country after each step are in `results/sample_flow.csv`. Totals: 45,762 respondents → 27,392 partnered → 26,897 with a known shared/not-shared status → 16,300 supporters with a known status.

## Who does each task

Q18a–f ask who does each task (`v39`–`v44`): 1 always me, 2 usually me, 3 about equal or both together, 4 usually my spouse/partner, 5 always my spouse/partner, 6 done by a third person. Codes -4, -8 and -9 (not applicable, can't choose, no answer) are missing.

Using the respondent's sex, each answer becomes **woman**, **man**, **equal**, or **third person**. Example: a man answering "usually my partner" → the woman does it.

| Item | Task |
|---|---|
| `v39` | Doing the laundry |
| `v40` | Planning social/family activities (the one "invisible work" item) |
| `v41` | Caring for sick family members |
| `v42` | Shopping for groceries |
| `v43` | Household cleaning |
| `v44` | Preparing meals |

## Shared household

A household is **shared** if, among the tasks the couple does, **at least 50%** are done about equally or mostly by the man.

- Tasks done by a third person are left out of the share: they say nothing about how the couple splits the rest. In practice this rarely changes anything: a third person does on average 7% of tasks in South Africa, 3% in India, and less elsewhere.
- Fewer than **3** usable task answers → shared is left missing, not guessed.
- Session 3 reports results at 40% and 60% as well, plus an **hours-based check**: the woman's share of the couple's weekly household-work hours, from the respondent's own hours (`v34`) and the hours they report for their partner (`v36`), both capped at 95.

## Supporter

A respondent is a **supporter** if they **disagree or strongly disagree** (codes 4–5) with Q1f (`v6`): *"A man's job is to earn money; a woman's job is to look after the home and family."* "Neither agree nor disagree" (3) counts as not a supporter; "can't choose" and "no answer" (-8, -9) are missing.

**Why this item:**
- Rejecting it means rejecting the gendered split of paid and unpaid work *in words*. Checking whether the respondent's own home splits the housework is then the cleanest say–do test.
- It is a long-standing ISSP gender-attitude item, which keeps the definition usable for the 1988–2022 trend in v1.1 (to be confirmed in the cumulation file).
- The item originally planned ("both the man and the woman should contribute to household income") is not in ISSP 2022.

**Sensitivity checks (Session 3):**
- `v20` = 3: mother and father should provide for the family financially *equally*. Supporters by this item range from 18% (India) to 85% (Spain).
- `v10` = 1 or 2: a woman should work full- or part-time when the youngest child is at school. This is a very low bar, met by 70% (Philippines) to 100% of respondents, and is closest to the "free to work outside the home" framing in Bursztyn et al.

For comparison, supporters by the main item (`v6`) range from 9% (Philippines) to 90% (Norway); India 23%. The plan's premise that "most people say they support women working" holds for the low-bar item but **not** for `v6` in about a third of countries. That is itself a finding to report.

## Groups (supporters only)

| Label | Meaning |
|---|---|
| **True egalitarian** | Supporter **and** shared household |
| **Unshared supporter** | Supporter whose household does **not** meet the shared threshold |

The plan's working name was "say-only supporter." The data label is neutral because it describes the household, not the respondent's sincerity: a woman who rejects the gendered split but whose husband doesn't share the work is not saying one thing and doing another. Results are reported **separately for men and women**, and the say–do gap is led by men's answers.

**Small groups:** where a country has fewer than **50** supporters of one sex, that sex's estimate is shown with its (wide) interval but is flagged and left out of rankings. This applies to Bulgaria, the Philippines, Hungary and Slovakia (smallest groups: 36, 38, 42 and 47).

## Weights

- Weight variable: **`WEIGHT_COM`** (combination of all design and post-stratification weights). All values are positive.
- Eight countries supply no weights; their weight is 1 for everyone: **Switzerland, Iceland, Italy, Japan, Norway, Sweden, Slovenia, Thailand**. Their estimates are unweighted.
- Weights are rescaled to average 1 within each country, which doesn't change any within-country share.
- Confidence intervals: ISSP does not publish sampling clusters or strata, so CIs assume simple random sampling within each country, adjusted for weighting through the effective sample size. They are probably somewhat too narrow; this is stated wherever they appear.

## Model variables (Session 3)

| Name | Variable | Note |
|---|---|---|
| Age | `AGE` | |
| Education | `EDULEVEL` | ISCED simplified, 0–8 |
| In paid work (self, partner) | `WORK`, `SPWORK` | 1 = currently in paid work |
| Paid work hours (self, partner) | `WRKHRS`, `SPWRKHRS` | Not in paid work → **0 hours**, not missing |
| Children at home | `HHTODD`, `HHCHILDR` | Below school age; school age to 17 |
| Own share judged fair | `v45` | Q19, 1 much more than fair … 5 much less |

**There is no "who earns more" item**, so the plan's "woman's income share" is replaced by the couple's relative paid-work hours. Income variables are country-specific bands and are not used.

## What this does not measure

- **Couples.** Each respondent reports alone. Men's and women's answers come from different households, so any comparison between them is at the country level only.
- **Time per task.** The task items measure who usually does each task, not how long it takes. The hours items cover this only in total.
- **Childcare.** It is not among the task items.
- **Causes.** Every result is an association.

## Changelog

- Oct 23, 2026: definitions fixed before analysis.
