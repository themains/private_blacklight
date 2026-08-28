# 03_import.R
# Read the collected scans into domain-level measures.
# 34,078 Blacklight scans and 64,072 WhoTracksMe records, 28s combined --
# cheap enough that neither needs to be kept as an intermediate file.

# ---------------------------------------------------------------------------
# Blacklight
# ---------------------------------------------------------------------------
# Every successful scan puts all seven measure cards in groups[[1]]; group 2,
# where present, only ever holds `reported_alphabet`. Verified across all
# 34,078 scans, so the first group is taken rather than searched.
parse_blacklight <- function(json_dir = FP_BL_JSON_DIR) {
    files <- sort(list.files(json_dir, pattern = "\\.json$", full.names = FALSE))
    message(sprintf("Parsing %s Blacklight scans", format(length(files), big.mark = ",")))

    out <- vector("list", length(files))
    for (i in seq_along(files)) {
        payload <- fromJSON(file.path(json_dir, files[i]), simplifyVector = FALSE)
        cards <- payload$groups[[1]]$cards
        row <- list(filename = sub("\\.json$", "", files[i]))
        for (nm in c(BL_COUNT_CARDS, BL_FLAG_CARDS)) row[[nm]] <- 0L

        for (card in cards) {
            ct <- card$cardType
            if (!is.null(ct) && ct %in% names(BL_COUNT_CARDS)) {
                row[[BL_COUNT_CARDS[[ct]]]] <- as.integer(card$bigNumber)
            } else if (!is.null(ct) && ct %in% names(BL_FLAG_CARDS)) {
                row[[BL_FLAG_CARDS[[ct]]]] <- as.integer(isTRUE(card$testEventsFound))
            }
        }
        out[[i]] <- row
        if (i %% 5000 == 0) message(sprintf("  %s/%s", i, length(files)))
    }
    setcolorder(
        rbindlist(out),
        c("filename", "ddg_join_ads", "third_party_cookies", "canvas_fingerprinting",
          "session_recording", "key_logging", "fb_pixel", "google_analytics")
    )[]
}

# ---------------------------------------------------------------------------
# WhoTracksMe
# ---------------------------------------------------------------------------
# Category counts expand sparsely: a domain WTM measured but which has no
# tracker in a category gets NA here, not 0. That is deliberate and matches the
# documented policy -- WTM never reports below 1.02 trackers per page load, so
# its process cannot emit "measured none". 02_join.R decides what absence means:
# a domain with no telemetry at all is dropped, and remaining NAs become 0.
parse_whotracksme <- function(json_dir = FP_WTM_JSON_DIR) {
    files <- sort(list.files(json_dir, pattern = "\\.json$", full.names = FALSE))
    message(sprintf("Parsing %s WhoTracksMe records", format(length(files), big.mark = ",")))

    out <- vector("list", length(files))
    for (i in seq_along(files)) {
        payload <- tryCatch(
            fromJSON(file.path(json_dir, files[i]), simplifyVector = FALSE),
            error = function(e) NULL
        )
        if (is.null(payload) || !length(payload)) next
        st <- payload$statistics
        num <- function(x, strip = NULL) {
            if (is.null(x)) return(NA_real_)
            x <- as.character(x)
            if (!is.null(strip)) x <- sub(strip, "", x, fixed = TRUE)
            suppressWarnings(as.numeric(x))
        }
        row <- list(
            domain_name = gsub("_", ".", sub("_data\\.json$", "", files[i]), fixed = TRUE),
            `Trackers Per Page Load` = num(st[["Trackers Per Page Load"]]),
            `Tracking Requests Per Page Load` = num(st[["Tracking Requests Per Page Load"]]),
            `Trackers Requests / All Requests` = num(st[["Trackers Requests / All Requests"]], "%"),
            `Data Saved` = num(st[["Data Saved"]], "MB")
        )
        for (tr in payload$trackers) {
            cat_ <- if (is.null(tr$category)) "Unknown" else tr$category
            row[[cat_]] <- (row[[cat_]] %||% 0L) + 1L
        }
        out[[i]] <- row
        if (i %% 10000 == 0) message(sprintf("  %s/%s", i, length(files)))
    }
    rbindlist(out, fill = TRUE)[]
}

`%||%` <- function(x, y) if (is.null(x)) y else x

# Join the panel's visits to the domain measures and aggregate to the person.
#
# NA policy (scripts/missing_data.md):
#   unscanned domain  -> contributes 0 to the numerator, stays in the
#                        denominator. The paper's stated floor.
#   WTM absent        -> not zero. Domains with no telemetry at all are dropped
#                        before the join; who_* rates divide by WTM-covered
#                        visits, never by all visits.
#   zero-exposure     -> panelists whose visits all landed on unscanned domains
#                        are genuine zero observations and are kept (N = 1,134).

suppressPackageStartupMessages(library(data.table))

AL_THRESHOLDS <- c(1, 3, 5, 10)

build_person_level <- function(bl, wtm) {
    visits <- visit_panel()
    visits <- visits[!is.na(private_domain)]

    bl <- as.data.table(bl)
    bl[, private_domain := gsub("_", ".", filename, fixed = TRUE)]
    bl_cols <- setdiff(names(bl), c("filename", "private_domain"))

    # Absence of telemetry is not a measured zero, so drop those rows outright;
    # within a domain WTM did measure, a missing category *is* zero.
    wtm <- as.data.table(wtm)
    stat_cols <- c("Trackers Per Page Load", "Tracking Requests Per Page Load",
                   "Trackers Requests / All Requests", "Data Saved")
    wtm <- wtm[rowSums(!is.na(wtm[, ..stat_cols])) > 0]
    wtm_cols <- setdiff(names(wtm), "domain_name")
    for (j in wtm_cols) set(wtm, which(is.na(wtm[[j]])), j, 0)
    setnames(wtm, "domain_name", "private_domain")
    setnames(wtm, wtm_cols, paste0("who_", make_clean(wtm_cols)))
    wtm_cols <- paste0("who_", make_clean(wtm_cols))

    d <- merge(visits, bl[, c("private_domain", bl_cols), with = FALSE],
               by = "private_domain", all.x = TRUE)
    d <- merge(d, wtm, by = "private_domain", all.x = TRUE)

    d[, who_covered := as.integer(!is.na(`who_trackers_per_page_load`))]
    # Visit-weight every domain-level measure, then sum over the person.
    for (j in c(bl_cols, wtm_cols)) set(d, NULL, j, d[[j]] * d$visits)

    person <- d[, c(
        list(tt_visits = sum(visits), tt_domains = uniqueN(private_domain),
             who_visits = sum(who_covered * visits)),
        lapply(.SD, function(x) sum(x, na.rm = TRUE))
    ), by = caseid, .SDcols = c(bl_cols, wtm_cols)]
    setnames(person, bl_cols, paste0("bl_", bl_cols))

    person[, who_coverage := who_visits / tt_visits]
    for (m in paste0("bl_", bl_cols)) {
        set(person, NULL, paste0(m, "_rate"), person[[m]] / person$tt_visits)
        for (k in AL_THRESHOLDS)
            set(person, NULL, sprintf("%s_al%d", m, k), person[[m]] >= k)
    }
    for (m in wtm_cols) {
        denom <- fifelse(person$who_visits == 0, NA_real_, as.numeric(person$who_visits))
        set(person, NULL, paste0(m, "_rate"), person[[m]] / denom)
        for (k in AL_THRESHOLDS)
            set(person, NULL, sprintf("%s_al%d", m, k), person[[m]] >= k)
    }

    prof <- fread(FP_YG_PROFILE)
    prof[, `:=`(
        gender_lab = c("Male", "Female")[gender],
        race_lab   = c("White","Black","Hispanic","Asian","Other","Other","Other","Other")[race],
        educ_lab   = c("HS or Below","HS or Below","Some college","Some college",
                       "College","Postgrad")[educ],
        agegroup_lab = agegroup_from_birthyr(birthyr)
    )]
    merge(person, prof, by = "caseid", all.x = TRUE)[]
}

# janitor-style: lowercase, non-alphanumeric runs to single underscores.
make_clean <- function(x) {
    x <- tolower(gsub("[^A-Za-z0-9]+", "_", x))
    sub("_+$", "", sub("^_+", "", x))
}


# ---------------------------------------------------------------------------
# The visit panel
# ---------------------------------------------------------------------------
# Built from realityMine_web, which is the complete browsing record: every one
# of the 167,894 person-domain pairs in the desktop and mobile files appears in
# it, with identical durations, and it is never short on page records (equal on
# 84% of pairs, more on the rest). The device files are strict subsets.
#
# The committed yg_ind_domain.csv was built by summing all three, which counts
# the same browsing twice under two different units -- web contributes one row
# per page record, the device files one per session. The identity
#   yg_visits == web_page_records + device_session_rows
# holds for 100.00% of pairs, and yg_duration == web + device duration likewise,
# so every published rate carried a denominator inflated by ~42% (6,236,834
# against the true 4,398,822) and mixing pages with sessions. Levels were
# therefore ~2% low; the demographic gaps are unaffected because the inflation
# is close to proportional within a person.
FP_WEB_VISITS <- file.path(DATA_DIR, "yg",
                           "realityMine_web_2022-06-01_2022-06-30.csv")

build_visit_panel <- function() {
    if (!file.exists(FP_WEB_VISITS))
        stop("missing ", basename(FP_WEB_VISITS), " -- the visit panel is built ",
             "from it.\n  It is restricted on Dataverse (doi:10.7910/DVN/VIV4TS):\n",
             "    curl -L -H \"X-Dataverse-key: $DATAVERSE_KEY\" \\\n",
             "      https://dataverse.harvard.edu/api/access/datafile/6797139 \\\n",
             "      -o ", FP_WEB_VISITS, call. = FALSE)
    message("Building visit panel from realityMine_web")
    v <- fread(FP_WEB_VISITS,
               select = c("caseid", "private_domain", "page_duration"),
               showProgress = FALSE)
    v <- v[!is.na(private_domain) & nzchar(private_domain)]
    v[, .(visits = .N, duration = sum(page_duration, na.rm = TRUE)),
      by = .(caseid, private_domain)]
}

# The 2 GB source is read once per run; every consumer gets its own copy so
# in-place mutation cannot corrupt the shared table.
.panel_cache <- new.env(parent = emptyenv())
visit_panel <- function() {
    if (is.null(.panel_cache$d)) .panel_cache$d <- build_visit_panel()
    copy(.panel_cache$d)
}
