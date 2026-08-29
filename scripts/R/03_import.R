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
parse_blacklight <- function(json_dir = bl_corpus()) {
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
# ---------------------------------------------------------------------------
# Scan corpora, stored as archives
# ---------------------------------------------------------------------------
# The two scan corpora are tens of thousands of small JSON files, which is a
# wasteful way to keep them: 64,072 WhoTracksMe records are 261 MB loose and
# 23 MB zipped. They are stored as archives and expanded into a per-session
# temporary directory on first use -- about ten seconds for either corpus,
# against a pipeline that runs in minutes.
#
# A loose directory, if one is present, wins: that keeps a working copy usable
# and lets the archive be the distribution format rather than a second thing to
# keep in step.
.corpus_cache <- new.env(parent = emptyenv())

corpus_dir <- function(dir, archive, label) {
    if (dir.exists(dir)) return(dir)
    key <- basename(archive)
    if (!is.null(.corpus_cache[[key]])) return(.corpus_cache[[key]])
    # GitHub rejects blobs over 100 MB, so an archive larger than that is
    # committed as `.part-aa`, `.part-ab`, ... and rejoined here. Splitting is
    # plain concatenation: the parts carry no headers of their own.
    parts <- sort(Sys.glob(paste0(archive, ".part-*")))
    if (!file.exists(archive) && !length(parts))
        stop("neither ", basename(dir), "/ nor ", key, " is present; ",
             "one of them carries the ", label, " scans", call. = FALSE)
    dest <- file.path(tempdir(), sub("\\.(zip|tar\\.gz)$", "", key))
    message(sprintf("Expanding %s", key))
    src <- archive
    if (!file.exists(archive)) {
        src <- file.path(tempdir(), key)
        if (!file.exists(src)) {
            con <- file(src, "wb")
            for (p in parts) writeBin(readBin(p, "raw", file.size(p)), con)
            close(con)   # must be flushed before untar reads it
        }
    }
    if (grepl("\\.zip$", key)) unzip(src, exdir = dest)
    else untar(src, exdir = dest)
    # Archives may or may not carry a top-level folder; find where the JSON went.
    hits <- list.files(dest, pattern = "\\.json$", recursive = TRUE, full.names = TRUE)
    if (!length(hits)) stop("no JSON found inside ", key, call. = FALSE)
    .corpus_cache[[key]] <- unique(dirname(hits))[1]
    .corpus_cache[[key]]
}

parse_whotracksme <- function(json_dir = wtm_corpus()) {
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
# Stored as parquet rather than the 2 GB CSV Dataverse ships: 183 MB for
# identical content, and because parquet is columnar the pipeline reads only the
# three or four columns it wants instead of parsing 27. Convert once with
# scripts/R/tools/csv_to_parquet.R if you have re-downloaded the CSV.
FP_WEB_VISITS <- file.path(DATA_DIR, "yg",
                           "realityMine_web_2022-06-01_2022-06-30.parquet")

# One place that knows how the visit source is stored, so switching formats does
# not mean editing every consumer.
read_web_visits <- function(cols) {
    if (!file.exists(FP_WEB_VISITS))
        stop("missing ", basename(FP_WEB_VISITS), ".\n",
             "  It is built from the restricted RealityMine visit file",
             " (doi:10.7910/DVN/VIV4TS, file 6797139):\n",
             "    Rscript scripts/R/tools/csv_to_parquet.R", call. = FALSE)
    as.data.table(arrow::read_parquet(FP_WEB_VISITS, col_select = all_of(cols)))
}

build_visit_panel <- function() {
    message("Building visit panel from realityMine_web")
    v <- read_web_visits(c("caseid", "private_domain", "page_duration"))
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

# ---------------------------------------------------------------------------
# The CPS benchmark
# ---------------------------------------------------------------------------
# Table 1 compares the panel against the population, and the projection rakes
# onto the same margins, so both need the ASEC. Deriving it here rather than
# reading a committed CSV means the margins cannot fall behind the category
# definitions they are supposed to share with the panel: the age and education
# cuts live in 01_constants.R next to the panel's own.
FP_ASEC_ZIP <- file.path(DATA_DIR, "cps", "asecpub22csv.zip")

.asec_cache <- new.env(parent = emptyenv())
cps_asec <- function() {
    if (!is.null(.asec_cache$d)) return(copy(.asec_cache$d))
    if (!file.exists(FP_ASEC_ZIP))
        stop("missing ", basename(FP_ASEC_ZIP), "; download the 2022 ASEC person ",
             "file from census.gov and place it there", call. = FALSE)
    d <- fread(cmd = sprintf("unzip -p %s pppub22.csv", shQuote(FP_ASEC_ZIP)),
               select = c("A_AGE", "A_SEX", "PEHSPNON", "PRDTRACE", "A_HGA", "MARSUPWT"),
               showProgress = FALSE)
    d <- d[A_AGE >= 18]

    # Some vintages carry two implied decimals on the weight. The weighted count
    # of adults has to land near the 2022 population, which is what says which
    # vintage this is.
    if (sum(d$MARSUPWT) > 1e9) d[, MARSUPWT := MARSUPWT / 100]
    stopifnot(sum(d$MARSUPWT) > 2.3e8, sum(d$MARSUPWT) < 2.8e8)

    d[, gender_lab := fifelse(A_SEX == 1, "Male", "Female")]
    # Hispanic takes precedence, matching Table 1's mutually exclusive races.
    d[, race_lab := fcase(PEHSPNON == 1, "Hispanic",
                          PRDTRACE == 1, "White",
                          PRDTRACE == 2, "Black",
                          PRDTRACE == 4, "Asian",
                          default = "Other")]
    stopifnot(all(d$A_HGA >= 31 & d$A_HGA <= 46))
    d[, educ_lab := as.character(cut(A_HGA, CPS_EDUC_BINS, labels = CPS_EDUC_LABELS))]
    d[, agegroup_lab := as.character(cut(A_AGE, CPS_AGE_BINS, labels = AGE_ORDER))]
    .asec_cache$d <- d
    copy(d)
}

# Weighted share of US adults in each category of the four Table 1 variables.
cps_margins <- function() {
    d <- cps_asec()
    tot <- sum(d$MARSUPWT)
    out <- rbindlist(lapply(c("gender", "race", "educ", "agegroup"), function(v) {
        col <- paste0(v, "_lab")
        s <- d[, .(cps_perc = 100 * sum(MARSUPWT) / tot), by = c(col)]
        setnames(s, col, "cat")
        stopifnot(abs(sum(s$cps_perc) - 100) < 0.1)
        s[, variable := v][, .(variable, cat, cps_perc)]
    }))
    out[, cps_perc := round(cps_perc, 3)][]
}

# The denominator the projection multiplies its shares by.
cps_adult_population <- function() sum(cps_asec()$MARSUPWT)
