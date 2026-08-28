"""Central configuration for the Wayback Machine validity pipeline.

Extends the coverage strand (B) to domains neither Blacklight nor HTTP Archive
measured, supplies the contemporaneous WB-vs-HA instrument check (strand C),
and the 2022 liveness check (strand D). See ../validity_strands.md.

Everything fetched from archive.org is cached to disk gzipped (raw CDX JSON
and raw snapshot HTML), so the analysis reproduces from disk even if Wayback
availability changes, and re-runs never re-fetch.
"""

import os

# --------------------------------------------------------------------------- #
# Wayback access
# --------------------------------------------------------------------------- #
# All archive.org access goes through the EDGI `wayback` library, whose
# rate limits and retries follow Internet Archive guidance (see
# 02_fetch_snapshots.py). Only the snapshot window is configured here.

# Snapshot window around the browsing month; prefer the snapshot closest to
# TARGET_TS. June-only would lose too many long-tail domains (sparse capture).
WINDOW_FROM = "20220401"
WINDOW_TO = "20220831"
TARGET_TS = "20220615"

MAX_HTML_BYTES = 5_000_000  # skip pathological pages

# --------------------------------------------------------------------------- #
# Target groups (see 01_build_wb_targets.py)
# --------------------------------------------------------------------------- #
# remainder : domains with no Blacklight scan AND no HA June-2022 measurement,
#             reach >= 2, top-N by panel visits (the never-measured tail).
# calib_bl  : sample of Blacklight-scanned domains -> E[BL count | WB status]
#             calibration for the bounds notebook.
# calib_ha  : sample of HA-June-2022-measured domains -> contemporaneous
#             WB-vs-HA agreement (both June 2022).
N_REMAINDER = 4000
N_CALIB_BL = 500
N_CALIB_HA = 500
SAMPLE_SEED = 20220615  # deterministic sampling

# --------------------------------------------------------------------------- #
# Paths (resolved from this file's location)
# --------------------------------------------------------------------------- #
_HERE = os.path.dirname(os.path.abspath(__file__))
# These modules live at scripts/collect/<mod>/, so the repository root is
# three levels up, not the two the original scripts/<mod>/ layout implied.
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

DATA_DIR = os.path.join(REPO_ROOT, "data")
WB_DATA_DIR = os.path.join(DATA_DIR, "wayback")
CDX_DIR = os.path.join(WB_DATA_DIR, "cdx")  # capture lists (CDX-shaped), gzipped
HTML_DIR = os.path.join(WB_DATA_DIR, "html")  # raw snapshot HTML, gzipped
TABLES_DIR = os.path.join(REPO_ROOT, "tables")
FIGURES_DIR = os.path.join(REPO_ROOT, "figures")

FP_YG_IND_DOMAIN = os.path.join(DATA_DIR, "yg", "yg_ind_domain.csv")
FP_BLACKLIGHT = os.path.join(DATA_DIR, "blacklight_domain.csv")
FP_HA_TARGETS = os.path.join(DATA_DIR, "httparchive", "ha_targets.csv")
FP_HA_DOMAIN_MEASURES = os.path.join(DATA_DIR, "httparchive", "ha_domain_measures.csv")
# Built by scripts/httparchive/04_classify_trackers.py (pinned Tracker Radar).
FP_DDG_CATEGORIES = os.path.join(DATA_DIR, "tracker_lists", "ddg_categories.csv")

FP_WB_TARGETS = os.path.join(WB_DATA_DIR, "wb_targets.csv")
FP_WB_MANIFEST = os.path.join(WB_DATA_DIR, "wb_manifest.csv")
FP_WB_DOMAIN_MEASURES = os.path.join(WB_DATA_DIR, "wb_domain_measures.csv")
FP_WB_ERRORS = os.path.join(WB_DATA_DIR, "_errors.log")

# Same endpoint sets as the HA classifier (scripts/httparchive/config.py).
AD_CATEGORIES = {"Advertising", "Ad Motivated Tracking"}
FB_PIXEL_HOSTS = {"facebook.com", "facebook.net"}
GA_HOSTS = {"google-analytics.com", "googletagmanager.com"}


def cdx_path(domain):
    return os.path.join(CDX_DIR, domain.replace(".", "_") + ".json.gz")


def html_path(domain):
    return os.path.join(HTML_DIR, domain.replace(".", "_") + ".html.gz")
