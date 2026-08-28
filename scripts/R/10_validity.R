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
FP_BL_JSON <- file.path(DATA_DIR, "blacklight_json")
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

build_scan_failure_reasons <- function(visits, path) {
    dom <- as.data.table(visits)[, .(reach = uniqueN(caseid), visits = sum(visits)),
                                 by = private_domain]
    scanned <- sub("\\.json$", "", list.files(FP_BL_JSON, pattern = "\\.json$"))
    dom[, scanned := gsub(".", "_", private_domain, fixed = TRUE) %chin% scanned]

    un <- merge(dom[!(scanned)], parse_scan_errors(), by = "private_domain", all.x = TRUE)
    un[is.na(reason), reason := "not_in_error_log"]
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
                    list.files(FP_BL_JSON, pattern = "\\.json$")), fixed = TRUE)
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
    agg <- function(cr) ha_by_domain(ha[crawl == cr], keys, cr)
    h22 <- agg("panel"); h25 <- agg("blacklight_match")
    matched <- intersect(h22$private_domain, h25$private_domain)
    cat(sprintf("  HA domains: %s in 2022, %s in 2025, %s matched\n",
                format(nrow(h22), big.mark = ","), format(nrow(h25), big.mark = ","),
                format(length(matched), big.mark = ",")))

    yg <- as.data.table(visits)
    tt <- yg[, .(tt = sum(visits)), by = caseid]
    rate <- function(h) {
        d <- merge(yg, h[private_domain %chin% matched], by = "private_domain",
                   all.x = TRUE)
        r <- d[, lapply(.SD, function(x) sum(ifelse(is.na(x), 0, x) * visits)),
               by = caseid, .SDcols = keys]
        r <- merge(r, tt, by = "caseid")
        for (k in keys) set(r, NULL, k, r[[k]] / r$tt)
        r[match(person$caseid, caseid)]   # the paper's analytical sample
    }
    r22 <- rate(h22); r25 <- rate(h25)

    rows <- lapply(TEMPORAL_MEASURES, function(p) {
        a <- r22[[p[1]]]; b <- r25[[p[1]]]
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
    ha <- fread(FP_HA_MEASURES, showProgress = FALSE)[crawl == "panel"]
    ha22 <- ha_by_domain(ha, c(keys, "cookies_queried"), "coverage")
    setnames(ha22, setdiff(names(ha22), "private_domain"),
             paste0("ha_", setdiff(names(ha22), "private_domain")))
    wb <- fread(FP_WB_MEASURES, showProgress = FALSE)[, c("private_domain", WB_FILL_KEYS),
                                                      with = FALSE]
    setnames(wb, WB_FILL_KEYS, paste0("wb_", WB_FILL_KEYS))

    m <- as.data.table(visits)
    m[, filename := gsub(".", "_", private_domain, fixed = TRUE)]
    b <- as.data.table(bl); setnames(b, setdiff(names(b), "filename"),
                                     paste0("bl_", setdiff(names(b), "filename")))
    m <- merge(m, b, by = "filename", all.x = TRUE)
    m <- merge(m, ha22, by = "private_domain", all.x = TRUE)
    m <- merge(m, wb, by = "private_domain", all.x = TRUE)

    scanned <- !is.na(m$bl_ddg_join_ads)
    ha_meas <- !is.na(m$ha_ddg_join_ads)
    wb_meas <- !is.na(m$wb_ddg_join_ads)
    tt <- m[, .(tt = sum(visits)), by = caseid]

    cat(sprintf("  unscanned visits %.1f%%; of those HA covers %.1f%%, WB adds %.1f%%, %.1f%% never measured\n",
        100 * sum(m$visits[!scanned]) / sum(m$visits),
        100 * sum(m$visits[!scanned & ha_meas]) / sum(m$visits[!scanned]),
        100 * sum(m$visits[!scanned & !ha_meas & wb_meas]) / sum(m$visits[!scanned]),
        100 * sum(m$visits[!scanned & !ha_meas & !wb_meas]) / sum(m$visits[!scanned])))

    wmean <- function(v, w) if (!length(v)) 0 else weighted.mean(v, w)

    scenario_rates <- function(k) {
        cbl <- m[[paste0("bl_", k)]]; w <- m$visits
        ha_pres <- !is.na(m[[paste0("ha_", k)]]) & m[[paste0("ha_", k)]] > 0
        fill_mean <- wmean(cbl[scanned], w[scanned])
        fill_p90 <- wquantile(cbl[scanned], w[scanned], 0.90)

        # The HTTP Archive cookie extract is rank-capped while its request
        # extract is not, so a domain can be present and never have been asked
        # about cookies. Letting "not asked" join the "asked, found none" arm
        # inverts the calibration -- absent would predict more tracking than
        # present -- so the gate below refuses to continue if it does.
        k_meas <- if (k == "third_party_cookies")
            ha_meas & !is.na(m$ha_cookies_queried) & m$ha_cookies_queried > 0 else ha_meas
        cal <- scanned & k_meas
        m1 <- wmean(cbl[cal & ha_pres], w[cal & ha_pres])
        m0 <- wmean(cbl[cal & !ha_pres], w[cal & !ha_pres])
        if (!(m1 > m0)) stop(sprintf(
            "%s: calibration inverted -- HA-present predicts %.3f but HA-absent %.3f",
            k, m1, m0))
        ha_fill <- ifelse(ha_pres, m1, m0)

        wb_fill <- NULL
        if (k %in% WB_FILL_KEYS) {
            wp <- !is.na(m[[paste0("wb_", k)]]) & m[[paste0("wb_", k)]] > 0
            cw <- scanned & wb_meas
            wb_fill <- ifelse(wp, wmean(cbl[cw & wp], w[cw & wp]),
                              wmean(cbl[cw & !wp], w[cw & !wp]))
        }
        build <- function(ha_layer, wb_layer, unmeasured) {
            cc <- cbl
            rest <- !scanned
            if (ha_layer) { cc[rest & k_meas] <- ha_fill[rest & k_meas]
                            rest <- rest & !k_meas }
            if (wb_layer && !is.null(wb_fill)) {
                cc[rest & wb_meas] <- wb_fill[rest & wb_meas]
                rest <- rest & !wb_meas }
            cc[rest] <- unmeasured
            cc
        }
        cfg <- list(zero = list(FALSE, FALSE, 0), mean = list(FALSE, FALSE, fill_mean),
                    p90 = list(FALSE, FALSE, fill_p90), ha_zero = list(TRUE, FALSE, 0),
                    ha_p90 = list(TRUE, FALSE, fill_p90),
                    hawb_zero = list(TRUE, TRUE, 0), hawb_mean = list(TRUE, TRUE, fill_mean),
                    hawb_p90 = list(TRUE, TRUE, fill_p90))
        vapply(cfg, function(s) {
            cc <- build(s[[1]], s[[2]], s[[3]])
            r <- data.table(caseid = m$caseid, num = cc * m$visits)[
                , .(num = sum(num)), by = caseid]
            r <- merge(r, tt, by = "caseid")
            mean(r$num[match(person$caseid, r$caseid)] /
                 r$tt[match(person$caseid, r$caseid)])
        }, numeric(1))
    }
    res <- vapply(keys, scenario_rates, numeric(length(COVERAGE_SCENARIOS)))
    out <- cbind(
        data.frame(measure = vapply(COVERAGE_MEASURES, `[`, character(1), 2),
                   stringsAsFactors = FALSE),
        as.data.frame(matrix(sprintf("%.3f", t(res[COVERAGE_SCENARIOS, ])),
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

# ---------------------------------------------------------------------------
# Everything this module writes, in one place.
# ---------------------------------------------------------------------------
emit_validity <- function(bl, person, visits, third_parties) {
    coded <- fread(file.path(AUDIT_DIR, "audit_sample_coded.csv"), showProgress = FALSE)

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
    invisible(NULL)
}
