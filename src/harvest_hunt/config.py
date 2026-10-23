"""Variable names and codes for ISSP 2022 (ZA10000, v2.0.0).

Confirmed against the data file and ZA10000_v2-0-0_missing.txt on Oct 23, 2026.
See variables.md for the full variable list.
"""

# --- Identifiers ------------------------------------------------------------------
COUNTRY = "c_alphan"      # 2-letter code (AT ... ZA); 32 countries, one sample each
SEX = "SEX"               # 1 = male, 2 = female, -9 = no answer
MALE, FEMALE = 1, 2
PARTNER_SEX = None        # not in the file: different-sex couples are assumed (a limitation)
PARTNERED = "PARTLIV"     # 1 = has partner, same household; 2 = partner elsewhere; 3 = none
PARTNERED_YES = [1]
WEIGHT = "WEIGHT_COM"     # combination of all design and post-stratification weights.
                          # Equals 1 for everyone in CH, IS, IT, JP, NO, SE, SI, TH (no weights).

# --- Household tasks: Q18a-f "who does it?" ------------------------------------------
TASKS = {
    "laundry": "v39",
    "plan_activities": "v40",   # planning social/family activities (invisible work)
    "care_sick": "v41",
    "groceries": "v42",
    "cleaning": "v43",
    "meals": "v44",
}
# 1 always me, 2 usually me, 3 about equal or both together, 4 usually my partner,
# 5 always my partner, 6 done by a third person. -4 not applicable, -8 can't choose, -9 no answer.
ALWAYS_ME, USUALLY_ME, EQUAL, USUALLY_PARTNER, ALWAYS_PARTNER, THIRD_PERSON = 1, 2, 3, 4, 5, 6

# --- Weekly hours of household work (for the hours-based sensitivity check) --------
HOURS_SELF = "v34"        # Q15a respondent; 0-95 (95 = 95 or more)
HOURS_PARTNER = "v36"     # Q16a spouse/partner; 0-95

# --- Supporter: Q1f "A man's job is to earn money; a woman's job is to look after
#     the home and family." 1 strongly agree ... 5 strongly disagree. ---------------
SUPPORTER_ITEM = "v6"
SUPPORTER_CODES = [4, 5]  # disagree or strongly disagree
# Sensitivity items (Session 3):
#   v20 Q7a who should provide for the family financially: 3 = mother and father equally
#   v10 Q3b woman's work when youngest child is at school: 1 full-time, 2 part-time, 3 stay home
#       (code 4, "women should decide", exists only in Taiwan)

# --- Carried through for modelling (Session 3) -----------------------------------------
COVARIATES = {
    "age": "AGE",
    "educ": "EDULEVEL",            # ISCED simplified 0-8
    "work": "WORK",                # 1 currently in paid work
    "partner_work": "SPWORK",      # 1 currently in paid work
    "work_hours": "WRKHRS",
    "partner_work_hours": "SPWRKHRS",
    "kids_school": "HHCHILDR",     # children from school age to 17 in household
    "kids_under_school": "HHTODD", # children below school age in household
    "fair_share": "v45",           # Q19 own share of housework: 1 much more ... 5 much less than fair
}
# There is no "who earns more" item. Relative paid-work hours replace income share.

# --- Missing-value codes ----------------------------------------------------------------
# Every negative code in this file means missing or not applicable
# (-1 not available, -4 NAP, -7 refused, -8 can't choose / don't know, -9 no answer).
MISSING_CODES = [-1, -2, -3, -4, -5, -6, -7, -8, -9]

# --- Definitions (pre-registered defaults; sensitivity tested in Session 3) -------------
SHARED_THRESHOLD = 0.5    # share of couple-done tasks done equally or mostly by the man
MIN_TASKS_ANSWERED = 3    # fewer usable tasks -> "shared" is left missing
