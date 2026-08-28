# 00_setup.R
# Packages, options and paths. Sourced first by 99_run_all.R.

suppressPackageStartupMessages({
    library(here)
    library(data.table)
    library(dplyr)
    library(jsonlite)
    library(ggplot2)
    library(sandwich)
    library(lmtest)
    library(digest)
})

options(stringsAsFactors = FALSE)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR    <- here("data")
TABLES_DIR  <- here("tables")
FIGURES_DIR <- here("figures")

FP_BL_JSON_DIR <- file.path(DATA_DIR, "blacklight_json")
FP_WTM_JSON_DIR <- file.path(DATA_DIR, "website_trackers")
FP_YG_PROFILE    <- file.path(DATA_DIR, "yg", "profile.csv")
FP_CPS_MARGINS   <- file.path(DATA_DIR, "cps", "cps_asec_2022_margins.csv")

