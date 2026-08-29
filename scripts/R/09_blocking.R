# 09_blocking.R
# What today's defenses leave behind, and for whom.
#
# Because each Blacklight scan names the third parties responsible for each
# behavior, applying a blocklist to those domains and recomputing every measure
# is arithmetic rather than simulation.
#
# One input is not reproducible in R and is treated as collected data:
# data/blocking/blocked_pairs.csv, the result of matching 332,890 domain-script
# pairs against pinned EasyList/EasyPrivacy/Disconnect rules with Python's
# adblock engine. R has no equivalent rule matcher, and the blocklists are
# pinned in data/blocklists/manifest.json, so the pairs are frozen alongside
# them rather than re-derived.

FP_BLOCKED_PAIRS <- file.path(DATA_DIR, "blocking", "blocked_pairs.csv")
FP_DOMAIN_SCRIPTS <- file.path(DATA_DIR, "blocking", "bl_domain_scripts.csv")

# Three tiers of defense, in the order the manuscript reports them.
TIERS <- c(A = "EasyList", B = "EasyPrivacy", C = "All three lists")
HEADLINE_TIER <- "C"
MEASURES_BLOCK <- c("ddg_join_ads", "third_party_cookies", "canvas_fingerprinting",
                    "session_recording", "key_logging", "fb_pixel", "google_analytics")

# Cards that name no responsible domain cannot be attributed, so nothing can be
# blocked and their residual equals their published level by construction. That
# is a property of the instrument, not a finding about defenses.
UNATTRIBUTED <- c("fb_pixel", "google_analytics")

# Each card carries a measure name and whether it counts responsible domains or
# just flags the behaviour. A count measure's residual is how many responsible
# domains a tier fails to stop; a behavioural measure survives if *any* does --
# blocking two of three session recorders still leaves the site recording.
CARD_MEASURES <- list(
    ddg_join_ads          = list("ddg_join_ads",          "count"),
    cookies               = list("third_party_cookies",   "count"),
    canvas_fingerprinters = list("canvas_fingerprinting", "flag"),
    session_recorders     = list("session_recording",     "flag"),
    key_logging           = list("key_logging",           "flag"),
    fb_pixel_events       = list("fb_pixel",              "flag"),
    ga                    = list("google_analytics",      "flag")
)

# ---------------------------------------------------------------------------
# Residual domain-level measures
# ---------------------------------------------------------------------------
# Two bounds per tier. The plain variant counts what a domain-level rule
# certainly stops; the `_lo` variant also credits rules that merely mention the
# domain, which is the optimistic reading of what a blocker achieves.
build_residual_domain <- function(bl) {
    scripts <- fread(FP_DOMAIN_SCRIPTS)
    pairs <- fread(FP_BLOCKED_PAIRS)
    d <- merge(scripts, pairs, by = c("private_domain", "script_domain"), all.x = TRUE)
    if (anyNA(d[[paste0("blocked_", names(TIERS)[1])]]))
        stop("attribution rows with no blocking verdict", call. = FALSE)

    # Every scanned domain, not just the 25,981 that name a responsible third
    # party. The 8,097 with none are the all-zero scans: nothing can be blocked
    # on them, so their residual is zero -- but they are 19.5% of panel visits
    # and the sensitivity analysis needs them present to be able to count them.
    out <- data.table(filename = sort(unique(bl$filename)))
    for (card in names(CARD_MEASURES)) {
        measure <- CARD_MEASURES[[card]][[1]]; kind <- CARD_MEASURES[[card]][[2]]
        sub <- d[card_type == card]
        for (tier in names(TIERS)) for (sfx in c("", "_lo")) {
            col <- if (sfx == "") paste0("blocked_", tier) else paste0("rule_present_", tier)
            v <- sub[, .(val = if (kind == "count") sum(!get(col)) else as.integer(any(!get(col)))),
                     by = filename]
            setnames(v, "val", paste0(measure, "_resid_", tier, sfx))
            out <- merge(out, v, by = "filename", all.x = TRUE)
        }
    }
    for (j in setdiff(names(out), "filename")) set(out, which(is.na(out[[j]])), j, 0)

    # Cookies are counted per cookie but attributed per domain, so the residual
    # is a count of cookie-setting domains left unblocked. Carry the domain count
    # alongside rather than comparing it against the published cookie count --
    # dividing one by the other overstated blocking efficacy by 14 points.
    nd <- scripts[card_type == "cookies", .N, by = filename]
    out <- merge(out, nd, by = "filename", all.x = TRUE)
    setnames(out, "N", "third_party_cookie_domains")
    out[is.na(third_party_cookie_domains), third_party_cookie_domains := 0L][]
}

# ---------------------------------------------------------------------------
# Residual exposure per person
# ---------------------------------------------------------------------------
# Same visit-weighting as the published measures, so residual and published sit
# on one scale and the comparison in residual_levels is like for like.
build_residual_person <- function(resid, bl, person) {
    # Carry the published measures alongside the residuals so the two aggregate
    # together and the gate below has an unblocked column to check.
    resid <- merge(as.data.table(bl), resid, by = "filename", all.y = TRUE)
    visits <- visit_panel()[!is.na(private_domain)]
    r <- copy(resid)[, private_domain := gsub("_", ".", filename, fixed = TRUE)]
    vals <- setdiff(names(r), c("filename", "private_domain"))

    d <- merge(visits, r[, c("private_domain", vals), with = FALSE],
               by = "private_domain", all.x = TRUE)
    for (j in vals) set(d, NULL, j, d[[j]] * d$visits)
    user <- d[, c(lapply(.SD, sum, na.rm = TRUE),
                  .(tt_visits = sum(visits))), by = caseid, .SDcols = vals]
    setnames(user, vals, paste0("bl_", vals))
    for (m in paste0("bl_", vals))
        set(user, NULL, paste0(m, "_rate"), user[[m]] / user$tt_visits)

    # The rebuilt unblocked exposure must reproduce the published person file.
    # If it does not, the attribution is not faithful and nothing downstream of
    # it can be trusted.
    chk <- merge(user[, .(caseid, bl_ddg_join_ads)],
                 as.data.table(person)[, .(caseid, pub = bl_ddg_join_ads)], by = "caseid")
    if (!isTRUE(all.equal(chk$bl_ddg_join_ads, chk$pub)))
        stop("rebuilt unblocked exposure does not match the published person file",
             call. = FALSE)
    message("  gate: rebuilt unblocked exposure matches the published file exactly")
    merge(user, as.data.table(person)[, .(caseid, gender_lab, race_lab, educ_lab,
                                          agegroup_lab, birthyr)], by = "caseid")
}

# ---------------------------------------------------------------------------
# Does blocking narrow the age gap, or just lower everyone?
# ---------------------------------------------------------------------------
# Blocking lowers exposure for everyone, so the absolute gap between age groups
# falls almost mechanically. A claim that protection is "regressive" is really a
# claim about the gap falling more slowly than the level it sits on, so the gap
# is a log-ratio -- how many times the 65+ mean exceeds the under-25 mean --
# which is scale-free, symmetric between the groups, and does not blow up when
# the denominator is 0.004.
OLD_GROUP <- "65+"; YOUNG_GROUP <- "<25"

log_ratio <- function(d, ycol) {
    a <- mean(d[[ycol]][d$agegroup_lab == OLD_GROUP], na.rm = TRUE)
    b <- mean(d[[ycol]][d$agegroup_lab == YOUNG_GROUP], na.rm = TRUE)
    if (!(a > 0 && b > 0)) return(NA_real_)
    log(a / b)
}

# Resampling panelists, not visits: the panelist is the unit the gap is defined
# over. Our own seed -- R cannot reproduce numpy's PCG64 stream, and freezing
# the draws to a file would dress RNG state up as data.
bootstrap_ci <- function(d, statistic, reps = BOOTSTRAP_REPS, seed = BOOTSTRAP_SEED) {
    set.seed(seed)
    n <- nrow(d)
    draws <- vapply(seq_len(reps),
                    function(i) statistic(d[sample.int(n, n, replace = TRUE), ]),
                    numeric(1))
    stats::quantile(draws, c(0.025, 0.975), na.rm = TRUE, names = FALSE)
}

build_residual_levels <- function(user, path) {
    d <- as.data.frame(user)
    d$agegroup_lab <- factor(as.character(d$agegroup_lab), levels = AGE_ORDER)
    # A third measure order. Tables 2-3 and the prose lead with the attributed
    # measures; Tables 5-6 swap keylogging and session recording; the blocking
    # tables put the behavioural three first, because those are the ones a
    # blocker struggles with. Reproduced rather than unified -- changing any of
    # them alters a published table.
    rows <- lapply(MEASURES_BLOCK, function(m) {
        # Cookies are attributed per domain, so its published baseline is the
        # count of cookie-setting domains, not the count of cookies.
        base <- if (m == "third_party_cookies") "bl_third_party_cookie_domains_rate"
                else paste0("bl_", m, "_rate")
        pub <- mean(d[[base]], na.rm = TRUE)
        cells <- unlist(lapply(names(TIERS), function(t) {
            hi <- mean(d[[sprintf("bl_%s_resid_%s_rate", m, t)]], na.rm = TRUE)
            lo <- mean(d[[sprintf("bl_%s_resid_%s_lo_rate", m, t)]], na.rm = TRUE)
            sprintf("%.3f [%.3f]", hi, lo)
        }))
        surv <- 100 * mean(d[[sprintf("bl_%s_resid_%s_rate", m, HEADLINE_TIER)]],
                           na.rm = TRUE) / pub
        label <- if (m == "third_party_cookies") "Third-Party Cookie Domains" else VAR_LABELS[m]
        c(label, sprintf("%.3f", pub), cells, sprintf("%.1f", surv))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# The headline gap table: how many times the 65+ mean exceeds the under-25 mean
# before and after the strongest tier, and the shift with a bootstrap interval.
# Only the five attributed measures appear -- Facebook Pixel and Google
# Analytics name no responsible domain, so their "residual" equals their
# published level by construction and a gap shift for them is meaningless.
GAP_MEASURES <- c("ddg_join_ads", "third_party_cookies", "canvas_fingerprinting",
                  "session_recording", "key_logging")

build_residual_age_gap <- function(user, path) {
    d <- as.data.frame(user)
    d$agegroup_lab <- factor(as.character(d$agegroup_lab), levels = AGE_ORDER)

    rows <- lapply(GAP_MEASURES, function(m) {
        pre  <- if (m == "third_party_cookies") "bl_third_party_cookie_domains_rate"
                else paste0("bl_", m, "_rate")
        post <- sprintf("bl_%s_resid_%s_rate", m, HEADLINE_TIER)
        shift_of <- function(x) log_ratio(x, post) - log_ratio(x, pre)
        ci <- bootstrap_ci(d, shift_of)
        label <- if (m == "third_party_cookies") "Third-Party Cookie Domains" else VAR_LABELS[m]
        c(label,
          sprintf("%.2f", exp(log_ratio(d, pre))),
          sprintf("%.2f", exp(log_ratio(d, post))),
          sprintf("%+.3f [%+.3f, %+.3f]", shift_of(d), ci[1], ci[2]))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Placebo: is the narrowing what the lists target, or just their size?
# ---------------------------------------------------------------------------
# A blocklist that removes 86% of ad-tracker exposure will move the age gap for
# arithmetic reasons alone. The test asks whether a *random* set of third
# parties removing the same amount moves it as far. Both arms block at the
# level of a third-party host -- the real list blocks a host if the tier stops
# it on any site -- because holding the unit the same is what makes the
# comparison fair. That is why the observed shifts here differ slightly from
# the gap table above, which scores each (site, host) pair separately.
#
# The published code bisected for the cut that matched the real list's removal,
# re-running the exposure sum ~16 times per draw. That is unnecessary: exposure
# is a sum over domains and blocking only ever turns contributions off, so both
# the removed fraction and the two group means are monotone step functions of
# the cut. Evaluating them at *every* cut with one cumulative sum is exact,
# gives the closest cut rather than a bisection's overshoot, and is fast enough
# that no result depends on the draw count.

placebo_inputs <- function(visits, user) {
    people <- as.character(user$caseid)
    totals <- ifelse(user$tt_visits > 0, user$tt_visits, NA_real_)
    grp <- as.character(user$agegroup_lab)

    v <- as.data.table(visits)[as.character(caseid) %chin% people]
    v[, w := visits / totals[match(as.character(caseid), people)]]
    v[, g := grp[match(as.character(caseid), people)]]

    # u_group[d] is domain d's mean contribution to a group's exposure rate, so
    # any group mean is just a sum of these over the domains still live.
    share <- function(keep, n) {
        a <- v[which(keep), .(u = sum(w, na.rm = TRUE) / n), by = private_domain]
        setNames(a$u, a$private_domain)
    }
    list(all = share(rep(TRUE, nrow(v)), nrow(user)),
         old = share(v$g == OLD_GROUP, sum(grp == OLD_GROUP)),
         young = share(v$g == YOUNG_GROUP, sum(grp == YOUNG_GROUP)))
}

# One card's exposure as a function of which third parties survive. A count
# measure is linear in that set, so each third party's cost is fixed and the
# whole step curve is one cumulative sum. A behavioural measure is not: a
# domain keeps flagging until its *last* responsible script goes, so it leaves
# at the largest permutation position among its scripts, which has to be found
# per draw. Both return the three group sums standing after every cut k.
placebo_card <- function(sub, u, kind) {
    dom <- sub$private_domain
    pull <- function(keys) {
        m <- sapply(c("all", "old", "young"), function(nm) {
            x <- u[[nm]][keys]
            ifelse(is.na(x), 0, x)
        })
        matrix(m, ncol = 3, dimnames = NULL)
    }
    univ <- sort(unique(sub$script_domain))
    K <- length(univ)
    step <- function(agg) {
        lost <- matrix(0, K, 3)
        lost[as.integer(rownames(agg)), ] <- agg
        apply(lost, 2, cumsum)
    }

    if (kind == "count") {
        cs <- rowsum(pull(dom), sub$script_domain)
        cs <- cs[match(univ, rownames(cs)), , drop = FALSE]
        base <- colSums(cs)
        live <- function(perm) {
            cum <- apply(cs[match(perm, univ), , drop = FALSE], 2, cumsum)
            sweep(-cum, 2, base, "+")
        }
    } else {
        du <- unique(dom)
        dw <- pull(du)
        base <- colSums(dw)
        live <- function(perm) {
            p <- setNames(seq_along(perm), perm)[sub$script_domain]
            o <- order(p)
            dl <- integer(0)
            dl[dom[o]] <- p[o]
            agg <- rowsum(dw, dl[du])
            sweep(-step(agg), 2, base, "+")
        }
    }
    list(univ = univ, base = base, live = live)
}

build_blocking_placebo <- function(visits, user, path, reps = PLACEBO_DRAWS,
                                   seed = BOOTSTRAP_SEED) {
    u <- placebo_inputs(visits, user)
    scr <- as.data.table(fread(FP_DOMAIN_SCRIPTS))
    pairs <- fread(FP_BLOCKED_PAIRS)
    blocked_host <- pairs[, .(b = any(as.logical(blocked_C))), by = script_domain]
    blocked_real <- setNames(blocked_host$b, blocked_host$script_domain)

    rows <- list()
    for (card in names(CARD_MEASURES)) {
        measure <- CARD_MEASURES[[card]][[1]]
        kind <- CARD_MEASURES[[card]][[2]]
        if (!measure %in% GAP_MEASURES) next
        sub <- scr[card_type == card]
        univ <- sort(unique(sub$script_domain))

        # The real list as one arm of the same machinery: put the blocked hosts
        # first in the "permutation" and cut at exactly how many are blocked.
        is_blk <- !is.na(blocked_real[univ]) & blocked_real[univ]
        real_perm <- c(univ[is_blk], univ[!is_blk])
        card_fn <- placebo_card(sub, u, kind)
        nblk <- sum(is_blk)
        real <- if (nblk > 0) card_fn$live(real_perm)[nblk, ] else card_fn$base
        rc <- card_fn

        pre <- log(rc$base[2]) - log(rc$base[3])
        observed <- log(real[2]) - log(real[3]) - pre
        target <- 1 - real[1] / rc$base[1]

        set.seed(seed + match(measure, GAP_MEASURES))
        shifts <- vapply(seq_len(reps), function(i) {
            lv <- card_fn$live(sample(univ))
            removed <- c(0, 1 - lv[, 1] / rc$base[1])
            k <- which.min(abs(removed - target)) - 1L
            m <- if (k == 0L) rc$base else lv[k, ]
            log(m[2]) - log(m[3]) - pre
        }, numeric(1))
        shifts <- shifts[is.finite(shifts)]

        centre <- median(shifts)
        p <- (1 + sum(abs(shifts - centre) >= abs(observed - centre))) / (1 + length(shifts))
        lab <- if (measure == "third_party_cookies") "Third-Party Cookies" else VAR_LABELS[measure]
        rows[[length(rows) + 1]] <- c(
            lab,
            sprintf("%.1f\\%%", 100 * target),
            sprintf("%+.3f", observed),
            sprintf("%+.3f [%+.3f, %+.3f]", centre,
                    quantile(shifts, .025), quantile(shifts, .975)),
            sprintf("%.3f", p))
    }
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Projection onto CPS margins
# ---------------------------------------------------------------------------
# The panel is a convenience sample with no survey weight, so a raw percentage
# describes these 1,134 people and nobody else. Raking their four demographic
# margins onto the CPS answers a narrower question: if the country browsed the
# way people with these demographics browsed, how many would have met a
# keylogger in a month? It corrects composition, not selection into a metered
# panel -- and it inherits the zero-fill for unscanned domains on top of that.

MARGIN_VARS <- c(gender = "gender_lab", race = "race_lab",
                 educ = "educ_lab", agegroup = "agegroup_lab")
RAKE_TRIM <- c(.025, .975)
PROJ_REPS <- 500

rake <- function(data, targets, max_iter = 200, tol = 1e-8) {
    w <- rep(1, nrow(data))
    for (it in seq_len(max_iter)) {
        before <- w
        for (v in names(MARGIN_VARS)) {
            tg <- targets[targets$variable == v, ]
            want <- setNames(tg$cps_perc / sum(tg$cps_perc), tg$cat)
            col <- as.character(data[[MARGIN_VARS[[v]]]])
            for (cat in names(want)) {
                m <- col == cat
                if (!any(m)) stop("No panelists in ", MARGIN_VARS[[v]], " == ", cat)
                w[m] <- w[m] * want[[cat]] * sum(w) / sum(w[m])
            }
        }
        if (max(abs(w - before)) < tol) break
    }
    w * nrow(data) / sum(w)
}

# Extreme weights would let a handful of panelists drive a national number.
weights_for <- function(data, targets) {
    w <- rake(data, targets)
    b <- quantile(w, RAKE_TRIM, names = FALSE)
    w <- pmin(pmax(w, b[1]), b[2])
    list(w = w * nrow(data) / sum(w), lo = b[1], hi = b[2])
}


build_population_projection <- function(user, path, reps = PROJ_REPS,
                                        seed = BOOTSTRAP_SEED) {
    targets <- as.data.frame(cps_margins())
    d <- as.data.frame(user)
    w0 <- rake(d, targets)

    # Raking that does not reproduce its own targets is not a weight.
    worst <- max(unlist(lapply(names(MARGIN_VARS), function(v) {
        tg <- targets[targets$variable == v, ]
        got <- tapply(w0, as.character(d[[MARGIN_VARS[[v]]]]), sum) / sum(w0) * 100
        abs(got[tg$cat] - tg$cps_perc)
    })))
    if (worst > 0.1) stop("raked margins do not reproduce CPS targets: ", worst)
    cat(sprintf("  gate: raked margins reproduce CPS within %.4f pp\n", worst))

    tw <- weights_for(d, targets)
    deff <- 1 + var(tw$w) / mean(tw$w)^2
    pop <- cps_adult_population()
    cat(sprintf("  design effect %.2f, effective n %.0f; CPS adults %.0fM\n",
                deff, nrow(d) / deff, pop / 1e6))

    cols <- function(m) c(paste0("bl_", m), sprintf("bl_%s_resid_%s", m, HEADLINE_TIER))

    # Re-rake inside every replicate: holding the weights fixed would treat the
    # post-stratification as known rather than estimated and understate the
    # interval.
    set.seed(seed)
    draws <- array(NA_real_, c(reps, length(GAP_MEASURES), 2))
    for (b in seq_len(reps)) {
        s <- d[sample.int(nrow(d), nrow(d), replace = TRUE), ]
        wb <- tryCatch(weights_for(s, targets)$w, error = function(e) NULL)
        if (is.null(wb)) next
        for (j in seq_along(GAP_MEASURES)) for (k in 1:2)
            draws[b, j, k] <- weighted.mean(s[[cols(GAP_MEASURES[j])[k]]] > 0, wb)
    }
    ok <- mean(!is.na(draws[, 1, 1]))
    cat(sprintf("  usable replicates: %.0f%%\n", 100 * ok))

    rows <- lapply(seq_along(GAP_MEASURES), function(j) {
        m <- GAP_MEASURES[j]
        cell <- function(k) {
            share <- weighted.mean(d[[cols(m)[k]]] > 0, tw$w)
            q <- quantile(draws[, j, k], c(.025, .975), na.rm = TRUE, names = FALSE)
            sprintf("%.1f [%.1f, %.1f]", pop * share / 1e6,
                    pop * q[1] / 1e6, pop * q[2] / 1e6)
        }
        lab <- if (m == "third_party_cookies") "Third-Party Cookies" else VAR_LABELS[m]
        c(lab,
          sprintf("%.1f", 100 * mean(d[[cols(m)[1]]] > 0)),
          sprintf("%.1f", 100 * weighted.mean(d[[cols(m)[1]]] > 0, tw$w)),
          cell(1), cell(2))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Does anything turn on trusting a scan that found nothing?
# ---------------------------------------------------------------------------
# Blacklight loads one anonymous, logged-out page per domain. Where the tracking
# happens behind a login that returns nothing, and the domain enters every
# estimate as a genuine zero -- 23.8% of successful scans, carrying 19.5% of
# panel visits, facebook.com alone 7.2%. The paper's validity work bounds the
# *unscanned* stratum; nothing bounds this one.
#
# Classifying these domains would need work this data cannot support (Tracker
# Radar profiles facebook and amazon precisely for being third parties
# elsewhere, so membership cannot separate a walled garden from a redirect
# hop). So ask the narrower question that needs no classification: does any
# conclusion turn on the zero? Three readings side by side --
#   published  they contribute zero to numerator and denominator
#   excluded   their visits leave both, so rates describe only what was seen
#   imputed    they get the mean of domains that did show tracking, the most
#              generous reading available
ALLZERO_SPECS <- c("published", "excluded", "imputed")

# Where the baseline is a different quantity from the published measure, the row
# has to say so rather than inherit the published measure's name.
BASE_COLUMN <- c(third_party_cookies = "bl_third_party_cookie_domains")

allzero_person_rates <- function(visits, dom, spec) {
    extra <- "third_party_cookie_domains"
    src <- c(MEASURES_BLOCK, sprintf("%s_resid_%s", MEASURES_BLOCK, HEADLINE_TIER), extra)
    cols <- paste0("bl_", src)

    d <- merge(as.data.table(visits), dom[, c("private_domain", "all_zero", src),
                                          with = FALSE],
               by = "private_domain", all.x = TRUE, sort = FALSE)
    az <- !is.na(d$all_zero) & d$all_zero
    # The measures arrive as integer counts and flags. Writing a mean into an
    # integer column truncates it silently -- a 0.05 canvas rate lands as 0 and
    # the imputation looks like it did nothing -- so widen them first.
    for (s2 in src) if (!is.double(d[[s2]])) set(d, NULL, s2, as.numeric(d[[s2]]))

    if (spec == "excluded") {
        d <- d[!az]
    } else if (spec == "imputed") {
        # Mean over domains that did show tracking, so the fill is "an average
        # measured site" rather than an average including the zeros themselves.
        nz <- dom[!(all_zero)]
        for (s in src) set(d, which(az), s, mean(nz[[s]], na.rm = TRUE))
    }
    num <- d[, lapply(.SD, function(x) sum(as.numeric(ifelse(is.na(x), 0, x)) * visits)),
             by = caseid, .SDcols = src]
    setnames(num, src, cols)
    den <- d[, .(den = sum(visits)), by = caseid]
    r <- merge(num, den, by = "caseid")
    r[, (cols) := lapply(.SD, function(x) x / den), .SDcols = cols]
    r[, den := NULL][]
}

build_allzero_sensitivity <- function(resid, bl, visits, user, path) {
    # The residual frame carries only what a blocklist leaves; the published
    # levels it is measured against come from the scans themselves.
    dom <- merge(as.data.table(resid), as.data.table(bl), by = "filename")
    dom[, private_domain := gsub("_", ".", filename, fixed = TRUE)]
    dom[, all_zero := rowSums(.SD) == 0, .SDcols = MEASURES_BLOCK]
    demo <- as.data.table(user)[, .(caseid, gender_lab, race_lab, educ_lab, agegroup_lab)]

    v <- merge(as.data.table(visits), dom[, .(private_domain, all_zero)],
               by = "private_domain", all.x = TRUE, sort = FALSE)
    cat(sprintf("  all-zero scans: %s of %s domains (%.1f%%), %.1f%% of visits\n",
                format(sum(dom$all_zero), big.mark = ","), format(nrow(dom), big.mark = ","),
                100 * mean(dom$all_zero),
                100 * sum(v$visits[!is.na(v$all_zero) & v$all_zero]) / sum(v$visits)))

    fits <- lapply(ALLZERO_SPECS, function(s)
        merge(allzero_person_rates(visits, dom, s), demo, by = "caseid"))
    names(fits) <- ALLZERO_SPECS

    rows <- lapply(GAP_MEASURES, function(m) {
        lab <- if (m %in% names(BASE_COLUMN)) "Third-Party Cookie Domains" else VAR_LABELS[m]
        cells <- vapply(ALLZERO_SPECS, function(s) {
            d <- as.data.frame(fits[[s]])
            co <- fit_demo(paste0("bl_", m), d)
            a <- co[co$term == AGE_TERM_LABEL, ]
            sprintf("%.3f (%+.3f%s)", mean(d[[paste0("bl_", m)]]), a$b, stars(a$p))
        }, character(1))
        c(lab, cells)
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Everything this module writes, in one place.
# ---------------------------------------------------------------------------
emit_blocking <- function(bl, person, visits) {
    resid <- build_residual_domain(bl)
    user <- build_residual_person(resid, bl, person)

    build_residual_levels(user, file.path(TABLES_DIR, "residual_levels"))
    build_residual_age_gap(user, file.path(TABLES_DIR, "residual_age_gap"))
    build_blocking_placebo(visits, user, file.path(TABLES_DIR, "blocking_placebo"))
    build_population_projection(user, file.path(TABLES_DIR, "population_projection"))
    build_allzero_sensitivity(resid, bl, visits, user,
                              file.path(TABLES_DIR, "allzero_sensitivity"))
    build_robustness_age_coding(user, file.path(TABLES_DIR, "robustness_age_coding"))
    invisible(user)
}

# ---------------------------------------------------------------------------
# Does the blocking result depend on how age is coded?
# ---------------------------------------------------------------------------
# The residual age effect is reported for one age coding -- 65+ against under-25
# in binned form. If the conclusion turned on that choice it would not be much of
# a conclusion, so the same quantity is recomputed four ways: the paper's bins,
# 65+ against everyone else, a continuous per-decade gradient, and a binary
# "encountered it at all" outcome restricted to the two end groups.
#
# Cells are the residual effect as a percentage of the unblocked one. Near 100
# means a blocklist leaves the age gap where it found it; near 0 means it closes
# it. The binary column reads differently from the other three by construction:
# where a measure reaches nearly everyone before and after blocking, a
# whether-at-all outcome has almost no variation left to explain.
AGE_CODINGS <- c("bins", "vs_rest", "continuous", "binary")
CONTROLS_NOAGE <- FORMULA_RHS_NOAGE

age_effect <- function(yvar, data, spec) {
    d <- as.data.frame(data)
    d$agegroup_lab <- factor(as.character(d$agegroup_lab), levels = AGE_ORDER)
    grab <- function(m, term, scale = 1) {
        ct <- lmtest::coeftest(m, vcov. = sandwich::vcovHC(m, type = "HC1"))
        c(b = scale * ct[term, 1], p = ct[term, 4])
    }
    if (spec == "bins") {
        co <- fit_demo(yvar, d)
        a <- co[co$term == AGE_TERM_LABEL, ]
        return(c(b = a$b, p = a$p))
    }
    if (spec == "vs_rest") {
        d$age65 <- as.integer(d$agegroup_lab == OLD_GROUP)
        return(grab(lm(as.formula(paste(yvar, "~ age65 +", CONTROLS_NOAGE)), d), "age65"))
    }
    if (spec == "continuous") {
        # birthyr runs backwards against age, so negate to read as "per decade
        # older" and keep the sign comparable with the other codings.
        return(grab(lm(as.formula(paste(yvar, "~ birthyr +", CONTROLS_NOAGE)), d),
                    "birthyr", scale = -10))
    }
    d <- d[d$agegroup_lab %in% c(OLD_GROUP, YOUNG_GROUP), ]
    d$any_exposure <- as.integer(d[[yvar]] > 0)
    d$age65 <- as.integer(d$agegroup_lab == OLD_GROUP)
    grab(lm(as.formula(paste("any_exposure ~ age65 +", CONTROLS_NOAGE)), d), "age65")
}

build_robustness_age_coding <- function(user, path) {
    rows <- lapply(GAP_MEASURES, function(m) {
        pre <- if (m == "third_party_cookies") "bl_third_party_cookie_domains_rate"
               else paste0("bl_", m, "_rate")
        post <- sprintf("bl_%s_resid_%s_rate", m, HEADLINE_TIER)
        lab <- if (m == "third_party_cookies") "Third-Party Cookie Domains" else VAR_LABELS[[m]]
        c(lab, vapply(AGE_CODINGS, function(s) {
            a <- age_effect(pre, user, s); b <- age_effect(post, user, s)
            sprintf("%.0f", 100 * b[["b"]] / a[["b"]])
        }, character(1)))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    out <- out[order(out[[1]]), ]
    write_tex(out, path)
    invisible(out)
}
