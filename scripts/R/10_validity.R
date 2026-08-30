# 10_validity.R
# What the design cannot see, measured rather than assumed.
#
# Two features of this study invite doubt: browsing was observed in June 2022
# but Blacklight scanned in ~January 2025, and scans completed for only ~53% of
# unique domains (~76% of visits). Neither is settled by argument. Each strand
# below answers one of them against an instrument that does not share
# Blacklight's failure modes.
#
#   A  timing    HTTP Archive crawled the same domains at both dates, so the
#                2022->2025 change can be measured instead of assumed away.
#   B  coverage  Unscanned visits currently count as zero tracking. Replacing
#                that with measurement bounds what the zero-fill costs.
#   C  agreement Where two instruments measure the same domain at the same
#                time, do they agree? Sets the scale for everything in A and B.
#   D  selection What the unscanned half actually is -- dead sites would be
#                harmless, live user-facing content would not.
#
# Collection stays in Python and is pinned: the BigQuery extracts, the Wayback
# fetch, the rescans. This module reads their outputs and does the analysis.

FP_ERROR_LOG <- file.path(DATA_DIR, "blacklight_errors.log")
# The scan corpus normally lives in the archive, not a loose directory, so
# resolve it through bl_corpus() rather than by path. Reading the bare path
# returns nothing when the directory is absent, and "no scans" is
# indistinguishable here from "no domain was scanned".
FP_BL_JSON <- function() bl_corpus()
AUDIT_DIR <- file.path(DATA_DIR, "selection_audit")
HA_DIR <- file.path(DATA_DIR, "httparchive")
WB_DIR <- file.path(DATA_DIR, "wayback")

# ---------------------------------------------------------------------------
# D. Why the unscanned domains went unscanned
# ---------------------------------------------------------------------------
# A domain missing from the scans is only a threat if it was a real page a real
# person read. The scraper's error log distinguishes the cases, and the
# distinction matters: a bot wall means the site is alive and refusing an
# automated visitor, while a network error is a property of our scraper and
# says nothing about the domain at all.
FAILURE_PATTERNS <- list(
    api_network_error = "^Request failed for (\\S+): ",
    empty_groups      = "^'groups' key is missing or empty for (\\S+)\\.",
    site_unreachable  = "^Website unreachable: (\\S+)\\. Skipping"
)

FAILURE_LABELS <- c(
    empty_groups      = "Scan returned nothing (bot wall / JS challenge / non-HTML)",
    api_network_error = "Scraper-to-API network failure (not a domain property)",
    site_unreachable  = "Site unreachable at scan time",
    not_in_error_log  = "No error recorded (failure reason unknown)"
)

parse_scan_errors <- function() {
    lines <- readLines(FP_ERROR_LOG, warn = FALSE)
    # Internationalised domains put undecodable bytes in the log. Python read it
    # with errors="replace"; do the same rather than dropping the lines, so the
    # counts below cover every failure the scraper recorded.
    lines <- iconv(lines, "UTF-8", "UTF-8", sub = "\uFFFD")
    lines <- lines[nzchar(trimws(lines))]
    reason <- rep(NA_character_, length(lines))
    domain <- rep(NA_character_, length(lines))
    for (r in names(FAILURE_PATTERNS)) {
        hit <- is.na(reason) & grepl(FAILURE_PATTERNS[[r]], lines)
        reason[hit] <- r
        domain[hit] <- sub(paste0(FAILURE_PATTERNS[[r]], ".*$"), "\\1", lines[hit])
    }
    ok <- !is.na(reason)
    cat(sprintf("  error log: %s lines, %s matched, %s unmatched\n",
                format(length(lines), big.mark = ","), format(sum(ok), big.mark = ","),
                format(sum(!ok), big.mark = ",")))
    # Later lines win, as the Python dict assignment did: a domain retried and
    # failing differently is recorded by its last failure.
    d <- data.table(private_domain = sub("\\.$", "", domain[ok]), reason = reason[ok])
    unique(d, by = "private_domain", fromLast = TRUE)
}

# Scan success against domain reach. This lived as a hand-typed table in the
# manuscript and silently kept its pre-correction numbers through both the
# visit-panel fix and the 434-scan recovery, so it is generated here now.
REACH_THRESHOLDS <- c(1L, 2L, 5L, 10L, 50L, 100L)

# The April 2026 rescan of the 500 widest-reach domains. Hand-typed in the
# manuscript until now; it reproduced exactly when checked, but so should have
# the reach table next to it.
FP_BL_JSON_2026 <- file.path(DATA_DIR, "blacklight_json_2026")
RESCAN_ORDER <- c("ddg_join_ads", "third_party_cookies", "fb_pixel",
                  "session_recording", "key_logging", "canvas_fingerprinting",
                  "google_analytics")
RESCAN_LABELS <- c("Ad trackers", "Third-party cookies", "Facebook Pixel",
                   "Session recording", "Key logging", "Canvas fingerprinting",
                   "Google Analytics")

# The retry pass. parse_blacklight marks these by the `domain_name` key their
# payloads carry and the first pass's never did; it selects the same 434
# domains as diffing the corpus against its pre-retry state in git.
#
# An earlier version defined them as the error log intersected with the corpus.
# That was checked while a stray directory had reduced the corpus to exactly
# these 434 files, so the test was circular and passed. On the whole corpus the
# intersection is 987, because a domain can fail once and be scanned later
# without the retry pass being what reached it.
register_retry_pass <- function(bl, visits) {
    rec_files <- attr(bl, "recovered")
    if (is.null(rec_files))
        stop("parse_blacklight did not mark the recovered scans", call. = FALSE)
    rec <- gsub("_", ".", rec_files, fixed = TRUE)
    bl <- copy(as.data.table(bl))
    bl[, recovered := filename %chin% rec_files]
    v <- as.data.table(visits)
    num("RetryRecovered", tex_num(length(rec)))
    num("RetryVisitShare",
        100 * v[private_domain %chin% rec, sum(visits)] / v[, sum(visits)])
    num("RetryAdTrackers",   bl[recovered == TRUE,  mean(ddg_join_ads)])
    num("FirstPassAdTrackers", bl[recovered == FALSE, mean(ddg_join_ads)])
    cat(sprintf("  retry pass: %d recovered, %.1f vs %.1f ad trackers per domain\n",
                length(rec), bl[recovered == TRUE, mean(ddg_join_ads)],
                bl[recovered == FALSE, mean(ddg_join_ads)]))
    invisible(rec)
}

build_rescan_drift <- function(bl, visits, path) {
    n26 <- parse_blacklight(FP_BL_JSON_2026)
    m <- merge(bl, n26, by = "filename", suffixes = c("_25", "_26"))
    if (nrow(m) != nrow(n26))
        stop("rescan drift: ", nrow(n26) - nrow(m), " rescanned domains are ",
             "absent from the January corpus", call. = FALSE)
    cat(sprintf("  rescan drift: %d domains matched in both scans\n", nrow(m)))

    # What the rescanned 500 cover, which the text reports alongside the table.
    d500 <- gsub("_", ".", n26$filename, fixed = TRUE)
    v <- as.data.table(visits)
    num("RescanN", tex_num(nrow(n26)))
    num("RescanPanelistShare",
        100 * v[private_domain %chin% d500, uniqueN(caseid)] / v[, uniqueN(caseid)])
    num("RescanVisitShare",
        100 * v[private_domain %chin% d500, sum(visits)] / v[, sum(visits)])
    num("RescanTimeShare",
        100 * v[private_domain %chin% d500, sum(duration)] / v[, sum(duration)])

    rows <- lapply(seq_along(RESCAN_ORDER), function(i) {
        a <- m[[paste0(RESCAN_ORDER[i], "_25")]] > 0
        b <- m[[paste0(RESCAN_ORDER[i], "_26")]] > 0
        data.frame(measure = RESCAN_LABELS[i],
                   jan = sprintf("%.1f", 100 * mean(a)),
                   apr = sprintf("%.1f", 100 * mean(b)),
                   chg = sprintf("$%+.1f$", 100 * (mean(b) - mean(a))),
                   agree = sprintf("%.1f", 100 * mean(a == b)),
                   persist = sprintf("%.1f", 100 * mean(b[a])),
                   stringsAsFactors = FALSE)
    })
    write_tex(do.call(rbind, rows), path)
    invisible(m)
}

build_scan_by_reach <- function(visits, path) {
    dom <- as.data.table(visits)[, .(reach = uniqueN(caseid), visits = sum(visits)),
                                 by = private_domain]
    scanned <- sub("\\.json$", "", list.files(FP_BL_JSON(), pattern = "\\.json$"))
    dom[, scanned := gsub(".", "_", private_domain, fixed = TRUE) %chin% scanned]

    rows <- lapply(REACH_THRESHOLDS, function(t) {
        s <- dom[reach >= t]
        data.frame(threshold = sprintf("$\\geq %d$ panelist%s", t,
                                       if (t == 1L) "" else "s"),
                   n = formatC(nrow(s), format = "d", big.mark = ","),
                   pct = sprintf("%.1f\\%%", 100 * mean(s$scanned)),
                   stringsAsFactors = FALSE)
    })
    write_tex(do.call(rbind, rows), path)

    # The surrounding prose quotes these.
    num("ScansCompleted", tex_num(sum(dom$scanned)))
    num("DomainsTotal",   format(nrow(dom), big.mark = ","))
    num("ScanDomainShare", 100 * mean(dom$scanned))
    num("VisitsScanned",  tex_num(dom[scanned == TRUE, sum(visits)]))
    num("VisitsTotal",    tex_num(sum(dom$visits)))
    num("VisitsMillions", sum(dom$visits) / 1e6)
    num("ScanVisitCoverage",
        100 * dom[scanned == TRUE, sum(visits)] / sum(dom$visits))
    num("ReachTopShare", 100 * mean(dom[reach >= 100]$scanned))
    num("ReachTenShare", 100 * mean(dom[reach >= 10]$scanned))
    num("ReachTopN", tex_num(nrow(dom[reach >= 100])))
    cat(sprintf("  scan-by-reach: %s of %s domains scanned (%.1f%%); ",
                format(sum(dom$scanned), big.mark = ","),
                format(nrow(dom), big.mark = ","), 100 * mean(dom$scanned)))
    cat(sprintf("visit coverage %s of %s (%.1f%%)\n",
                format(dom[scanned == TRUE, sum(visits)], big.mark = ","),
                format(sum(dom$visits), big.mark = ","),
                100 * dom[scanned == TRUE, sum(visits)] / sum(dom$visits)))
    invisible(dom)
}

build_scan_failure_reasons <- function(visits, path) {
    dom <- as.data.table(visits)[, .(reach = uniqueN(caseid), visits = sum(visits)),
                                 by = private_domain]
    scanned <- sub("\\.json$", "", list.files(FP_BL_JSON(), pattern = "\\.json$"))
    dom[, scanned := gsub(".", "_", private_domain, fixed = TRUE) %chin% scanned]

    un <- merge(dom[!(scanned)], parse_scan_errors(), by = "private_domain", all.x = TRUE)
    un[is.na(reason), reason := "not_in_error_log"]
    num("UnscannedDomains", tex_num(nrow(un)))
    cat(sprintf("  unscanned domains: %s (%.1f%% of visits)\n",
                format(nrow(un), big.mark = ","),
                100 * sum(un$visits) / sum(dom$visits)))

    comp <- un[, .(n_domains = .N, visits = sum(visits)), by = reason]
    comp <- comp[match(names(FAILURE_LABELS), reason)]
    comp <- comp[!is.na(n_domains)]
    out <- data.frame(
        reason = FAILURE_LABELS[comp$reason],
        n = format(comp$n_domains, big.mark = "", trim = TRUE),
        v = format(comp$visits, big.mark = "", trim = TRUE),
        pct_dom = sprintf("%.1f", 100 * comp$n_domains / nrow(un)),
        pct_unscanned_visits = sprintf("%.1f", 100 * comp$visits / sum(un$visits)),
        pct_all_visits = sprintf("%.1f", 100 * comp$visits / sum(dom$visits)),
        stringsAsFactors = FALSE)
    out$n <- formatC(comp$n_domains, format = "d", big.mark = ",")
    out$v <- formatC(comp$visits, format = "d", big.mark = ",")
    write_tex(out, path)
    invisible(out)
}

# Was the unscanned half actually alive in June 2022? A domain Blacklight could
# not scan in 2025 is only a threat to the estimates if it was a live page in
# 2022, so ask two independent instruments that were watching then: HTTP
# Archive's June-2022 crawl, and whether the Wayback Machine holds a snapshot.
# The second row restricts to domains where at least one of them actually
# looked, because "no snapshot" and "never queried" are not the same evidence.
FP_HA_MEASURES <- file.path(HA_DIR, "ha_domain_measures.csv")

# HTTP Archive crawls each domain twice, desktop and mobile, so anything using
# it at the domain level has to combine the two.
#
# The only measure that is ever missing is third_party_cookies, and it is
# missing exactly when cookies_queried is 0 -- the rank-capped cookie query
# never asked. Missingness is therefore a property of the *query*, never of the
# domain: it never means "asked and found none". So a domain queried on one
# client has been measured, and dropping it because the other client was not
# asked would let the query's coverage masquerade as the data -- the same error
# as the rank-cap zero-fill that once manufactured a downward cookie trend.
# Averaging over the clients that did measure is the honest reading; a domain
# neither client was asked about stays missing, which is what "HTTP Archive
# never measured this" has to mean downstream.
#
# This bites on 101 of 13,878 domains. Where both clients were queried they
# agree closely (Spearman 0.92, median absolute difference 0), so one client
# stands in for the domain acceptably.
ha_by_domain <- function(ha, keys, label = "") {
    if ("cookies_queried" %in% names(ha) && "third_party_cookies" %in% names(ha)) {
        bad <- sum(is.na(ha$third_party_cookies) != (ha$cookies_queried == 0))
        if (bad) stop("missing cookie values no longer mean 'never queried' (",
                      bad, " rows disagree); the skip-missing average below ",
                      "would then be discarding real measurements")
    }
    out <- ha[, lapply(.SD, function(x)
        if (all(is.na(x))) NA_real_ else mean(x, na.rm = TRUE)),
        by = private_domain, .SDcols = keys]

    # Say out loud how much is being skipped, and on how many domains the choice
    # actually changes the answer: those measured on one client but not the
    # other. Everything else is missing on both clients or neither, where
    # skipping and propagating agree.
    for (k in intersect(keys, names(ha))) {
        na_rows <- sum(is.na(ha[[k]]))
        if (!na_rows) next
        per <- ha[, .(n = .N, m = sum(!is.na(get(k)))), by = private_domain]
        cat(sprintf("  %s%s: %s of %s crawl rows missing; %s domains fully missing, %s mixed across clients\n",
                    if (nzchar(label)) paste0(label, " ") else "", k,
                    format(na_rows, big.mark = ","), format(nrow(ha), big.mark = ","),
                    format(sum(per$m == 0), big.mark = ","),
                    format(sum(per$m > 0 & per$m < per$n), big.mark = ",")))
    }
    out
}
FP_WB_MANIFEST <- file.path(WB_DIR, "wb_manifest.csv")

build_wb_liveness <- function(visits, bl, path) {
    ha <- fread(FP_HA_MEASURES, showProgress = FALSE)
    wb <- fread(FP_WB_MANIFEST, showProgress = FALSE)

    dom <- as.data.table(visits)[, .(visits = sum(visits)), by = private_domain]
    dom[, filename := gsub(".", "_", private_domain, fixed = TRUE)]
    dom[, bl_scanned := filename %chin% bl$filename]
    dom[, ha22 := private_domain %chin% unique(ha[crawl == "panel", private_domain])]
    dom[, wb_hit := private_domain %chin% wb[as.logical(cdx_hit), private_domain]]
    dom[, wb_checked := private_domain %chin% wb$private_domain]
    dom[, alive_2022 := ha22 | wb_hit]

    un <- dom[!(bl_scanned)]
    cat(sprintf("  BL-unscanned: %s domains (%.1f%% of visits)\n",
                format(nrow(un), big.mark = ","),
                100 * sum(un$visits) / sum(dom$visits)))

    row <- function(sub, label) c(
        label,
        formatC(nrow(sub), format = "d", big.mark = ","),
        sprintf("%.1f", 100 * sum(sub$visits) / sum(dom$visits)),
        sprintf("%.1f", 100 * mean(sub$alive_2022)),
        sprintf("%.1f", 100 * sum(sub$visits[sub$alive_2022]) / sum(sub$visits)))

    out <- as.data.frame(rbind(
        row(un, "all BL-unscanned"),
        row(un[ha22 | wb_checked], "BL-unscanned with a 2022 check (HA or WB queried)")
    ), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# D (continued). What the unscanned domains actually are
# ---------------------------------------------------------------------------
# 200 unscanned domains drawn in two strata -- 100 proportional to visits, 100
# uniform -- and coded against a written rubric. The visits stratum answers
# "what does the missing traffic consist of"; the uniform stratum answers "what
# do the missing domains consist of", and they differ sharply.
AUDIT_CATEGORIES <- c("content_site", "adtech_infrastructure", "cdn_api_host",
                      "parked_or_forsale", "adult_content", "dead", "unknown")
AUDIT_SEED <- 20250112
AUDIT_BOOT_SEED <- 20250114
PI_REPS <- 200000

# Wilson score interval, without continuity correction, matching statsmodels'
# proportion_confint(method="wilson"). Preferred to the normal approximation
# because several of these cells hold 0 or 1 successes out of 100.
wilson_ci <- function(k, n, z = qnorm(0.975)) {
    centre <- (k + z^2 / 2) / (n + z^2)
    half <- z / (n + z^2) * sqrt(k * (n - k) / n + z^2 / 4)
    c(centre - half, centre + half)
}

build_selection_audit_composition <- function(coded, path) {
    d <- as.data.table(coded)
    stopifnot(nrow(d) == 200, all(d$category %chin% AUDIT_CATEGORIES))

    cell <- function(sub, cat) {
        k <- sum(sub$category == cat); n <- nrow(sub)
        ci <- wilson_ci(k, n)
        c(as.character(k), sprintf("%.0f", 100 * k / n),
          sprintf("[%.0f, %.0f]", 100 * ci[1], 100 * ci[2]))
    }
    rows <- lapply(AUDIT_CATEGORIES, function(cat)
        c(gsub("_", "\\\\_", cat),
          cell(d[in_visits_stratum == TRUE], cat),
          cell(d[in_uniform_stratum == TRUE], cat)))
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    out <- out[order(-as.integer(out[[2]])), ]
    write_tex(out, path)
    invisible(out)
}

# The measures the rescan can speak to. Session recording, keylogging and canvas
# fingerprinting are too rare in 200 domains to estimate, so they stay out.
AUDIT_MEASURES <- c(ddg_join_ads = "Ad trackers",
                    third_party_cookies = "Third-party cookies",
                    fb_pixel = "Facebook Pixel",
                    google_analytics = "Google Analytics (Remarketing)")

# The visits stratum was drawn PPS *without* replacement: draw one domain
# proportional to visits, renormalise, repeat. An unweighted mean of that is
# unbiased only for PPS *with* replacement, so a design correction is needed.
#
# The inclusion probabilities of successive sampling have no closed form -- in
# particular they are not min(n*p_i, 1), which here sums to 91.1 rather than the
# 100 any fixed-size design must satisfy. Estimate them instead by simulating
# the design. Rather than redrawing 200,000 samples, use the exponential race:
# giving unit i an arrival time Exp(p_i) and taking the k earliest is exactly
# successive sampling, and it vectorises. (Checked numerically against numpy's
# sequential draw before being relied on here.)
simulate_inclusion <- function(pool, n_draw = 100, reps = PI_REPS, seed = AUDIT_SEED) {
    p <- pool$visits / sum(pool$visits)
    n <- length(p)
    set.seed(seed)
    cnt <- numeric(n)
    for (i in seq_len(reps)) {
        key <- rexp(n) / p
        thr <- sort.int(key, partial = n_draw)[n_draw]
        hit <- key <= thr
        cnt[hit] <- cnt[hit] + 1
    }
    pi <- cnt / reps
    if (abs(sum(pi) - n_draw) > 0.5)
        stop("simulated inclusion probabilities sum to ", round(sum(pi), 2),
             ", not ", n_draw, "; the simulated design is not the one that drew")
    cat(sprintf("  inclusion probabilities: sum %.3f (must be %d); ",
                sum(pi), n_draw))
    cat(sprintf("min(n*p,1) would give %.2f\n", sum(pmin(n_draw * p, 1))))
    setNames(pi, pool$private_domain)
}

# Hajek (ratio) form, the standard choice when the realised weights cannot sum
# to the known total -- here they cannot, because only 63 of the 100 drawn
# domains rescanned successfully. The estimate is therefore conditional on
# being scannable in 2026, which is this paper's own selection problem again and
# is not repaired by reweighting.
hajek <- function(y, w) sum(w * y) / sum(w)

build_selection_audit_tracking <- function(coded, visits, bl, path,
                                           figure_path = NULL,
                                           reps = PI_REPS, seed = AUDIT_BOOT_SEED) {
    keys <- names(AUDIT_MEASURES)
    d <- as.data.table(coded)
    yg <- as.data.table(visits)
    dom <- yg[, .(visits = sum(visits)), by = private_domain]
    dom[, filename := gsub(".", "_", private_domain, fixed = TRUE)]
    pop <- merge(dom, as.data.table(bl), by = "filename")

    ha <- fread(FP_HA_MEASURES, showProgress = FALSE)[crawl == "panel"]
    ha22 <- ha_by_domain(ha, keys)

    j <- merge(pop, ha22, by = "private_domain", all.x = TRUE, suffixes = c("", "_ha"))
    # Calibrated fills, visit-weighted exactly as the coverage bounds compute
    # them: what Blacklight measures on domains HTTP Archive saw as tracking,
    # versus on domains it saw as clean.
    fills <- lapply(keys, function(k) {
        m <- !is.na(j[[paste0(k, "_ha")]])
        pres <- m & j[[paste0(k, "_ha")]] > 0
        c("FALSE" = weighted.mean(j[[k]][m & !pres], j$visits[m & !pres]),
          "TRUE"  = weighted.mean(j[[k]][pres], j$visits[pres]))
    })
    names(fills) <- keys

    # The pool is the frame the sample was actually drawn from -- the domains
    # unscanned when the draw happened -- not whatever is unscanned today. A
    # later retry pass recovered scans for 11 of the 200 drawn domains, and
    # taking today's unscanned set would drop them out of a design whose
    # inclusion probabilities are defined on the frame they were drawn from.
    # What we now know about those 11 does not change what the population was.
    pool <- fread(file.path(AUDIT_DIR, "failure_reasons.csv"),
                  select = c("private_domain", "visits"), showProgress = FALSE)
    pool <- pool[, .(visits = sum(visits)), by = private_domain]
    pi <- simulate_inclusion(pool, reps = reps)
    pv <- setNames(pool$visits, pool$private_domain)

    now <- d[bl_scan_success == TRUE & in_visits_stratum == TRUE]
    uni <- d[bl_scan_success == TRUE & in_uniform_stratum == TRUE]
    w_ht <- unname(pv[now$private_domain] / pi[now$private_domain])
    cat(sprintf("  visits stratum: %d rescanned of 100 drawn\n", nrow(now)))

    hm <- as.data.table(ha22)[match(now$private_domain, private_domain)]
    set.seed(seed)
    rows <- lapply(keys, function(k) {
        x <- as.numeric(now[[paste0("bl_", k)]])
        draws <- vapply(seq_len(10000), function(i) {
            ix <- sample.int(length(x), length(x), replace = TRUE)
            hajek(x[ix], w_ht[ix])
        }, numeric(1))
        ci <- quantile(draws, c(.025, .975), names = FALSE)

        # The coverage bounds only ever fill domains HTTP Archive actually
        # measured, so the comparison has to be restricted to those, with the
        # direct estimate recomputed on the same subset -- otherwise the two
        # columns describe different sets of domains.
        meas <- !is.na(hm[[k]])
        pred <- mean(fills[[k]][as.character(hm[[k]][meas] > 0)])
        c(AUDIT_MEASURES[[k]],
          fmt2(weighted.mean(pop[[k]], pop$visits)),
          fmt2(hajek(x, w_ht)),
          sprintf("[%.2f, %.2f]", ci[1], ci[2]),
          fmt2(pred), fmt2(hajek(x[meas], w_ht[meas])),
          as.character(sum(meas)),
          fmt2(mean(as.numeric(uni[[paste0("bl_", k)]]))))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)

    # The comparison the strand exists to make: tracking measured directly on
    # the domains the paper had to zero-fill, against the population it did
    # measure. Bars above their neighbour mean the zero-fill understates.
    if (!is.null(figure_path)) {
        pl <- rbindlist(lapply(seq_along(keys), function(i) data.table(
            measure = AUDIT_MEASURES[[i]],
            arm = c("Scanned population (Jan 2025, visit-weighted)",
                    "Unscanned audit sample (rescanned Jul 2026)"),
            value = as.numeric(c(out[i, 2], out[i, 3])))))
        pl[, measure := factor(measure, levels = unname(AUDIT_MEASURES))]
        g <- ggplot(pl, aes(measure, value, fill = arm)) +
            geom_col(position = position_dodge(width = .7), width = .62) +
            scale_fill_manual(values = c(C_NULL, C_SIGNIFICANT), name = NULL) +
            scale_y_continuous(expand = expansion(mult = c(0, .08))) +
            labs(x = NULL, y = "Mean per visit-weighted domain") +
            theme_blacklight(grid = "y") +
            theme(legend.position = "bottom",
                  axis.text.x = element_text(angle = 20, hjust = 1))
        save_fig(g, figure_path, width = FIG_FULL_W, height = 3.4)
    }
    invisible(out)
}

# ---------------------------------------------------------------------------
# Does the concentration result survive into the unscanned mass?
# ---------------------------------------------------------------------------
# The concentration figure rests on scanned domains, where unscanned visits were
# zero-filled -- which can only understate Google's reach. Here it is measured
# instead: of the audit sample's July-2026 rescans, what share load at least one
# third-party host Tracker Radar attributes to Google LLC? The same statistic
# over the Jan-2025 scanned population is the comparison.
FP_AUDIT_JSON <- file.path(DATA_DIR, "blacklight_json_audit")

build_google_reach_audit <- function(third_parties, visits, path) {
    cats <- fread(file.path(DATA_DIR, "tracker_lists", "ddg_categories.csv"),
                  showProgress = FALSE)
    goog <- unique(cats[owner == "Google LLC", domain])
    cat(sprintf("  Google LLC domains in Tracker Radar: %d\n", length(goog)))

    scanned <- gsub("_", ".", sub("\\.json$", "",
                    list.files(FP_BL_JSON(), pattern = "\\.json$")), fixed = TRUE)
    tp <- as.data.table(third_parties)
    hit <- unique(tp[tp_domain %chin% goog, private_domain])
    v <- as.data.table(visits)[, .(visits = sum(visits)), by = private_domain]
    pop <- data.table(private_domain = scanned)
    pop[, google := private_domain %chin% hit]
    pop[, visits := v$visits[match(private_domain, v$private_domain)]]
    pop[is.na(visits), visits := 0]
    share <- weighted.mean(pop$google, pop$visits)

    # The rescans live in their own directory, so the same extraction is run
    # over them rather than assuming the audit domains appear above.
    aud <- extract_third_parties(FP_AUDIT_JSON)
    aud_hit <- unique(aud[tp_domain %chin% goog, private_domain])
    scanned_now <- gsub("_", ".", sub("\\.json$", "",
                        list.files(FP_AUDIT_JSON, pattern = "\\.json$")), fixed = TRUE)

    s <- fread(file.path(AUDIT_DIR, "audit_sample.csv"), showProgress = FALSE)
    s[, scanned_now := private_domain %chin% scanned_now]
    s[, google := private_domain %chin% aud_hit]

    rows <- list(c("Scanned population, Jan 2025 (visit-weighted)",
                   sprintf("%.1f", 100 * share),
                   formatC(nrow(pop), format = "d", big.mark = ","), "--"))
    for (st in c("in_visits_stratum", "in_uniform_stratum")) {
        sub <- s[get(st) == TRUE & scanned_now == TRUE]
        k <- sum(sub$google); n <- nrow(sub); ci <- wilson_ci(k, n)
        rows[[length(rows) + 1]] <- c(
            sprintf("Unscanned sample, %s stratum (scanned Jul 2026)",
                    if (st == "in_visits_stratum") "visits" else "uniform"),
            sprintf("%.1f", 100 * k / n), as.character(n),
            sprintf("[%.0f, %.0f]", 100 * ci[1], 100 * ci[2]))
    }
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# C. Do two instruments agree where they measure the same thing?
# ---------------------------------------------------------------------------
# Everything in strands A and B leans on HTTP Archive standing in for
# Blacklight. That is only licensed if the two agree where both looked at the
# same domain at the same date. Where they disagree, the construct difference
# is named in the row label rather than smoothed over: HTTP Archive sees
# header-set cookies only, and GA presence is not GA remarketing.
HA_BL_PAIRS <- list(
    c("ddg_join_ads_ha", "ddg_join_ads_bl", "Ad trackers (same construct)"),
    c("ddg_known_trackers", "ddg_join_ads_bl", "Any known tracker (HA) vs ad trackers (BL)"),
    c("third_party_cookies_ha", "third_party_cookies_bl",
      "3p cookies: header-set (HA) vs all (BL)"),
    c("fb_pixel_ha", "fb_pixel_bl", "FB requests (HA) vs FB pixel (BL)"),
    c("google_analytics_ha", "google_analytics_bl",
      "GA/GTM presence (HA) vs GA remarketing (BL)")
)

build_ha_bl_agreement <- function(bl, path) {
    m <- fread(FP_HA_MEASURES, showProgress = FALSE)
    ha <- m[crawl == "blacklight_match" & client == "mobile"]
    ha[, filename := gsub(".", "_", private_domain, fixed = TRUE)]
    j <- merge(ha, as.data.table(bl), by = "filename", suffixes = c("_ha", "_bl"))
    cat(sprintf("  domains measured by both instruments: %s\n",
                format(nrow(j), big.mark = ",")))

    rows <- lapply(HA_BL_PAIRS, function(p) {
        # Restrict each row to domains both instruments actually measured.
        # third_party_cookies is missing wherever HTTP Archive's rank-capped
        # query never asked, and "never asked" is not "asked and found none" --
        # treating it as zero would let one row's prevalence describe 6,902
        # domains while its correlation described 2,490.
        ok <- !is.na(j[[p[1]]]) & !is.na(j[[p[2]]])
        a <- j[[p[1]]][ok] > 0; b <- j[[p[2]]][ok] > 0
        c(p[3], formatC(sum(ok), format = "d", big.mark = ","),
          sprintf("%.1f", 100 * mean(a)), sprintf("%.1f", 100 * mean(b)),
          sprintf("%.1f", 100 * mean(a == b)),
          sprintf("%.2f", cor(j[[p[1]]][ok], j[[p[2]]][ok], method = "spearman")))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# Wayback recovers only what a static parse of the archived HTML can see, so it
# should undercount anything injected by JavaScript. That is the point of the
# comparison: it sets how much of a 2022 request map a static snapshot can
# stand in for, measured against HTTP Archive on domains both cover.
WB_HA_PAIRS <- list(
    c("ddg_join_ads", "Ad trackers (static subset vs full request map)"),
    c("ddg_known_trackers", "Any known tracker"),
    c("fb_pixel", "Facebook requests"),
    c("google_analytics", "Google Analytics/GTM"),
    c("n_third_parties", "Any third party")
)
FP_WB_MEASURES <- file.path(WB_DIR, "wb_domain_measures.csv")

build_wb_ha_agreement <- function(path) {
    keys <- vapply(WB_HA_PAIRS, `[`, character(1), 1)
    man <- fread(FP_WB_MANIFEST, showProgress = FALSE)
    wb <- fread(FP_WB_MEASURES, showProgress = FALSE)
    ha <- fread(FP_HA_MEASURES, showProgress = FALSE)[crawl == "panel"]
    ha22 <- ha_by_domain(ha, keys, "wb-ha")

    calib <- man[group == "calib_ha", private_domain]
    j <- merge(wb[private_domain %chin% calib], ha22, by = "private_domain",
               suffixes = c("_wb", "_ha"))
    cat(sprintf("  domains measured by both, June 2022: %s\n",
                format(nrow(j), big.mark = ",")))

    rows <- lapply(WB_HA_PAIRS, function(p) {
        w <- j[[paste0(p[1], "_wb")]]; h <- j[[paste0(p[1], "_ha")]]
        pw <- w > 0; ph <- h > 0
        c(p[2], formatC(nrow(j), format = "d", big.mark = ","),
          sprintf("%.1f", 100 * mean(pw)), sprintf("%.1f", 100 * mean(ph)),
          sprintf("%.1f", 100 * mean(pw == ph)),
          sprintf("%.1f", 100 * sum(pw & ph) / max(sum(ph), 1)),
          sprintf("%.2f", cor(w, h, method = "spearman")))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# A. Timing: how much did the web move between June 2022 and June 2025?
# ---------------------------------------------------------------------------
# Browsing was observed in June 2022; Blacklight scanned in ~January 2025. HTTP
# Archive crawled the same domains at both dates with one instrument, so the
# drift can be measured rather than assumed. Both an unweighted domain
# prevalence and a visit-weighted one, because the panel's traffic is
# concentrated and the two answer different questions.
HA_MEASURES <- list(
    c("ddg_join_ads", "Ad trackers"),
    c("third_party_cookies", "Third-party cookies (header-set)"),
    c("fb_pixel", "Facebook requests"),
    c("google_analytics", "Google Analytics/GTM"),
    c("ddg_known_trackers", "Any known tracker"),
    c("n_third_parties", "Any third party")
)
HA_CLIENTS <- c("desktop", "mobile")

build_httparchive_drift <- function(path) {
    m <- fread(FP_HA_MEASURES, showProgress = FALSE)
    tg <- fread(file.path(HA_DIR, "ha_targets.csv"), showProgress = FALSE)
    w <- setNames(tg$visits, tg$private_domain)

    rows <- list()
    for (cl in HA_CLIENTS) {
        a <- m[crawl == "panel" & client == cl]
        b <- m[crawl == "recent" & client == cl]
        shared <- intersect(a$private_domain, b$private_domain)
        a <- a[match(shared, private_domain)]; b <- b[match(shared, private_domain)]
        for (p in HA_MEASURES) {
            # The cookie measure is missing wherever the rank-capped query never
            # asked, and coverage is not stable across crawls -- 45.2% of matched
            # desktop domains were queried in 2022 against 36.3% in 2025. Reading
            # "never asked" as "found none" lets that shifting coverage
            # manufacture a decline, so restrict to domains queried in both.
            keep <- if (p[1] == "third_party_cookies")
                as.logical(a$cookies_queried) & as.logical(b$cookies_queried)
            else rep(TRUE, length(shared))
            pa <- a[[p[1]]][keep] > 0; pb <- b[[p[1]]][keep] > 0
            wt <- w[shared[keep]]; wt[is.na(wt)] <- 0
            rows[[length(rows) + 1]] <- c(
                cl, p[2], formatC(sum(keep), format = "d", big.mark = ","),
                sprintf("%.1f", 100 * mean(pa)), sprintf("%.1f", 100 * mean(pb)),
                sprintf("%.1f", 100 * (mean(pb) - mean(pa))),
                sprintf("%.1f", 100 * weighted.mean(pa, wt)),
                sprintf("%.1f", 100 * weighted.mean(pb, wt)),
                sprintf("%.1f", 100 * (weighted.mean(pb, wt) - weighted.mean(pa, wt))))
        }
    }
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# The same question at the level the paper's estimates actually use. Domain
# prevalence can move a lot while person-level exposure barely does, because
# people concentrate their browsing. Recomputing each panelist's rate under
# June-2022 and Jan-2025 measurements of the *same* domains separates a change
# in the web from a change in who browsed what.
TEMPORAL_MEASURES <- list(
    c("ddg_join_ads", "Ad trackers"),
    c("third_party_cookies", "Third-party cookies (header-set)"),
    c("fb_pixel", "Facebook requests"),
    c("google_analytics", "Google Analytics/GTM")
)

build_temporal_user_exposure <- function(visits, person, table_path, figure_path) {
    keys <- vapply(TEMPORAL_MEASURES, `[`, character(1), 1)
    ha <- fread(FP_HA_MEASURES, showProgress = FALSE)
    agg <- function(cr) ha_by_domain(ha[crawl == cr], c(keys, "cookies_queried"), cr)
    h22 <- agg("panel"); h25 <- agg("blacklight_match")
    matched <- intersect(h22$private_domain, h25$private_domain)
    cat(sprintf("  HA domains: %s in 2022, %s in 2025, %s matched\n",
                format(nrow(h22), big.mark = ","), format(nrow(h25), big.mark = ","),
                format(length(matched), big.mark = ",")))

    yg <- as.data.table(visits)
    setnames(h22, setdiff(names(h22), "private_domain"),
             paste0("a_", setdiff(names(h22), "private_domain")))
    setnames(h25, setdiff(names(h25), "private_domain"),
             paste0("b_", setdiff(names(h25), "private_domain")))
    d <- merge(yg, h22[private_domain %chin% matched], by = "private_domain", all.x = TRUE)
    d <- merge(d, h25[private_domain %chin% matched], by = "private_domain", all.x = TRUE)

    # Matching on the domain is not enough for cookies. A domain can sit inside
    # the rank cap at one date and outside it at the other, and the capped share
    # grows over time, so scoring the unasked side as zero reads a change in what
    # was queried as a change in what sites do. Restrict each measure to the
    # domains carrying it at both dates, and zero the weight elsewhere so the
    # denominator follows the numerator.
    both_of <- function(k) if (k == "third_party_cookies")
        !is.na(d$a_cookies_queried) & d$a_cookies_queried > 0 &
        !is.na(d$b_cookies_queried) & d$b_cookies_queried > 0
    else !is.na(d[[paste0("a_", k)]]) & !is.na(d[[paste0("b_", k)]])

    rate <- function(pre) {
        r <- data.table(caseid = person$caseid)
        for (k in keys) {
            w <- fifelse(both_of(k), as.numeric(d$visits), 0)
            x <- d[[paste0(pre, "_", k)]]
            a <- data.table(caseid = d$caseid, n = ifelse(is.na(x), 0, x) * w,
                            den = w)[, lapply(.SD, sum), by = caseid]
            a[den == 0, den := NA_real_]
            i <- match(person$caseid, a$caseid)
            set(r, NULL, k, a$n[i] / a$den[i])
        }
        r
    }
    r22 <- rate("a"); r25 <- rate("b")

    # Restricting to domains measured at both dates leaves some panelists with no
    # qualifying visits for a measure. They drop from that row rather than being
    # scored as zero, and the count is reported so the base is visible.
    rows <- lapply(TEMPORAL_MEASURES, function(p) {
        a <- r22[[p[1]]]; b <- r25[[p[1]]]
        ok <- !is.na(a) & !is.na(b)
        cat(sprintf("  %-32s %d of %d panelists have qualifying visits\n",
                    p[1], sum(ok), length(ok)))
        a <- a[ok]; b <- b[ok]
        c(p[2], sprintf("%.3f", mean(a)), sprintf("%.3f", mean(b)),
          sprintf("%+.1f", 100 * (mean(b) - mean(a)) / mean(a)),
          sprintf("%.2f", cor(a, b)))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, table_path)

    # Each point is one panelist under the two measurement dates; the line is
    # parity. Points below it are people the 2025 scan reads as less exposed
    # than the 2022 crawl would have.
    pl <- rbindlist(lapply(TEMPORAL_MEASURES[1:2], function(p) data.table(
        panel = p[2], x = r25[[p[1]]], y = r22[[p[1]]])))
    pl <- pl[!is.na(x) & !is.na(y)]
    pl[, panel := factor(panel, levels = vapply(TEMPORAL_MEASURES[1:2], `[`,
                                                character(1), 2))]
    g <- ggplot(pl, aes(x, y)) +
        geom_abline(slope = 1, intercept = 0, colour = C_INTERVAL, linewidth = .4) +
        geom_point(size = .5, alpha = .25, colour = C_SIGNIFICANT) +
        facet_wrap(~panel, scales = "free") +
        labs(x = "Exposure per visit, measured January 2025",
             y = "Exposure per visit,\nmeasured June 2022") +
        theme_blacklight(grid = "both")
    save_fig(g, figure_path, width = FIG_FULL_W, height = 3.1)
    invisible(out)
}

# ---------------------------------------------------------------------------
# The calibrated fill, in one place
# ---------------------------------------------------------------------------
# Two things need it: the coverage-bounds table, which reports what the zero-fill
# costs in aggregate, and the per-panelist scenario rates the demographic
# robustness checks regress on. It used to exist twice, once here and once in a
# Python script, which is two implementations of one method free to drift apart.

# The visit table joined to Blacklight, HTTP Archive June 2022 and Wayback, with
# the three "was this domain measured" masks every fill depends on.
coverage_frame <- function(visits, bl) {
    keys <- vapply(COVERAGE_MEASURES, `[`, character(1), 1)
    ha <- fread(FP_HA_MEASURES, showProgress = FALSE)[crawl == "panel"]
    ha22 <- ha_by_domain(ha, c(keys, "cookies_queried"), "coverage")
    setnames(ha22, setdiff(names(ha22), "private_domain"),
             paste0("ha_", setdiff(names(ha22), "private_domain")))
    wb <- fread(FP_WB_MEASURES, showProgress = FALSE)[, c("private_domain", WB_FILL_KEYS),
                                                      with = FALSE]
    wb <- unique(wb, by = "private_domain")
    setnames(wb, WB_FILL_KEYS, paste0("wb_", WB_FILL_KEYS))

    m <- as.data.table(visits)
    m[, filename := gsub(".", "_", private_domain, fixed = TRUE)]
    b <- as.data.table(bl); setnames(b, setdiff(names(b), "filename"),
                                     paste0("bl_", setdiff(names(b), "filename")))
    m <- merge(m, b, by = "filename", all.x = TRUE)
    m <- merge(m, ha22, by = "private_domain", all.x = TRUE)
    m <- merge(m, wb, by = "private_domain", all.x = TRUE)
    list(m = m,
         scanned = !is.na(m$bl_ddg_join_ads),
         ha_meas = !is.na(m$ha_ddg_join_ads),
         wb_meas = !is.na(m$wb_ddg_join_ads))
}

wmean0 <- function(v, w) if (!length(v)) 0 else weighted.mean(v, w)

# Per measure: what to fill an unmeasured visit with, and which visits each
# auxiliary instrument can actually speak to.
measure_fills <- function(f, k) {
    m <- f$m; w <- m$visits
    cbl <- m[[paste0("bl_", k)]]
    ha_pres <- !is.na(m[[paste0("ha_", k)]]) & m[[paste0("ha_", k)]] > 0

    # The HTTP Archive cookie extract is rank-capped while its request extract is
    # not, so a domain can be present and never have been asked about cookies.
    # Letting "not asked" join the "asked, found none" arm inverts the
    # calibration -- absent would predict more tracking than present -- so the
    # gate below refuses to continue if it does.
    k_meas <- if (k == "third_party_cookies")
        f$ha_meas & !is.na(m$ha_cookies_queried) & m$ha_cookies_queried > 0 else f$ha_meas
    cal <- f$scanned & k_meas
    m1 <- wmean0(cbl[cal & ha_pres], w[cal & ha_pres])
    m0 <- wmean0(cbl[cal & !ha_pres], w[cal & !ha_pres])
    if (!(m1 > m0)) stop(sprintf(
        "%s: calibration inverted -- HA-present predicts %.3f but HA-absent %.3f",
        k, m1, m0))

    wb_fill <- NULL
    if (k %in% WB_FILL_KEYS) {
        wp <- !is.na(m[[paste0("wb_", k)]]) & m[[paste0("wb_", k)]] > 0
        cw <- f$scanned & f$wb_meas
        wb_fill <- ifelse(wp, wmean0(cbl[cw & wp], w[cw & wp]),
                          wmean0(cbl[cw & !wp], w[cw & !wp]))
    }
    list(cbl = cbl, k_meas = k_meas, ha_fill = ifelse(ha_pres, m1, m0), wb_fill = wb_fill,
         fill_mean = wmean0(cbl[f$scanned], w[f$scanned]),
         fill_p90 = wquantile(cbl[f$scanned], w[f$scanned], 0.90))
}

# One scenario: which auxiliary layers to apply, and what to assume for the
# visits no instrument reached.
fill_counts <- function(f, fl, ha_layer, wb_layer, unmeasured) {
    cc <- fl$cbl
    rest <- !f$scanned
    if (ha_layer) { cc[rest & fl$k_meas] <- fl$ha_fill[rest & fl$k_meas]
                    rest <- rest & !fl$k_meas }
    if (wb_layer && !is.null(fl$wb_fill)) {
        cc[rest & f$wb_meas] <- fl$wb_fill[rest & f$wb_meas]
        rest <- rest & !f$wb_meas }
    cc[rest] <- unmeasured
    cc
}

# Visit-weighted per-panelist rate for a filled count vector.
per_user_rate <- function(m, counts, ids) {
    r <- data.table(caseid = m$caseid, num = counts * m$visits,
                    den = m$visits)[, .(num = sum(num), den = sum(den)), by = caseid]
    i <- match(ids, r$caseid)
    r$num[i] / r$den[i]
}

# ---------------------------------------------------------------------------
# B. Coverage: what does counting unscanned visits as tracker-free cost?
# ---------------------------------------------------------------------------
# Visits to domains Blacklight never scanned currently contribute zero to the
# numerator and stay in the denominator, so every published rate is a lower
# bound by construction. Rather than argue about the size of that bound, fill
# the gap with measurement: HTTP Archive's June-2022 request maps cover most of
# the missing visit mass, Wayback covers a little more, and each fill is
# calibrated against Blacklight on domains both instruments saw.
#
# Eight scenarios span the range. The first three assume; the rest measure what
# can be measured and only assume for the remainder.
COVERAGE_MEASURES <- list(
    c("ddg_join_ads", "Ad trackers"),
    c("third_party_cookies", "Third-party cookies"),
    c("fb_pixel", "Facebook Pixel"),
    c("google_analytics", "Google Analytics (Remarketing)")
)
# A static parse cannot see Set-Cookie headers, so Wayback has no cookie
# reading and that measure falls back to the HTTP Archive fills.
WB_FILL_KEYS <- c("ddg_join_ads", "fb_pixel", "google_analytics")
COVERAGE_SCENARIOS <- c("zero", "mean", "p90", "ha_zero", "ha_p90",
                        "hawb_zero", "hawb_mean", "hawb_p90")

wquantile <- function(v, w, q) {
    o <- order(v); v <- v[o]; w <- w[o]
    v[searchsorted(cumsum(w) / sum(w), q)]
}
# numpy's searchsorted with the default 'left' side, 1-indexed for R.
searchsorted <- function(sorted, x) sum(sorted < x) + 1L

build_coverage_bounds <- function(visits, bl, person, table_path, figure_path) {
    keys <- vapply(COVERAGE_MEASURES, `[`, character(1), 1)
    f <- coverage_frame(visits, bl)
    m <- f$m; scanned <- f$scanned; ha_meas <- f$ha_meas; wb_meas <- f$wb_meas

    num("UnscannedVisitShare", 100 * sum(m$visits[!scanned]) / sum(m$visits))
    num("HAMissingCoverage",
        100 * sum(m$visits[!scanned & ha_meas]) / sum(m$visits[!scanned]))
    num("WBMissingCoverage",
        100 * sum(m$visits[!scanned & !ha_meas & wb_meas]) / sum(m$visits[!scanned]))
    cat(sprintf("  unscanned visits %.1f%%; of those HA covers %.1f%%, WB adds %.1f%%, %.1f%% never measured\n",
        100 * sum(m$visits[!scanned]) / sum(m$visits),
        100 * sum(m$visits[!scanned & ha_meas]) / sum(m$visits[!scanned]),
        100 * sum(m$visits[!scanned & !ha_meas & wb_meas]) / sum(m$visits[!scanned]),
        100 * sum(m$visits[!scanned & !ha_meas & !wb_meas]) / sum(m$visits[!scanned])))

    scenario_rates <- function(k) {
        fl <- measure_fills(f, k)
        cfg <- list(zero = list(FALSE, FALSE, 0), mean = list(FALSE, FALSE, fl$fill_mean),
                    p90 = list(FALSE, FALSE, fl$fill_p90), ha_zero = list(TRUE, FALSE, 0),
                    ha_p90 = list(TRUE, FALSE, fl$fill_p90),
                    hawb_zero = list(TRUE, TRUE, 0), hawb_mean = list(TRUE, TRUE, fl$fill_mean),
                    hawb_p90 = list(TRUE, TRUE, fl$fill_p90))
        vapply(cfg, function(s) mean(per_user_rate(
            m, fill_counts(f, fl, s[[1]], s[[2]], s[[3]]), person$caseid)), numeric(1))
    }
    res <- vapply(keys, scenario_rates, numeric(length(COVERAGE_SCENARIOS)))
    out <- cbind(
        data.frame(measure = vapply(COVERAGE_MEASURES, `[`, character(1), 2),
                   stringsAsFactors = FALSE),
        as.data.frame(matrix(
            mapply(fmt_measure, t(res[COVERAGE_SCENARIOS, ]),
                   rep(keys, times = length(COVERAGE_SCENARIOS))),
            nrow = length(keys)), stringsAsFactors = FALSE))
    write_tex(out, table_path)

    # Each bar is how far the estimate can move under one class of assumption.
    # The published number sits at the left end of the widest bar: measurement
    # narrows the range and raises its floor.
    bd <- as.data.frame(t(res))
    lv <- c("assumption only (zero to p90)", "+ HTTP Archive 2022 fill",
            "+ Wayback fill")
    pl <- rbindlist(lapply(seq_len(nrow(bd)), function(i) data.table(
        measure = out[[1]][i], band = lv,
        lo = c(bd$zero[i], bd$ha_zero[i], bd$hawb_zero[i]),
        hi = c(bd$p90[i], bd$ha_p90[i], bd$hawb_p90[i]))))
    pl[, band := factor(band, levels = lv)]
    pl[, measure := factor(measure, levels = rev(out[[1]]))]
    g <- ggplot(pl, aes(y = measure, colour = band)) +
        geom_linerange(aes(xmin = lo, xmax = hi),
                       position = position_dodge(width = .55), linewidth = 2.4) +
        scale_colour_manual(values = c(C_INTERVAL, "#8a8a8a", "#2f2f2f"), name = NULL) +
        labs(x = "Mean exposure per visit", y = NULL) +
        theme_blacklight(grid = "x") +
        theme(legend.position = "bottom")
    save_fig(g, figure_path, width = FIG_FULL_W, height = 3.2)
    invisible(out)
}

# Does the missingness fall unevenly across people? The coverage-bounds table
# answers what the zero-fill costs on average; these ask whether it could be
# manufacturing the demographic gaps, which only per-panelist rates can settle.
# Display names match the column headers the manuscript table uses.
# A legend has to stand alone, so these spell out the fill rather than reusing
# the table's column abbreviations (HA, HA+WB).
SCENARIO_LABELS <- c(
    zero      = "Counted as zero",
    mean      = "Scanned average",
    ha_mean   = "HTTP Archive",
    hawb_mean = "Archive + Wayback"
)
cell_be <- function(r) sprintf("%.2f%s (%.2f)", r[1], stars(r[3]), r[2])

fit_terms <- function(yvar, data) {
    r <- fit_demo(yvar, data)
    stats::setNames(lapply(seq_len(nrow(r)), function(i)
        c(r$b[i], r$se[i], r$p[i])), r$term)
}

build_implications_tables <- function(person, rates) {
    d <- merge(person, as.data.frame(rates), by = "caseid")

    # Per-user scan coverage, in percentage points, on the demographic spec.
    d$coverage_pct <- 100 * d$coverage
    cov <- fit_terms("coverage_pct", d)
    # The text names the largest coefficient in this table.
    big <- names(cov)[which.max(vapply(cov, function(x) abs(x[1]), numeric(1)))]
    num("CovDemoLargestTerm", big)
    num("CovDemoLargestB", cov[[big]][1], "%.2f")
    num("CovDemoLargestP", fmt_p(cov[[big]][3]))
    write_tex(data.frame(term = names(cov),
                         v = vapply(cov, cell_be, character(1))),
              file.path(TABLES_DIR, "implications_coverage_by_demo"))

    # Each fill scenario re-estimates the published spec.
    cols <- unlist(lapply(IMPL_MEASURES, function(k) paste0(k, "_", SCENARIOS)))
    fills <- lapply(cols, fit_terms, data = d)
    write_tex(data.frame(term = names(fills[[1]]),
                         do.call(cbind, lapply(fills, vapply, cell_be, character(1)))),
              file.path(TABLES_DIR, "implications_demo_fill_scenarios"))

    # Same instrument at each date, and their difference.
    stems <- unlist(lapply(IMPL_MEASURES, function(k)
        c(paste0("ha22_", k), paste0("ha25_", k), paste0("drift_", k))))
    drift <- lapply(stems, fit_terms, data = d)
    names(drift) <- stems
    # The two p-values the text quotes when saying the gaps do not drift.
    num("DriftColAdP", fmt_p(drift[["drift_ddg_join_ads"]][["Educ: College"]][3]))
    num("DriftAsianAdP", fmt_p(drift[["drift_ddg_join_ads"]][["Race: Asian"]][3]))
    write_tex(data.frame(term = names(drift[[1]]),
                         do.call(cbind, lapply(drift, vapply, cell_be, character(1)))),
              file.path(TABLES_DIR, "implications_drift_by_demo"))
    invisible(NULL)
}

# Coefficients under each unscanned-visit fill, dodged so the four scenarios sit
# side by side for each term. Shape carries the scenario, which is a stable and
# necessary distinction; nothing else varies by shape in the paper.
build_scenarios_figure <- function(person, rates, path) {
    # The four scenarios are dodged within each term. DODGE is the share of the
    # one-unit term slot they occupy, so raising it separates the four lines and
    # narrows the gap between terms; the taller canvas buys back both.
    DODGE <- 0.85
    d <- merge(person, as.data.frame(rates), by = "caseid")
    rows <- list()
    for (k in IMPL_MEASURES) for (s in SCENARIOS) {
        r <- fit_demo(paste0(k, "_", s), d)
        r$measure <- if (k == "ddg_join_ads") "Ad trackers / visit" else "Third-party cookies / visit"
        r$scenario <- s
        rows[[length(rows) + 1]] <- r
    }
    df <- do.call(rbind, rows)
    df$scenario <- factor(SCENARIO_LABELS[df$scenario], levels = SCENARIO_LABELS)
    df$term <- factor(gsub("--", "–", df$term, fixed = TRUE),
                      levels = rev(gsub("--", "–", COEF_ORDER, fixed = TRUE)))
    df$lo <- df$b - 1.96 * df$se; df$hi <- df$b + 1.96 * df$se

    p <- ggplot(df, aes(b, term, shape = scenario, colour = scenario)) +
        geom_reference() +
        geom_errorbar(aes(xmin = lo, xmax = hi), width = 0, linewidth = 0.35,
                      position = position_dodge(width = DODGE)) +
        geom_point(size = 1.0, position = position_dodge(width = DODGE)) +
        scale_colour_manual(values = c("#000000", "#4d4d4d", "#8a8a8a", "#b3b3b3")) +
        scale_shape_manual(values = c(16, 15, 17, 18)) +
        facet_wrap(~measure, ncol = 2, scales = "free_x") +
        scale_x_continuous(n.breaks = 5) +
        labs(x = "Estimate and 95% conf. int.", y = NULL) +
        theme_blacklight(grid = "x") +
        theme(panel.spacing.x = unit(1.2, "lines"))
    # 12 terms x 4 scenarios: smaller markers on a taller canvas so the dodged
    # groups keep clear air between them.
    save_fig(p, path, width = FIG_FULL_W, height = 5.0)
}

# ---------------------------------------------------------------------------
# Everything this pipeline emits
# ---------------------------------------------------------------------------
# One entry point so 99_run_all.R stays a runner rather than a second place
# where the list of outputs lives.

# ---------------------------------------------------------------------------
# Everything this module writes, in one place.
# ---------------------------------------------------------------------------
emit_validity <- function(bl, person, visits, third_parties) {
    coded <- fread(file.path(AUDIT_DIR, "audit_sample_coded.csv"), showProgress = FALSE)

    build_scan_by_reach(visits, file.path(TABLES_DIR, "scan_by_reach"))
    build_rescan_drift(bl, visits, file.path(TABLES_DIR, "rescan_drift"))
    register_retry_pass(bl, visits)
    num("AuditRescanN", tex_num(length(list.files(FP_AUDIT_JSON, pattern = "\\.json$"))))
    build_scan_failure_reasons(visits, file.path(TABLES_DIR, "scan_failure_reasons"))
    build_wb_liveness(visits, bl, file.path(TABLES_DIR, "wb_liveness"))
    build_selection_audit_composition(coded,
        file.path(TABLES_DIR, "selection_audit_composition"))
    build_selection_audit_tracking(coded, visits, bl,
        file.path(TABLES_DIR, "selection_audit_tracking"),
        file.path(FIGURES_DIR, "selection_audit_tracking"))
    build_google_reach_audit(third_parties, visits,
        file.path(TABLES_DIR, "implications_google_reach_audit"))

    build_ha_bl_agreement(bl, file.path(TABLES_DIR, "ha_bl_agreement"))
    build_wb_ha_agreement(file.path(TABLES_DIR, "wb_ha_agreement"))
    build_httparchive_drift(file.path(TABLES_DIR, "httparchive_drift"))
    build_temporal_user_exposure(visits, person,
        file.path(TABLES_DIR, "temporal_user_exposure"),
        file.path(FIGURES_DIR, "temporal_user_exposure"))
    build_coverage_bounds(visits, bl, person,
        file.path(TABLES_DIR, "coverage_bounds_wayback"),
        file.path(FIGURES_DIR, "coverage_bounds_wayback"))

    # Per-panelist coverage and fills, derived here rather than read from a file
    # a separate pipeline had to remember to rebuild.
    rates <- build_user_scenario_rates(visits, bl, person)

    # Per-panelist scan coverage. The text reports this distribution to argue
    # the pooled coverage figure is not hiding panelists with almost none.
    cv <- as.data.frame(rates)$coverage
    num("CovMean",   100 * mean(cv))
    num("CovMedian", 100 * median(cv))
    num("CovSD",     100 * sd(cv))
    num("CovPFive",  100 * quantile(cv, 0.05))
    num("CovPNinetyFive", 100 * quantile(cv, 0.95))
    num("CovHalfPlus", 100 * mean(cv >= 0.5))
    num("CovSeventyPlus", 100 * mean(cv >= 0.7))

    build_implications_tables(person, rates)
    build_scenarios_figure(person, rates,
                           file.path(FIGURES_DIR, "implications_demo_scenarios"))
    invisible(NULL)
}

# ---------------------------------------------------------------------------
# Per-panelist coverage, fill scenarios, and drift
# ---------------------------------------------------------------------------
# The coverage-bounds table above asks what the zero-fill costs on average. The
# demographic robustness checks ask something the average cannot answer: whether
# the missingness is patterned across people in a way that could manufacture the
# demographic gaps. That needs the same fills carried down to the individual, so
# the same calibration serves both.
#
# This was a Python script until it went stale: it was built before 434 recovered
# scans entered the corpus, so three tables and a figure were regressing on a
# coverage of 76.4% that had since become 79.0%. Deriving it here means it cannot
# fall behind the corpus again.
IMPL_MEASURES <- c("ddg_join_ads", "third_party_cookies")
SCENARIOS <- c("zero", "mean", "ha_mean", "hawb_mean")

build_user_scenario_rates <- function(visits, bl, person) {
    f <- coverage_frame(visits, bl)
    m <- f$m
    ids <- person$caseid
    out <- data.table(caseid = ids)

    # Share of a panelist's visits that landed on a domain Blacklight reached.
    cov <- m[, .(sc = sum(visits[f$scanned[.I]]), tt = sum(visits)), by = caseid]
    out[, coverage := cov$sc[match(ids, cov$caseid)] / cov$tt[match(ids, cov$caseid)]]

    for (k in IMPL_MEASURES) {
        fl <- measure_fills(f, k)
        cfg <- list(zero = list(FALSE, FALSE, 0),
                    mean = list(FALSE, FALSE, fl$fill_mean),
                    ha_mean = list(TRUE, FALSE, fl$fill_mean),
                    hawb_mean = list(TRUE, TRUE, fl$fill_mean))
        for (s in names(cfg)) {
            cc <- fill_counts(f, fl, cfg[[s]][[1]], cfg[[s]][[2]], cfg[[s]][[3]])
            set(out, NULL, paste0(k, "_", s), per_user_rate(m, cc, ids))
        }
    }

    d <- ha_same_instrument(visits, ids)
    for (k in IMPL_MEASURES) {
        set(out, NULL, paste0("ha22_", k), d[[paste0("r22_", k)]])
        set(out, NULL, paste0("ha25_", k), d[[paste0("r25_", k)]])
        set(out, NULL, paste0("drift_", k), d[[paste0("r25_", k)]] - d[[paste0("r22_", k)]])
    }
    out[]
}

# Per-panelist exposure with domain-level tracking measured by HTTP Archive at
# each date, on the domains it saw at both.
#
# Matching on the domain is not enough for cookies. A domain can sit inside the
# rank cap at one date and outside it at the other, and the capped share grows
# over time, so scoring the unasked side as zero would read a change in what was
# queried as a change in what sites do. That is the artifact the cookie cap
# already produced once in this project; here the comparison is restricted to
# domains queried at both dates, and the weight goes to zero elsewhere so the
# denominator matches the numerator.
ha_same_instrument <- function(visits, ids) {
    keys <- IMPL_MEASURES
    ha <- fread(FP_HA_MEASURES, showProgress = FALSE)
    agg <- function(cr) ha_by_domain(ha[crawl == cr], c(keys, "cookies_queried"))
    h22 <- agg("panel"); h25 <- agg("blacklight_match")
    matched <- intersect(h22$private_domain, h25$private_domain)
    setnames(h22, setdiff(names(h22), "private_domain"),
             paste0("h22_", setdiff(names(h22), "private_domain")))
    setnames(h25, setdiff(names(h25), "private_domain"),
             paste0("h25_", setdiff(names(h25), "private_domain")))
    m <- merge(as.data.table(visits), h22[private_domain %chin% matched],
               by = "private_domain", all.x = TRUE)
    m <- merge(m, h25[private_domain %chin% matched], by = "private_domain", all.x = TRUE)

    out <- data.table(caseid = ids)
    for (k in keys) {
        a <- m[[paste0("h22_", k)]]; b <- m[[paste0("h25_", k)]]
        both <- if (k == "third_party_cookies")
            !is.na(m$h22_cookies_queried) & m$h22_cookies_queried > 0 &
            !is.na(m$h25_cookies_queried) & m$h25_cookies_queried > 0
        else !is.na(a) & !is.na(b)
        w <- fifelse(both, as.numeric(m$visits), 0)
        r <- data.table(caseid = m$caseid,
                        n22 = ifelse(is.na(a), 0, a) * w,
                        n25 = ifelse(is.na(b), 0, b) * w, den = w)[
            , lapply(.SD, sum), by = caseid]
        r[den == 0, den := NA_real_]
        i <- match(ids, r$caseid)
        set(out, NULL, paste0("r22_", k), r$n22[i] / r$den[i])
        set(out, NULL, paste0("r25_", k), r$n25[i] / r$den[i])
    }
    out
}
