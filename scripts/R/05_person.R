# 05_person.R
# Join panel visits to the domain measures and aggregate to the person.
# This is the paper's core analytic file: one row per panelist.

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

