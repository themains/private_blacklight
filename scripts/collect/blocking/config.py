"""Central configuration for the residual-exposure analysis.

Asks what a panelist's measured June-2022 exposure would have been had they
browsed behind the best defenses available at the time of measurement. Blacklight
attributes each detected behavior to the specific third-party domains
responsible, so residual exposure is computed rather than simulated. See
../residual_exposure.md and README.md in this directory.
"""

import os

# --------------------------------------------------------------------------- #
# Paths (resolved from this file's location)
# --------------------------------------------------------------------------- #
_HERE = os.path.dirname(os.path.abspath(__file__))
# These modules live at scripts/collect/<mod>/, so the repository root is
# three levels up, not the two the original scripts/<mod>/ layout implied.
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

DATA_DIR = os.path.join(REPO_ROOT, "data")
BLOCKING_DATA_DIR = os.path.join(DATA_DIR, "blocking")
BLOCKLIST_DIR = os.path.join(DATA_DIR, "blocklists")
TABLES_DIR = os.path.join(REPO_ROOT, "tables")
FIGURES_DIR = os.path.join(REPO_ROOT, "figures")

FP_BL_JSON_DIR = os.path.join(DATA_DIR, "blacklight_json")
FP_BLACKLIGHT = os.path.join(DATA_DIR, "blacklight_domain.csv")
FP_YG_IND_DOMAIN = os.path.join(DATA_DIR, "yg", "yg_ind_domain.csv")
FP_COMBINED = os.path.join(DATA_DIR, "combined_yg_bl_who_derived_hist_tracking.csv")

FP_SCRIPTS = os.path.join(BLOCKING_DATA_DIR, "bl_domain_scripts.csv")
FP_MANIFEST = os.path.join(BLOCKLIST_DIR, "manifest.json")
FP_BLOCKED_PAIRS = os.path.join(BLOCKING_DATA_DIR, "blocked_pairs.csv")
FP_RULE_COVERAGE = os.path.join(BLOCKING_DATA_DIR, "rule_coverage.csv")
FP_DOMAIN_RESIDUAL = os.path.join(BLOCKING_DATA_DIR, "blacklight_domain_residual.csv")
FP_USER_RESIDUAL = os.path.join(BLOCKING_DATA_DIR, "combined_residual.csv")

# --------------------------------------------------------------------------- #
# Blocklist tiers
#
# Each tier stands for a defense a real user could have installed. Pinned to the
# Blacklight scan window (Jan 2025) so the defense is contemporaneous with the
# measurement; PIN_DATE=None re-fetches current lists as a robustness variant.
#
# DuckDuckGo Tracker Radar is deliberately NOT a tier. Blacklight's ad-tracker
# measure is *defined* by Tracker Radar, so blocking with it would drive that
# measure to zero by construction.
# --------------------------------------------------------------------------- #
PIN_DATE = "2025-01-10"  # Blacklight scans ran 2025-01-04 .. 2025-01-13

EASYLIST_REPO = "easylist/easylist"
DISCONNECT_REPO = "disconnectme/disconnect-tracking-protection"

# name -> (github repo, path within repo)
#
# EasyList publishes built lists at easylist.to but versions only the source
# fragments, so pinning to a date means fetching a directory of fragments at the
# commit of interest and concatenating them. Allowlist (exception) fragments are
# included -- a real blocker applies them, and leaving them out would overstate
# blocking.
LIST_SOURCES = {
    "easylist": (EASYLIST_REPO, "easylist"),
    "easyprivacy": (EASYLIST_REPO, "easyprivacy"),
    "disconnect": (DISCONNECT_REPO, "services.json"),
}

# tier -> (label, [list names])
TIERS = {
    "A": ("Firefox ETP (Disconnect)", ["disconnect"]),
    "B": ("EasyPrivacy", ["easyprivacy"]),
    "C": ("uBO-like (EasyList + EasyPrivacy)", ["easylist", "easyprivacy"]),
}
TIER_ORDER = ["A", "B", "C"]

# --------------------------------------------------------------------------- #
# Blacklight card types and how each maps to a residual measure
#
# count : residual = number of responsible third-party domains left unblocked
# any   : residual = 1 if any responsible domain survives
# --------------------------------------------------------------------------- #
CARD_MEASURES = {
    "ddg_join_ads": ("ddg_join_ads", "count"),
    "cookies": ("third_party_cookies", "count"),
    "canvas_fingerprinters": ("canvas_fingerprinting", "any"),
    "session_recorders": ("session_recording", "any"),
    "key_logging": ("key_logging", "any"),
    "fb_pixel_events": ("fb_pixel", "any"),
    "ga": ("google_analytics", "any"),
}

# The fb_pixel and ga cards report no domainData.scripts. Blacklight detects both
# by the request endpoint, so attribution is assumed rather than observed, and is
# reported separately from the measured ones.
ASSUMED_ATTRIBUTION = {
    "fb_pixel_events": ["connect.facebook.net", "facebook.com"],
    "ga": ["google-analytics.com", "googletagmanager.com", "doubleclick.net"],
}

# --------------------------------------------------------------------------- #
# Matching
#
# Blacklight stores third-party hostnames, not full request URLs, so rules that
# key on a path or query string can never fire. Blocking is therefore
# understated and every residual figure is an upper bound. 03 quantifies the
# gap by reporting what share of each list's network rules are domain-anchored.
# --------------------------------------------------------------------------- #
REQUEST_TYPE = "script"
REQUEST_TYPE_SENSITIVITY = "image"

MEASURES = [m for m, _ in CARD_MEASURES.values()]
