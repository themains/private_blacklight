"""Central configuration for the implications analyses.

Ties the validity strands back to the paper's claims: does differential scan
coverage, coverage imputation, or 2022->2025 drift change the demographic
comparisons (ms Tables 4-5)? And does the tracking concentration claim
(Figure 3) extend to the unscanned mass? See README.md in this directory and
../paper_implications.md for the write-up.
"""

import os

# --------------------------------------------------------------------------- #
# Measures and scenarios
# --------------------------------------------------------------------------- #
# The paper's two headline rate measures carry the demographic analysis.
MEASURES = ["ddg_join_ads", "third_party_cookies"]

# Fill scenarios for unscanned visits, named as in
# httparchive/07_coverage_bounds and wayback/06_coverage_bounds_wayback:
#   zero      -> published construction (unscanned visits contribute zero)
#   mean      -> unscanned visits filled with the scanned visit-weighted mean
#   ha_mean   -> HA-2022-calibrated fill where HA measured the domain,
#                scanned mean for the remainder
#   hawb_mean -> HA fill, then Wayback fill for WB-only domains, scanned
#                mean for the remainder (cookies: no WB visibility -> = ha_mean)
SCENARIOS = ["zero", "mean", "ha_mean", "hawb_mean"]

# Wayback static parses cannot see cookies; WB fills apply to these only.
WB_KEYS = ["ddg_join_ads", "fb_pixel", "google_analytics"]

# --------------------------------------------------------------------------- #
# Regression spec behind Tables 5 and 6; scripts/07_demo_differences.py and
# scripts/07b_coefplot.py both fit through it, so table and figure cannot drift.
# --------------------------------------------------------------------------- #
FORMULA_RHS = (
    "C(gender_lab, Treatment('Male'))"
    " + C(race_lab, Treatment('White'))"
    " + C(educ_lab, Treatment('HS or Below'))"
    " + C(agegroup_lab, Treatment('<25'))"
)

COEF_LABELS = {
    "C(gender_lab, Treatment('Male'))[T.Female]": "Woman",
    "C(race_lab, Treatment('White'))[T.Black]": "Race: African American",
    "C(race_lab, Treatment('White'))[T.Asian]": "Race: Asian",
    "C(race_lab, Treatment('White'))[T.Hispanic]": "Race: Hispanic",
    "C(race_lab, Treatment('White'))[T.Other]": "Race: Other",
    "C(educ_lab, Treatment('HS or Below'))[T.Some college]": "Educ: Some college",
    "C(educ_lab, Treatment('HS or Below'))[T.College]": "Educ: College",
    "C(educ_lab, Treatment('HS or Below'))[T.Postgrad]": "Educ: Postgraduate",
    "C(agegroup_lab, Treatment('<25'))[T.25-34]": "Age: 25--34",
    "C(agegroup_lab, Treatment('<25'))[T.35-49]": "Age: 35--49",
    "C(agegroup_lab, Treatment('<25'))[T.50-64]": "Age: 50--64",
    "C(agegroup_lab, Treatment('<25'))[T.65+]": "Age: 65+",
}

# Replication gate. 07_demo_differences.py writes this file from the same fitted
# models it renders into Table 5, so the gate compares the scenario refit against
# the table the manuscript actually inputs. It used to compare against four
# coefficients transcribed out of the PDF, which tested whether someone had
# remembered to retype them rather than whether the code reproduced the table.
GATE_TOLERANCE = 5e-6  # both sides are the same estimator; only I/O rounding differs

# --------------------------------------------------------------------------- #
# Paths (resolved from this file's location)
# --------------------------------------------------------------------------- #
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

DATA_DIR = os.path.join(REPO_ROOT, "data")
IMPL_DATA_DIR = os.path.join(DATA_DIR, "implications")
TABLES_DIR = os.path.join(REPO_ROOT, "tables")
FIGURES_DIR = os.path.join(REPO_ROOT, "figures")

FP_YG_IND_DOMAIN = os.path.join(DATA_DIR, "yg", "yg_ind_domain.csv")
FP_BLACKLIGHT = os.path.join(DATA_DIR, "blacklight_domain.csv")
FP_COMBINED = os.path.join(DATA_DIR, "combined_yg_bl_who_derived_hist_tracking.csv")
FP_HA_DOMAIN_MEASURES = os.path.join(DATA_DIR, "httparchive", "ha_domain_measures.csv")
FP_WB_DOMAIN_MEASURES = os.path.join(DATA_DIR, "wayback", "wb_domain_measures.csv")
FP_DDG_CATEGORIES = os.path.join(DATA_DIR, "tracker_lists", "ddg_categories.csv")
FP_BL_JSON_DIR = os.path.join(DATA_DIR, "blacklight_json")
FP_AUDIT_JSON_DIR = os.path.join(DATA_DIR, "blacklight_json_audit")
FP_AUDIT_SAMPLE = os.path.join(DATA_DIR, "selection_audit", "audit_sample.csv")

FP_USER_RATES = os.path.join(IMPL_DATA_DIR, "user_scenario_rates.csv")
FP_TABLE5_COEFS = os.path.join(
    IMPL_DATA_DIR, "demo_differences_exposure_rate_coefficients.csv"
)
