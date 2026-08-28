"""Central configuration for the HTTP Archive robustness pipeline.

Everything that must stay fixed for a reproducible run lives here: the crawl
dates we pull, which clients, the tracker-list version, and all input/output
paths. No secrets are stored here -- the BigQuery billing project is read from
the environment so that credentials never enter the repository.

See README.md in this directory for auth and cost details.
"""

import os

# --------------------------------------------------------------------------- #
# BigQuery
# --------------------------------------------------------------------------- #
# Billing project for BigQuery jobs. Set it in your shell before running:
#     export BQ_BILLING_PROJECT=your-gcp-project-id
# Auth uses Application Default Credentials (gcloud auth application-default
# login) -- NOT an API key. See README.md.
BQ_BILLING_PROJECT = os.environ.get("BQ_BILLING_PROJECT")

# HTTP Archive public dataset (current schema: the `crawl` dataset).
HA_REQUESTS_TABLE = "httparchive.crawl.requests"

# Price used only to turn dry-run byte counts into a dollar estimate.
# On-demand analysis pricing (US multi-region) is $6.25 per TiB scanned.
BQ_PRICE_PER_TIB_USD = 6.25
BYTES_PER_TIB = 2**40

# --------------------------------------------------------------------------- #
# Crawls to pull
# --------------------------------------------------------------------------- #
# The panel was collected June 2022; Blacklight scans ran ~Jan 2025.
#   panel            -> matches the browsing window we actually observed
#   recent           -> same calendar month, three years later (change end-point)
#   blacklight_match -> nearest crawl to when Blacklight actually scanned, used
#                       only for the HA-vs-Blacklight cross-instrument check
CRAWL_DATES = {
    "panel": "2022-06-01",
    "recent": "2025-06-01",
    "blacklight_match": "2025-01-01",
}

# HTTP Archive crawls each origin under two emulated clients. Blacklight's
# collector emulated an iPhone 13 Mini, so `mobile` is the closer match for the
# cross-instrument check; `desktop` is closer to the panel's browsing mix.
CLIENTS = ["desktop", "mobile"]

# Clustering-based cost control. `crawl.requests` is clustered by
# (client, is_root_page, rank), so a rank ceiling prunes bytes scanned.
# None = no ceiling (full panel-domain coverage, higher cost). The response-
# header (Set-Cookie) scan is far more expensive per row, so it caps tighter.
# Leave as-is until 02_ha_dryrun.py reports the actual byte cost.
RANK_CAP = None
COOKIE_RANK_CAP = 100_000

# Which panel domains to request from HTTP Archive. Domains reaching at least
# this many panelists (matches the rescan-target rule) -- the head that
# dominates visit-weighted exposure.
TARGET_MIN_REACH = 2

# --------------------------------------------------------------------------- #
# Tracker lists (pinned for reproducibility)
# --------------------------------------------------------------------------- #
# DuckDuckGo Tracker Radar is the list Blacklight uses to flag ad trackers, so
# it is our primary classifier. The per-domain `categories` live only in the
# region files (domains/<region>/<domain>.json), so we pull the whole repo at a
# pinned commit and build a compact domain->categories table. One fixed list is
# applied to every crawl, so measured change reflects site behavior, not list
# churn. Pin a commit SHA so classification is reproducible.
DDG_TRACKER_RADAR_REF = "62a93b03bccf"  # tracker-radar @ 2026-06-08
DDG_TARBALL_URL = "https://codeload.github.com/duckduckgo/tracker-radar/tar.gz/{ref}"

# Categories that count a domain as an advertising tracker (mirrors Blacklight's
# ddg_join_ads intent). Verified against tracker-radar docs/CATEGORIES.md.
AD_CATEGORIES = {"Advertising", "Ad Motivated Tracking"}

# Endpoints that identify specific Blacklight measures by registered domain.
FB_PIXEL_HOSTS = {"facebook.com", "facebook.net"}  # connect.facebook.net, /tr
GA_HOSTS = {"google-analytics.com", "googletagmanager.com"}

# --------------------------------------------------------------------------- #
# Paths (all relative to the repo root; resolved from this file's location)
# --------------------------------------------------------------------------- #
_HERE = os.path.dirname(os.path.abspath(__file__))
# These modules live at scripts/collect/<mod>/, so the repository root is
# three levels up, not the two the original scripts/<mod>/ layout implied.
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

DATA_DIR = os.path.join(REPO_ROOT, "data")
HA_DATA_DIR = os.path.join(DATA_DIR, "httparchive")
TRACKER_LIST_DIR = os.path.join(DATA_DIR, "tracker_lists")
TABLES_DIR = os.path.join(REPO_ROOT, "tables")
FIGURES_DIR = os.path.join(REPO_ROOT, "figures")

FP_YG_IND_DOMAIN = os.path.join(DATA_DIR, "yg", "yg_ind_domain.csv")
FP_BLACKLIGHT = os.path.join(DATA_DIR, "blacklight_domain.csv")
FP_HA_TARGETS = os.path.join(HA_DATA_DIR, "ha_targets.csv")
FP_DDG_CATEGORIES = os.path.join(TRACKER_LIST_DIR, "ddg_categories.csv")
# Tidy per-(crawl, client, domain) tracking table, Blacklight-shaped measures.
FP_HA_DOMAIN_MEASURES = os.path.join(HA_DATA_DIR, "ha_domain_measures.csv")


def raw_requests_path(crawl_key, client):
    """Cached raw request-pair extract for one crawl/client."""
    date = CRAWL_DATES[crawl_key].replace("-", "")
    return os.path.join(HA_DATA_DIR, f"ha_requests_{date}_{client}.parquet")


def raw_cookies_path(crawl_key, client):
    """Cached raw third-party Set-Cookie extract for one crawl/client."""
    date = CRAWL_DATES[crawl_key].replace("-", "")
    return os.path.join(HA_DATA_DIR, f"ha_cookies_{date}_{client}.parquet")


def require_billing_project():
    """Return the billing project or raise a clear, actionable error."""
    if not BQ_BILLING_PROJECT:
        raise SystemExit(
            "BQ_BILLING_PROJECT is not set.\n"
            "  export BQ_BILLING_PROJECT=your-gcp-project-id\n"
            "and authenticate with:\n"
            "  gcloud auth application-default login\n"
            "(BigQuery needs Application Default Credentials, not an API key.)"
        )
    return BQ_BILLING_PROJECT
