"""Central configuration for the selection-bias audit of unscanned domains.

Strand D (missingness mechanism), deepened: a seeded random sample of domains
Blacklight never successfully scanned, coded against a written rubric and
re-measured directly (live probe + a fresh Blacklight scan). See
../validity_strands.md and README.md in this directory.
"""

import os

# --------------------------------------------------------------------------- #
# Sample design (unscanned domains only; two draws from the same pool)
# --------------------------------------------------------------------------- #
# visits stratum : drawn proportional to panel visits, without replacement --
#                  what a typical unscanned *visit* lands on (what the
#                  exposure estimates care about).
# uniform stratum: drawn uniformly over unscanned domains -- what a typical
#                  unscanned *domain* is (the long-tail picture).
N_PER_STRATUM = 100
SAMPLE_SEED = 20250112
SPOTCHECK_N = 20  # user-adjudicated subset for coder reliability
SPOTCHECK_SEED = 20250113

# --------------------------------------------------------------------------- #
# Blacklight rescan of the sample (same endpoint/pattern as scripts/rescan/)
# --------------------------------------------------------------------------- #
BLACKLIGHT_ENDPOINT = "https://blacklight-us-ca.api.themarkup.org"
SCAN_TIMEOUT = 300  # seconds; scans can take 2+ minutes
SCAN_MAX_RETRIES = 3  # covers transient errors + empty groups
SCAN_WORKERS = 3
SCAN_PAUSE = 2  # polite pause between successful calls, per worker

# Live probe of current status
PROBE_TIMEOUT = 10

# --------------------------------------------------------------------------- #
# Coding rubric categories (see CODING_RUBRIC.md)
# --------------------------------------------------------------------------- #
CATEGORIES = [
    "content_site",
    "adtech_infrastructure",
    "cdn_api_host",
    "parked_or_forsale",
    "adult_content",
    "dead",
    "unknown",
]

# --------------------------------------------------------------------------- #
# Paths (resolved from this file's location)
# --------------------------------------------------------------------------- #
_HERE = os.path.dirname(os.path.abspath(__file__))
# These modules live at scripts/collect/<mod>/, so the repository root is
# three levels up, not the two the original scripts/<mod>/ layout implied.
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

DATA_DIR = os.path.join(REPO_ROOT, "data")
AUDIT_DATA_DIR = os.path.join(DATA_DIR, "selection_audit")
SCAN_JSON_DIR = os.path.join(DATA_DIR, "blacklight_json_audit")
TABLES_DIR = os.path.join(REPO_ROOT, "tables")
FIGURES_DIR = os.path.join(REPO_ROOT, "figures")

FP_YG_IND_DOMAIN = os.path.join(DATA_DIR, "yg", "yg_ind_domain.csv")
FP_BLACKLIGHT = os.path.join(DATA_DIR, "blacklight_domain.csv")
FP_BL_JSON_DIR = os.path.join(DATA_DIR, "blacklight_json")
FP_ERROR_LOG = os.path.join(DATA_DIR, "blacklight_errors.log")
FP_DDG_CATEGORIES = os.path.join(DATA_DIR, "tracker_lists", "ddg_categories.csv")
FP_HA_DOMAIN_MEASURES = os.path.join(DATA_DIR, "httparchive", "ha_domain_measures.csv")
FP_WB_MANIFEST = os.path.join(DATA_DIR, "wayback", "wb_manifest.csv")
WB_HTML_DIR = os.path.join(DATA_DIR, "wayback", "html")

FP_FAILURE_REASONS = os.path.join(AUDIT_DATA_DIR, "failure_reasons.csv")
FP_AUDIT_SAMPLE = os.path.join(AUDIT_DATA_DIR, "audit_sample.csv")
FP_PROBE_RESULTS = os.path.join(AUDIT_DATA_DIR, "probe_results.csv")
FP_AUDIT_EVIDENCE = os.path.join(AUDIT_DATA_DIR, "audit_evidence.csv")
FP_CODES_CLAUDE = os.path.join(AUDIT_DATA_DIR, "codes_claude.csv")
FP_AUDIT_CODED = os.path.join(AUDIT_DATA_DIR, "audit_sample_coded.csv")
FP_SCAN_ERRORS = os.path.join(SCAN_JSON_DIR, "_errors.log")


def scan_json_path(domain):
    return os.path.join(SCAN_JSON_DIR, domain.replace(".", "_") + ".json")


def wb_html_path(domain):
    return os.path.join(WB_HTML_DIR, domain.replace(".", "_") + ".html.gz")
