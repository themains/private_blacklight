# 99_run_all.R
# Run the whole analysis, in order. From the repo root:
#
#     make analysis          (or)      Rscript scripts/R/99_run_all.R
#
# The file list is explicit rather than a glob: the order is the pipeline, and a
# missing file should be an error, not a silent skip.

suppressPackageStartupMessages(library(here))

STEPS <- c(
    "00_setup.R",       # packages, options, paths
    "01_constants.R",   # measure vocabulary, age cut, seeds
    "02_helpers.R",     # table writers, figure theme
    "03_import.R",      # scans -> domain measures
    "04_orgs.R",        # third parties -> parent organizations
    "05_person.R",      # the join -> person-level file
    "06_describe.R",    # Tables 1-4, organization figures
    "07_demography.R",  # Tables 5-6, coefficient plots, birth-year curve
    "08_robustness.R",  # denominator, fills, drift
    "09_blocking.R",    # residual exposure, placebo, projection
    "10_validity.R"     # coverage bounds, drift, selection audit
)

dir.create(here("logs"), showWarnings = FALSE)
log_file <- here("logs", format(Sys.time(), "run_%Y%m%d_%H%M%S.log"))

say <- function(...) {
    line <- sprintf("[%s] %s", format(Sys.time(), "%H:%M:%S"), paste0(...))
    message(line); cat(line, "\n", file = log_file, append = TRUE)
}

say("analysis started")

# Reference data first: a swapped blocklist or Tracker Radar map changes
# numbers everywhere, so fail before any of it is computed.
source(here("scripts", "R", "00_setup.R"))
source(here("scripts", "R", "02_helpers.R"))
check_pins()
say("reference data pins verified")
for (s in STEPS) {
    t0 <- Sys.time()
    source(here("scripts", "R", s))
    say(sprintf("  %-18s %5.1fs", s, as.numeric(Sys.time() - t0, "secs")))
}

# --- run the pipeline -------------------------------------------------------
t0 <- Sys.time()
BL_DOMAIN <<- parse_blacklight()
person <- build_person_level(BL_DOMAIN, parse_whotracksme())
THIRD_PARTIES <<- extract_third_parties()
PAIRS      <- domain_org_pairs(THIRD_PARTIES)
orgs       <- build_org_measures(PAIRS)
ORG_REACH <<- build_org_reach(PAIRS)
orgs       <- merge(orgs, build_org_gini(PAIRS), by = "caseid", all.x = TRUE)
orgs       <- merge(orgs, build_org_share_duration(PAIRS), by = "caseid", all.x = TRUE)
data   <- as.data.frame(merge(person, orgs, by = "caseid", all.x = TRUE))
say(sprintf("built person-level file: %d panelists (%.0fs)", nrow(data),
            as.numeric(Sys.time() - t0, "secs")))

emit_all(data)
VISITS <- visit_panel()
emit_blocking(BL_DOMAIN, person, VISITS)
emit_validity(BL_DOMAIN, person, VISITS, THIRD_PARTIES)

say(sprintf("wrote %d tables, %d figures",
            length(list.files(TABLES_DIR, "\\.tex$")),
            length(list.files(FIGURES_DIR, "\\.pdf$")) - 1L))
say(paste("log:", log_file))
