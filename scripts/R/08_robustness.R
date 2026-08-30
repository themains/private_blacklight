# 08_robustness.R
# Does the age gap survive the choices behind it: the rate's denominator, the
# treatment of unscanned visits, and the date the web was measured.

# ---------------------------------------------------------------------------
# Robustness: does the age gap survive the rate's denominator?
# ---------------------------------------------------------------------------
# Dividing each panelist's encounters by their own visits gives equal weight to
# a rate estimated from two visits and one estimated from forty thousand. Two
# alternatives: drop the imprecise denominators, and weight panelists by visits
# (which asks about the average visit rather than the average person).
AGE_TERM <- 'relevel(factor(agegroup_lab), ref = "<25")65+'
VISIT_THRESHOLDS <- c(10, 50, 100, 250)

age_gap <- function(yvar, data, weights = NULL) {
    data$agegroup_lab <- factor(as.character(data$agegroup_lab), levels = AGE_ORDER)
    f <- as.formula(paste(yvar, "~", FORMULA_RHS))
    m <- if (is.null(weights)) lm(f, data = data) else lm(f, data = data, weights = data[[weights]])
    ct <- lmtest::coeftest(m, vcov. = sandwich::vcovHC(m, type = "HC1"))
    ct[AGE_TERM, c(1, 2, 4)]
}

build_robustness_denominator <- function(data, path) {
    specs <- c(
        list(list("Published (all panelists)", data, NULL)),
        lapply(VISIT_THRESHOLDS, function(k)
            list(sprintf("Drop $<%d$ visits", k), data[data$tt_visits >= k, ], NULL)),
        list(list("Visit-weighted", data, "tt_visits"))
    )
    outcomes <- c("bl_ddg_join_ads_rate", "bl_third_party_cookies_rate")
    rows <- lapply(specs, function(s) {
        cells <- unlist(lapply(outcomes, function(y) {
            e <- age_gap(y, s[[2]], s[[3]])
            c(sprintf("%.3f%s", e[1], stars(e[3])), sprintf("(%.3f)", e[2]))
        }))
        c(s[[1]], formatC(nrow(s[[2]]), format = "d", big.mark = ","), cells)
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Gap benchmarks: put each coefficient on comparable scales
# ---------------------------------------------------------------------------
# Table 5 reports gaps in raw units. To compare them against disparities
# reported elsewhere, re-express each as (i) a percentage of its reference
# group's mean and (ii) Cohen's d against the pooled user-level SD.
BENCH_GROUPS <- list(
    c("Woman", "gender_lab", "Male"),
    c("Educ: College", "educ_lab", "HS or Below"),
    c("Educ: Postgraduate", "educ_lab", "HS or Below"),
    c("Age: 65+", "agegroup_lab", "<25"),
    c("Race: Asian", "race_lab", "White")
)
BENCH_OUTCOMES <- list(
    c("bl_ddg_join_ads_rate", "Ad trackers / visit"),
    c("bl_third_party_cookies_rate", "Third-party cookies / visit")
)

build_gap_benchmarks <- function(data, path) {
    rows <- list()
    for (o in BENCH_OUTCOMES) {
        res <- fit_demo(o[1], data)
        pooled_sd <- sd(data[[o[1]]], na.rm = TRUE)
        for (g in BENCH_GROUPS) {
            i <- match(g[1], res$term)
            ref_mean <- mean(data[[o[1]]][data[[g[2]]] == g[3]], na.rm = TRUE)
            rows[[length(rows) + 1]] <- c(
                o[2], g[1],
                paste0(sprintf("%.2f", res$b[i]), stars(res$p[i])),
                sprintf("%.2f", ref_mean),
                sprintf("%+.0f", 100 * res$b[i] / ref_mean),
                sprintf("%.2f", res$b[i] / pooled_sd)
            )
        }
    }
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Coefficient plots (Figures 4 and 5)
# ---------------------------------------------------------------------------
# Same fitted objects that fill Tables 5 and 6, so figure and table cannot
# drift. Four properties are deliberate and were defects in the original R:
#   - saved near the printed size, so type reaches the page at 8-9pt rather
#     than the 5.3pt a 16x10 canvas scaled to \textwidth produced;
#   - a real en dash in the age labels (a plot device is not LaTeX);
#   - cumulative panels marked "(00s)" and the top-organisation panel named for
#     what it regresses (visits, not share);
#   - significant markers actually black, as the caption claims.
suppressPackageStartupMessages(library(ggplot2))

build_coefplot <- function(data, yvars, titles, path) {
    df <- do.call(rbind, Map(function(y, ttl) {
        r <- fit_demo(y, data)
        r$panel <- ttl
        r$lo <- r$b - 1.96 * r$se
        r$hi <- r$b + 1.96 * r$se
        r$sig <- !is.na(r$p) & r$p < 0.05
        r
    }, yvars, titles))
    df$panel <- factor(df$panel, levels = titles)
    df$term  <- factor(gsub("--", "–", df$term, fixed = TRUE),
                       levels = rev(gsub("--", "–", COEF_ORDER, fixed = TRUE)))

    p <- ggplot(df, aes(x = b, y = term)) +
        geom_reference() +
        geom_errorbarh(aes(xmin = lo, xmax = hi), height = 0,
                       colour = C_INTERVAL, linewidth = 0.6) +
        geom_point(aes(colour = sig), size = 1.5) +
        scale_colour_manual(values = c(`TRUE` = C_SIGNIFICANT, `FALSE` = C_NULL),
                            guide = "none") +
        # Two columns, not four: at 6.5in a 4-across layout leaves each panel
        # 1.5in, which clips "Google Analytics (Remarketing)" and runs adjacent
        # x tick labels into each other.
        facet_wrap(~panel, ncol = 2, scales = "free_x") +
        scale_x_continuous(n.breaks = 4) +
        labs(x = "Estimate and 95% conf. int.", y = NULL) +
        theme_blacklight(grid = "x") +
        theme(panel.spacing.x = unit(1.2, "lines"))

    save_fig(p, path, width = FIG_FULL_W, height = 8.0)
    invisible(df)
}


# ---------------------------------------------------------------------------
# Do the coverage and timing threats move the demographic comparisons?
# ---------------------------------------------------------------------------
emit_all <- function(data) {
    cum <- data
    for (c_ in RESCALE_100) cum[[c_]] <- cum[[c_]] / 100

    # Tables 2-3: exposure per panelist
    emit_float(build_exposure_summary(data, "cumulative",
        file.path(TABLES_DIR, "individual_blacklight_cumulative_exposure_summary")), "tab2")
    emit_float(build_exposure_summary(data, "rate",
        file.path(TABLES_DIR, "individual_blacklight_exposure_rate_summary")), "tab3")

    # Tables 5-6: demographic differences
    emit_float(build_demo_table(data, c(paste0("bl_", MEASURES, "_rate"), "top_org_share"),
                     c(SHORT[MEASURES], "Top org share"), 3,
                     file.path(TABLES_DIR, "demo_differences_exposure_rate")), "tab6")
    tab5 <- build_demo_table(cum, c(paste0("bl_", MEASURES), "top_org_visits"),
                     c(ifelse(paste0("bl_", MEASURES) %in% RESCALE_100,
                              paste0(SHORT[MEASURES], " (00s)"), SHORT[MEASURES]),
                       "Top org visits (00s)"), 2,
                     file.path(TABLES_DIR, "demo_differences_cum_exposure"))
    emit_float(tab5, "tab5")

    # Cells the results section quotes. Ad trackers, cookies and top-org visits
    # are modelled in hundreds here, so `scale` puts them back on the raw count
    # the prose uses. Getting that wrong is invisible when reading the table
    # beside the sentence, which is how these drifted in the first place.
    m5 <- attr(tab5, "models")
    num_coef("CumColCookies", m5, "Cookies (00s)", "Educ: College", scale = 100)
    num_coef("CumColSessionRec", m5, "Session rec", "Educ: College")
    num_coef("CumWomanCanvas", m5, "Canvas FP", "Woman")

    build_robustness_denominator(data, file.path(TABLES_DIR, "robustness_denominator"))
    suppressWarnings(build_presence_adjusted(
        data, file.path(TABLES_DIR, "presence_adjusted_median")))
    build_gap_benchmarks(data, file.path(TABLES_DIR, "implications_gap_benchmarks"))

    # Descriptive exhibits
    d <- build_demo_summary(data, file.path(TABLES_DIR, "demo_summary"))
    build_demo_summary_n(file.path(TABLES_DIR, "demo_summary_n"))
    build_demo_summary_note(d, file.path(TABLES_DIR, "demo_summary_note"))
    emit_float(build_top_contributors(BL_DOMAIN,
        file.path(TABLES_DIR, "bl_top_contributors_domain")), "tab4")

    build_risk_divergence(data, file.path(TABLES_DIR, "risk_divergence_by_age"))

    # Why the age gap exists, and whether it survives the obvious alternatives.
    build_age_gap_decomposition(BL_DOMAIN, data,
        file.path(TABLES_DIR, "age_gap_decomposition"))
    build_age_spline_tests(data, file.path(TABLES_DIR, "age_spline_tests"))
    build_device_age_gradient(data, file.path(TABLES_DIR, "device_age_gradient"))
    build_cum_exposure(BL_DOMAIN, file.path(TABLES_DIR, "cum_exposure_by_hour"),
                       file.path(FIGURES_DIR, "cum_exposure_by_hour"))

    # Organization tracking (Figure 5): four panels sharing one grammar.
    build_distribution(data$n_orgs, "Number of organizations",
                       file.path(FIGURES_DIR, "dist_org_per_user_summtable"))
    build_distribution(data$gini_exposure[!is.na(data$gini_exposure)],
                       "Gini across organizations",
                       file.path(FIGURES_DIR, "dist_tracking_concentration_per_user_summtable"))
    build_distribution(100 * data$top_org_share,
                       "Share of visits seen by the top organization (%)",
                       file.path(FIGURES_DIR, "dist_maxshare_hist_summtable"))
    build_distribution(100 * data$top_org_share_duration,
                       "Share of browsing time seen by the top organization (%)",
                       file.path(FIGURES_DIR, "dist_maxshare_hist_duration_summtable"))
    build_reach_dominance(ORG_REACH,
                          file.path(FIGURES_DIR, "top_trackers_reach_dominance_annotated_top_orgs"))

    build_coefplot(data, c(paste0("bl_", MEASURES, "_rate"), "top_org_share"),
                   c(VAR_LABELS[MEASURES], "Top organization share"),
                   file.path(FIGURES_DIR, "coefplot_demo_differences_rate"))
    build_coefplot(cum, c(paste0("bl_", MEASURES), "top_org_visits"),
                   c(VAR_LABELS[MEASURES], "Top organization visits (00s)"),
                   file.path(FIGURES_DIR, "coefplot_demo_differences_cumulative"))
    build_lowess_age(data, file.path(FIGURES_DIR, "lowess_age_bl"))
    invisible(NULL)
}

# ---------------------------------------------------------------------------
# Holding volume constant without assuming exposure is proportional to it
# ---------------------------------------------------------------------------
# The paper reports demographic differences two ways, and what separates them is
# how each holds browsing volume constant. Dividing cumulative exposure by visits
# *imposes* proportionality. The alternative does not: it puts volume and volume
# squared on the right-hand side of a median regression on cumulative exposure
# and lets the data say whether the relationship is proportional, concave, or
# something else. Reporting both is what makes the movement between the two
# panels read as a fact about the phenomenon rather than about the arithmetic.
#
# Median regression is a linear program. quantreg's Barrodale-Roberts simplex
# solves it exactly, which is why it is used here rather than the iteratively
# reweighted least squares the published pipeline had to re-solve: that
# approximation moved the Age 65+ coefficient about 1% under a pure rescaling of
# the outcome, which is solver tolerance, not data.
PRESENCE_TERMS <- c("visits_scaled", "I(visits_scaled^2)")
PRESENCE_LABELS <- c("Total visits (scaled)", "Total visits$^2$ (scaled)")
PRESENCE_EXTRA <- c(top_org_visits = "Top organization visits")

# Map onto the unit interval, the scaling this adjustment conventionally uses.
rescale01 <- function(x) (x - min(x)) / (max(x) - min(x))

presence_formula <- function(yvar, presence) {
    rhs <- if (presence) paste(c(FORMULA_RHS, PRESENCE_TERMS), collapse = " + ")
           else FORMULA_RHS
    as.formula(paste(yvar, "~", rhs))
}

fit_median <- function(yvar, data, presence) {
    quantreg::rq(presence_formula(yvar, presence), tau = 0.5, data = data,
                 method = "br")
}

# Panelists are the unit of independent variation, so panelists are what gets
# resampled -- xy-pair resampling, not residual resampling, which would assume
# the fitted model.
presence_se <- function(yvar, data, presence, reps = BOOTSTRAP_REPS,
                        seed = BOOTSTRAP_SEED) {
    mf <- model.frame(presence_formula(yvar, presence), data = data)
    x <- model.matrix(attr(mf, "terms"), mf)
    set.seed(seed)
    b <- quantreg::boot.rq(x, model.response(mf), tau = 0.5, R = reps,
                           bsmethod = "xy")
    setNames(apply(b$B, 2, sd), colnames(x))
}

# The CPS denominator printed in Table 1's header. It was hand-typed once;
# deriving it from the same archive the margins come from is what keeps it from
# drifting away from them.
build_demo_summary_n <- function(path) {
    d <- fread(cmd = sprintf("unzip -p %s pppub22.csv",
                             shQuote(file.path(DATA_DIR, "cps", "asecpub22csv.zip"))),
               select = "A_AGE", showProgress = FALSE)
    n <- sum(d$A_AGE >= 18)
    if (!grepl("\\.tex$", path)) path <- paste0(path, ".tex")
    cat(gsub(",", "{,}", formatC(n, format = "d", big.mark = ",")), file = path)
    invisible(n)
}

build_presence_adjusted <- function(data, path, reps = BOOTSTRAP_REPS,
                                    seed = BOOTSTRAP_SEED) {
    d <- as.data.frame(data)
    d$agegroup_lab <- factor(as.character(d$agegroup_lab), levels = AGE_ORDER)
    d$visits_scaled <- rescale01(d$tt_visits)

    outcomes <- c(setNames(SHORT[MEASURES], paste0("bl_", MEASURES)), PRESENCE_EXTRA)
    cell <- function(b, se, p) sprintf("%s%s (%s)",
        formatC(b, format = "f", digits = 0, big.mark = ","), stars(p),
        formatC(se, format = "f", digits = 0, big.mark = ","))

    # Median regression on tied count outcomes has a *face* of optima, not a
    # vertex: two exact solvers reach the same objective to 1e-8 and disagree on
    # coefficients. That is a property of the estimand on this data, not a bug,
    # and it means the printed precision overstates what is identified for the
    # sparse measures. Solve with the deterministic simplex, and report how far
    # a second exact solver moves each fit so the reader sees the spread. The
    # cells the manuscript quotes were checked individually: six of eight are
    # identical across solvers, the other two move by 0.3% and 2.2%.
    spread <- function(yvar, presence) {
        a <- coef(fit_median(yvar, d, presence))
        b <- coef(quantreg::rq(presence_formula(yvar, presence), tau = 0.5,
                               data = d, method = "fn"))[names(a)]
        max(abs(a - b))
    }

    # The manuscript quotes individual cells of this table, so the raw
    # estimates are kept alongside the formatted ones and registered below.
    # Re-fitting to recover them would repeat the bootstrap.
    raw <- new.env(parent = emptyenv())
    one <- function(yvar, presence) {
        f <- fit_median(yvar, d, presence)
        se <- presence_se(yvar, d, presence, reps, seed)
        b <- coef(f)
        term <- COEF_MAP[names(b)]
        term[names(b) %in% PRESENCE_TERMS] <-
            PRESENCE_LABELS[match(names(b)[names(b) %in% PRESENCE_TERMS], PRESENCE_TERMS)]
        p <- 2 * (1 - pnorm(abs(b / se[names(b)])))
        raw[[paste0(yvar, if (presence) ".B" else ".A")]] <-
            data.frame(term = unname(term), b = unname(b),
                       se = unname(se[names(b)]), p = unname(p),
                       row.names = NULL, stringsAsFactors = FALSE)
        setNames(cell(b, se[names(b)], p), term)
    }

    order_raw <- COEF_ORDER
    order_pres <- c(COEF_ORDER, PRESENCE_LABELS)
    panel <- function(presence, ord) {
        cols <- lapply(names(outcomes), function(y) {
            v <- one(y, presence); out <- v[ord]; out[is.na(out)] <- ""; out
        })
        m <- cbind(ord, do.call(cbind, cols))
        apply(m, 1, function(r) paste0(paste(r, collapse = " & "), " \\\\"))
    }

    for (y in names(outcomes)) cat(sprintf(
        "  %-24s solver spread: panel A %.1f, panel B %.1f\n", y,
        spread(y, FALSE), spread(y, TRUE)))

    ncol <- length(outcomes) + 1L
    head <- function(t) sprintf("\\multicolumn{%d}{l}{\\textit{%s}} \\\\", ncol, t)
    lines <- c(head("Panel A. Demographics only"), panel(FALSE, order_raw),
               "\\addlinespace",
               head("Panel B. Demographics and browsing volume"),
               panel(TRUE, order_pres))
    if (!grepl("\\.tex$", path)) path <- paste0(path, ".tex")
    cat(paste(lines, collapse = "\n"), file = path)

    # The cells the text quotes, from the same fits that filled the table.
    pres <- function(stem, yvar, panel, term) {
        r <- raw[[paste0(yvar, ".", panel)]]
        i <- match(term, r$term)
        if (is.na(i)) stop("no term '", term, "' in ", yvar, call. = FALSE)
        num(paste0(stem, "B"), tex_num(r$b[i]))
        num(paste0(stem, "SE"), tex_num(r$se[i]))
        num(paste0(stem, "P"), fmt_p(r$p[i]))
    }
    pres("PresColAdVolFree", "bl_ddg_join_ads", "A", "Educ: College")
    pres("PresColAdVolHeld", "bl_ddg_join_ads", "B", "Educ: College")
    pres("PresOldAd",        "bl_ddg_join_ads", "B", "Age: 65+")
    pres("PresOldCookies",   "bl_third_party_cookies", "B", "Age: 65+")
    pres("PresAsianAd",      "bl_ddg_join_ads", "B", "Race: Asian")
    invisible(lines)
}
