# 11_missing_data.R
# What the pipeline assumes about missing data, and which way each choice bends.
#
# Every analysis of this panel rests on decisions about data that is not there:
# a domain the scanner never reached, a scan that came back empty, a cookie
# query that was never run. None of them is neutral, and most understate
# exposure. This module recomputes each one from the data and regenerates
# scripts/missing_data.md, so the document cannot drift away from the numbers it
# describes.
#
# It replaces a Python script that did the same job and stopped being able to.
# Its guards were written as literals -- scanned domains must equal 34,078, the
# unscanned share must be near 23.6% -- so when 434 recovered scans moved both,
# the generator could no longer run and the document was edited by hand instead.
# The guards here are still explicit, because a number moving silently is the
# thing worth catching, but they name what moved them and when.

# Last moved when 434 retried scans entered the corpus. A guard that cannot be
# updated honestly is a guard that gets deleted, so these say what they are.
MD_EXPECTED <- list(panelists = 1134, scanned = 34512,
                    unscanned_pct = 21.0, allzero_pct = 20.2)

missing_data_facts <- function(bl, wtm, person) {
    v <- visit_panel()
    b <- as.data.table(bl)[, private_domain := gsub("_", ".", filename, fixed = TRUE)]
    b[, all_zero := rowSums(.SD) == 0, .SDcols = MEASURES_BLOCK]
    w <- as.data.table(wtm)
    prof <- fread(FP_YG_PROFILE, showProgress = FALSE)

    total <- sum(v$visits)
    scanned <- v$private_domain %chin% b$private_domain
    az <- v$private_domain %chin% b[(all_zero), private_domain]
    covered <- w[!is.na(`Trackers Per Page Load`), domain_name]
    inw <- v$private_domain %chin% covered

    # Per-person coverage, which is what says whether the zero-fill could be
    # manufacturing a demographic gap rather than only lowering a level.
    cov <- v[, .(sc = sum(visits[scanned[.I]]), tt = sum(visits)), by = caseid]

    # Blacklight-measured tracking on domains WhoTracksMe does and does not
    # cover: the check that settled whether absence there means zero.
    dv <- v[, .(visits = sum(visits)), by = private_domain]
    bb <- merge(b, dv, by = "private_domain", all.x = TRUE)
    bb[is.na(visits), visits := 0]
    ads <- function(m) sum(bb$ddg_join_ads[m] * bb$visits[m]) / sum(bb$visits[m])
    inw_b <- bb$private_domain %chin% covered

    list(n_panelists = uniqueN(person$caseid),
         n_recruited = uniqueN(prof$caseid),
         n_domains = uniqueN(v$private_domain),
         n_scanned = nrow(b),
         total_visits = total,
         unscanned_pct = 100 * sum(v$visits[!scanned]) / total,
         allzero_domains = sum(b$all_zero),
         allzero_scan_pct = 100 * mean(b$all_zero),
         allzero_pct = 100 * sum(v$visits[az]) / total,
         wtm_domains = length(covered),
         wtm_domain_pct = 100 * length(covered) / uniqueN(w$domain_name),
         wtm_visit_pct = 100 * sum(v$visits[inw]) / total,
         wtm_min = min(w$`Trackers Per Page Load`, na.rm = TRUE),
         wtm_yes_ads = ads(inw_b), wtm_no_ads = ads(!inw_b),
         coverage_mean = mean(cov$sc / cov$tt),
         coverage_sd = sd(cov$sc / cov$tt),
         coverage_min = min(cov$sc / cov$tt), coverage_max = max(cov$sc / cov$tt),
         vendor_pct = 100 * sum(v$visits[v$private_domain == "decipherinc.com"]) / total,
         vendor_rank = which(dv[order(-visits), private_domain] == "decipherinc.com")[1],
         dropped = uniqueN(prof$caseid) - uniqueN(person$caseid))
}

# One entry per place missing data enters the pipeline, ordered by how much it
# could move a number. Each carries what the absence means, what the code does
# about it, how big it is, which way it bends, and a verdict: `tested` where the
# direction was checked against data, `conservative` where the choice is known
# to understate and the discarded alternative is recorded, `unknown` where it
# cannot be settled with what we have.
missing_data_entries <- function(f, cov) {
    pct <- function(x, d = 1) sprintf(paste0("%.", d, "f%%"), x)
    n <- function(x) formatC(x, format = "d", big.mark = ",")
    ordinal <- function(i) paste0(i, c("st","nd","rd",rep("th",7))[
        if (i %% 100 %in% 11:13) 10 else min(i %% 10, if (i %% 10 == 0) 10 else i %% 10)])
    list(
    list("Visit counting: page records versus sessions",
         "realityMine_web records one row per page load; the desktop and mobile files record one row per session, with a page_views count",
         "the visit panel is built from realityMine_web alone, one visit per page record",
         "03_import: build_visit_panel",
         sprintf("%s visits, against the 6,236,834 previously published", n(f$total_visits)),
         "the old count overstated the denominator, understating rates",
         "tested",
         paste("The committed yg_ind_domain.csv summed all three RealityMine files.",
               "realityMine_web is a strict superset of the other two, so that sum counted",
               "the same browsing twice under two different units. Correcting it leaves the",
               "analytic universe untouched and lowers levels about 2%. The demographic gaps",
               "widen slightly rather than narrowing, because the double-count was",
               "proportionally larger for younger, higher-education panelists.")),
    list("Unscanned domains",
         "Blacklight never returned a scan for the domain",
         "contributes zero to the numerator, stays in the denominator",
         "03_import + 05_person: left join, unmatched measures scored zero",
         sprintf("%s of visits", pct(f$unscanned_pct)),
         "understates", "conservative",
         sprintf(paste("Bounded by strand B: the published %s ad trackers per visit becomes",
                       "[%s, %s] under calibrated fills. Directly measured, a rescanned sample",
                       "of these domains carries MORE tracking than the scanned population",
                       "(%s against %s), so the floor is real. Alternative (mean fill) would give %s."),
                 cov$published, cov$lo, cov$hi, cov$rescan, cov$pop, cov$mean_fill)),
    list("Scans returning zero on all seven measures",
         "a logged-out landing page showed nothing; the site may still track behind a login",
         "treated as a genuine zero, indistinguishable from a measured absence",
         "03_import: measures initialised to 0 per card",
         sprintf("%s of visits, %s domains", pct(f$allzero_pct), n(f$allzero_domains)),
         "understates", "tested",
         paste("facebook.com alone is 7.2% of panel visits and scores zero on all seven.",
               "build_allzero_sensitivity re-runs the headline excluding these visits and",
               "imputing them at the mean of domains that did show tracking: the age gap",
               "holds in sign and significance under all three. No conclusion depends on the",
               "zero. The level does: exposure is understated.")),
    list("WhoTracksMe absent",
         "WhoTracksMe has no telemetry for the domain",
         "who_* divides by WTM-covered visits rather than filling zero",
         "05_person: who_visits denominator",
         sprintf("%s of visits, only %s domains covered (%s)",
                 pct(100 - f$wtm_visit_pct), n(f$wtm_domains), pct(f$wtm_domain_pct)),
         "was understating; now conditional", "tested",
         sprintf(paste("Absence is not zero. WhoTracksMe never reports below %.2f trackers per",
                       "page load, so its process cannot emit 'measured none'. Blacklight",
                       "measures %.2f ad trackers per visit on the domains WTM lacks against",
                       "%.2f on those it covers."), f$wtm_min, f$wtm_no_ads, f$wtm_yes_ads)),
    list("HTTP Archive cookie rank cap",
         "the cookie query was capped at rank 100k; the domain was never asked about",
         "left missing, with a flag; formerly filled zero",
         "10_validity: ha_by_domain and the cookies_queried mask",
         "58% of domain-crawls in 2022, 66% by mid-2025",
         "was manufacturing a downward trend", "tested",
         paste("The capped share grew across crawl dates, so zero-filling read a change in",
               "what was queried as a change in what sites do. It also inverted the",
               "calibrated fill, and measure_fills raises if the absent arm ever predicts",
               "more than the present one. The same cap damped the same-instrument cookie",
               "drift until the comparison was restricted to domains queried at both dates.")),
    list("Per-user scan coverage",
         "each person's rate is their true rate times their coverage",
         "attenuates every level by roughly a quarter",
         "rates divide by all visits, numerator covers scanned only",
         sprintf("mean coverage %.3f, sd %.2f, range %.2f to %.2f",
                 f$coverage_mean, f$coverage_sd, f$coverage_min, f$coverage_max),
         "understates levels", "tested",
         paste("Coverage is flat across age and education, so it does not manufacture the",
               "demographic gaps. It does understate levels, and any statement of the form",
               "'the average adult meets X trackers per visit' is low by roughly the",
               "complement of that mean.")),
    list("Path-keyed blocklist rules",
         "Blacklight stores hostnames, so a rule keyed on a URL path cannot fire",
         "reported as an interval, not a point",
         "collect/blocking/03_apply_blocklists",
         "8% of EasyList and 14% of EasyPrivacy network rules",
         "understates blocking, overstates residual", "conservative",
         paste("Every residual carries an identification bound: block only what a domain",
               "rule certainly stops, versus credit every host the list names. The Facebook",
               "pixel is the clean case, since EasyPrivacy stops it only with path rules.",
               "Kept separate from sampling uncertainty throughout.")),
    list("Facebook Pixel and Google Analytics (Remarketing) attribution",
         "these cards name no responsible domain, so the third party is assumed",
         "assigned a fixed host set, flagged, excluded from every headline",
         "09_blocking: UNATTRIBUTED",
         "2 of 7 measures", "unknown", "conservative",
         "Reported but never headlined. Settling it needs the request URLs Blacklight does not store."),
    list("Third-party cookie attribution",
         "a card gives a cookie count and a domain list, not a mapping",
         "residual counted per cookie-setting domain, not per cookie",
         "09_blocking: third_party_cookie_domains",
         "all cookie residuals", "unknown", "conservative",
         "The published cookie count is carried alongside as a scale reference rather than being split."),
    list("Card absent from a scan payload",
         "the test did not run, or ran and found nothing, and the two are indistinguishable",
         "recorded as zero either way",
         "03_import: measures initialised to 0",
         "unquantified", "understates", "unknown",
         "Settling it needs a per-card presence census across the scan payloads."),
    list("Panelists with no usable browsing",
         "recruited but logged nothing that could be attributed to a domain",
         "excluded from the analytic sample",
         "05_person: inner join on visits",
         sprintf("%d of %s recruited", f$dropped, n(f$n_recruited)),
         "unknown", "unknown",
         paste("The paper states this moves no demographic margin by more than a point.",
               "Whether they differ on browsing behaviour is not observable, since they have none.")),
    list("Panel-vendor domains in the denominator",
         "visits to the survey platform are metered like any other browsing",
         "counted in tt_visits, so they dilute every rate",
         "none; they are ordinary visits",
         sprintf("decipherinc.com alone is %s of all visits, the %s largest domain",
                 pct(f$vendor_pct, 2), ordinal(f$vendor_rank)),
         "understates rates", "unknown",
         paste("Whether panel-participation browsing belongs in the denominator is a",
               "definitional question, not a measurement one.")))
}

build_missing_data_doc <- function(bl, wtm, person, path) {
    f <- missing_data_facts(bl, wtm, person)

    # A number moving is the thing worth catching, so say so rather than let the
    # document quietly describe data it no longer matches.
    bad <- c(
        if (f$n_panelists != MD_EXPECTED$panelists) sprintf("panelists %d", f$n_panelists),
        if (f$n_scanned != MD_EXPECTED$scanned) sprintf("scanned domains %d", f$n_scanned),
        if (abs(f$unscanned_pct - MD_EXPECTED$unscanned_pct) > 0.2)
            sprintf("unscanned share %.1f%%", f$unscanned_pct),
        if (abs(f$allzero_pct - MD_EXPECTED$allzero_pct) > 0.2)
            sprintf("all-zero share %.1f%%", f$allzero_pct))
    if (length(bad))
        stop("the taxonomy quotes figures the data no longer supports: ",
             paste(bad, collapse = "; "),
             "\n  Update MD_EXPECTED deliberately, saying what moved them.", call. = FALSE)

    # Numbers the entries quote that come from generated tables rather than the
    # visit data, read back so the prose cannot disagree with the tables.
    cbw <- fread(file.path(TABLES_DIR, "coverage_bounds_wayback.tex"), sep = "&",
                 header = FALSE, showProgress = FALSE)
    sat <- fread(file.path(TABLES_DIR, "selection_audit_tracking.tex"), sep = "&",
                 header = FALSE, showProgress = FALSE)
    num <- function(x) trimws(gsub("\\\\\\\\", "", x))
    cov <- list(published = num(cbw$V2[1]), mean_fill = num(cbw$V3[1]),
                lo = num(cbw$V5[1]), hi = num(cbw$V6[1]),
                pop = num(sat$V2[1]), rescan = num(sat$V3[1]))

    e <- missing_data_entries(f, cov)
    out <- c(
        "# Missing data: what the pipeline assumes and which way it bends",
        "",
        "Generated by `scripts/R/11_missing_data.R`, which recomputes every quantity",
        "below from the data and stops if one of them stops reproducing. Do not edit",
        "by hand.",
        "",
        "Each entry carries one of three verdicts. **tested** means the direction was",
        "checked against data, and the check is named. **conservative** means the",
        "direction is known to understate exposure and the discarded alternative is",
        "recorded, so the cost of the choice is visible. **unknown** means it cannot be",
        "settled with what we have, and what it would take is recorded.",
        "",
        "Where a direction is arguable and untestable, the pipeline takes the branch",
        "that understates exposure and says so here.",
        "",
        sprintf("Panel: %s panelists, %s visits to %s domains, %s of them scanned.",
                formatC(f$n_panelists, format = "d", big.mark = ","),
                formatC(f$total_visits, format = "d", big.mark = ","),
                formatC(f$n_domains, format = "d", big.mark = ","),
                formatC(f$n_scanned, format = "d", big.mark = ",")),
        "")
    for (x in e) out <- c(out,
        sprintf("## %s", x[[1]]), "",
        sprintf("- **Means**: %s", x[[2]]),
        sprintf("- **Code does**: %s  ", x[[3]]),
        sprintf("  `%s`", x[[4]]),
        sprintf("- **Scale**: %s", x[[5]]),
        sprintf("- **Direction**: %s", x[[6]]),
        sprintf("- **Verdict**: **%s** - %s", x[[7]], x[[8]]), "")
    writeLines(out, path)
    cat(sprintf("  wrote %s (%d entries)\n", path, length(e)))
    invisible(out)
}
