# 07_demography.R
# Demographic differences in exposure: the paper's Tables 5 and 6, the two
# coefficient plots, and the birth-year curve. OLS with Huber-White (HC1)
# errors; references male / white / HS or below / under 25.

COEF_ORDER <- c("Woman", "Race: African American", "Race: Asian", "Race: Hispanic",
                "Race: Other", "Educ: Some college", "Educ: College",
                "Educ: Postgraduate", "Age: 25--34", "Age: 35--49", "Age: 50--64",
                "Age: 65+")

COEF_MAP <- c(
    "relevel(factor(gender_lab), ref = \"Male\")Female"          = "Woman",
    "relevel(factor(race_lab), ref = \"White\")Black"            = "Race: African American",
    "relevel(factor(race_lab), ref = \"White\")Asian"            = "Race: Asian",
    "relevel(factor(race_lab), ref = \"White\")Hispanic"         = "Race: Hispanic",
    "relevel(factor(race_lab), ref = \"White\")Other"            = "Race: Other",
    "relevel(factor(educ_lab), ref = \"HS or Below\")Some college" = "Educ: Some college",
    "relevel(factor(educ_lab), ref = \"HS or Below\")College"    = "Educ: College",
    "relevel(factor(educ_lab), ref = \"HS or Below\")Postgrad"   = "Educ: Postgraduate",
    "relevel(factor(agegroup_lab), ref = \"<25\")25-34"          = "Age: 25--34",
    "relevel(factor(agegroup_lab), ref = \"<25\")35-49"          = "Age: 35--49",
    "relevel(factor(agegroup_lab), ref = \"<25\")50-64"          = "Age: 50--64",
    "relevel(factor(agegroup_lab), ref = \"<25\")65+"            = "Age: 65+"
)

fit_demo <- function(yvar, data, rhs = FORMULA_RHS) {
    data <- data[!is.na(data[[yvar]]), ]
    # agegroup_lab is ordered; relevel() on an ordered factor would emit
    # polynomial contrasts, so drop the ordering first.
    data$agegroup_lab <- factor(as.character(data$agegroup_lab), levels = AGE_ORDER)
    f <- as.formula(paste(yvar, "~", rhs))
    m <- lm(f, data = data)
    ct <- lmtest::coeftest(m, vcov. = sandwich::vcovHC(m, type = "HC1"))
    out <- data.frame(term = COEF_MAP[rownames(ct)], b = ct[, 1], se = ct[, 2],
                      p = ct[, 4], row.names = NULL, stringsAsFactors = FALSE)
    out <- out[match(COEF_ORDER, out$term), ]
    out$term <- COEF_ORDER
    attr(out, "r2") <- summary(m)$r.squared
    attr(out, "n")  <- nobs(m)
    attr(out, "ymean") <- mean(data[[yvar]])
    out
}

# fixest's number format: `digits` significant figures, capped at `digits`
# decimal places. 2.809 -> 2.81, 0.0350 -> 0.035.
fmt_fixest <- function(x, digits) {
    if (is.na(x)) return("")
    if (x == 0) return(formatC(0, format = "f", digits = digits))
    dp <- min(max(digits - 1 - floor(log10(abs(x))), 0), digits)
    out <- formatC(x, format = "f", digits = dp)
    if (startsWith(out, "-0.") && as.numeric(out) == 0) substring(out, 2) else out
}

build_demo_table <- function(data, yvars, headers, digits, path) {
    models <- lapply(yvars, fit_demo, data = data)
    names(models) <- headers

    body <- list()
    for (i in seq_along(COEF_ORDER)) {
        coefs <- vapply(models, function(m) {
            s <- stars(m$p[i])
            paste0(fmt_fixest(m$b[i], digits), if (nzchar(s)) sprintf("$^{%s}$", s) else "")
        }, character(1))
        ses <- vapply(models, function(m) sprintf("(%s)", fmt_fixest(m$se[i], digits)),
                      character(1))
        body[[length(body) + 1]] <- c(COEF_ORDER[i], coefs)
        body[[length(body) + 1]] <- c("", ses)
    }
    stat_row <- function(lab, f) c(lab, vapply(models, f, character(1)))
    body[[length(body) + 1]] <- stat_row("Dependent variable mean",
        function(m) fmt_fixest(attr(m, "ymean"), digits))
    body[[length(body) + 1]] <- stat_row("R$^2$",
        function(m) formatC(attr(m, "r2"), format = "f", digits = 3))
    body[[length(body) + 1]] <- stat_row("Observations",
        function(m) formatC(attr(m, "n"), format = "d", big.mark = ","))

    out <- as.data.frame(do.call(rbind, body), stringsAsFactors = FALSE)
    write_tex(out, path)
    # The formatted body, so the float wrapper can reuse it; the fitted models
    # ride along for anything that needs the estimates themselves.
    structure(out, models = models)
}


# ---------------------------------------------------------------------------
# Exposure rate by birth year (Figure 4)
# ---------------------------------------------------------------------------
# Each measure winsorized at the 95th percentile, z-standardized, then LOWESS
# smoothed, so seven measures on different scales share one axis. Reference
# lines sit at 2022 - age, the same convention constants.AGE_BINS uses.
#
# Sized at \textwidth (6.5in) rather than the 11.2in the matplotlib version
# used: at .55\textwidth that canvas scaled to 0.33 and put the legend on the
# page at about 3pt.
build_lowess_age <- function(data, path, width = FIG_FULL_W, height = 3.8) {
    grid <- seq(min(data$birthyr), max(data$birthyr), length.out = 200)
    curves <- do.call(rbind, lapply(seq_along(MEASURES), function(i) {
        v <- data[[paste0("bl_", MEASURES[i], "_rate")]]
        v <- pmin(v, quantile(v, 0.95, na.rm = TRUE))
        v <- (v - mean(v, na.rm = TRUE)) / sd(v, na.rm = TRUE)
        lo <- stats::lowess(data$birthyr, v, f = 0.5, iter = 3)
        data.frame(birthyr = grid,
                   value = stats::approx(lo$x, lo$y, xout = grid, rule = 2)$y,
                   measure = VAR_LABELS[MEASURES[i]])
    }))
    curves$measure <- factor(curves$measure, levels = VAR_LABELS[MEASURES])
    refs <- data.frame(age = c(25, 35, 50, 65), birthyr = 2022 - c(25, 35, 50, 65))

    p <- ggplot(curves, aes(birthyr, value, colour = measure, linetype = measure)) +
        geom_vline(data = refs, aes(xintercept = birthyr), linetype = "dashed",
                   colour = "grey50", linewidth = 0.3, alpha = 0.8) +
        geom_text(data = refs, aes(x = birthyr, y = Inf, label = paste("Age", age)),
                  inherit.aes = FALSE, angle = 90, hjust = 1.1, vjust = -0.4,
                  size = 2.4, colour = "grey30") +
        geom_line(linewidth = 0.7) +
        scale_colour_manual(values = setNames(PALETTE7, VAR_LABELS[MEASURES])) +
        scale_linetype_manual(values = setNames(LINETYPES7, VAR_LABELS[MEASURES])) +
        labs(x = "Birth year", y = "Exposure rate (z-scores)",
             colour = NULL, linetype = NULL) +
        theme_blacklight(grid = "both") +
        guides(colour = guide_legend(nrow = 2), linetype = guide_legend(nrow = 2))

    save_fig(p, path, width = width, height = height)
    invisible(curves)
}


# ---------------------------------------------------------------------------
# Why are older panelists more exposed: what they browse, or which sites?
# ---------------------------------------------------------------------------
# "Older users encounter more trackers" is a fact without a mechanism, and two
# readings fit it. Older panelists might spend their time in categories that are
# more heavily tracked -- the gap would then be about *what* they browse. Or,
# within the same categories, they might land on more heavily tracked sites, in
# which case it is about *which* sites they choose. The remedies differ, so the
# two are worth separating.
#
# Write a group's exposure as a sum over categories of
#   (share of visits in the category) x (tracking per visit in that category)
# and the gap between two groups splits into
#   composition   different category mix, holding tracking intensity fixed
#   site choice   different tracking within the same categories, holding mix fixed
#   interaction   the residual cross term
#
# A shift-share is preferred to a regression Oaxaca here because it reads
# directly off observed quantities and sidesteps the choice of reference
# coefficients. Both base groups are reported: the split is not symmetric in
# which group supplies the weights.
#
# Categories are read per visit, from realityMine_web's own label column. The
# domain-level map in data/yg/domain_categories.csv is NOT usable for this --
# collapsing to the domain hands a portal every label any of its pages ever
# carried, so all 986,722 google.com visits come back "Job Related". The earlier
# version of this analysis was confined to the visits the two device files
# labelled and carried a gate checking that subsample's age gap resembled the
# full-sample one. Reading the source file directly covers the whole panel, so
# there is no subsample left to vouch for and the gate has no job to do.
DECOMP_MEASURES <- c("ddg_join_ads", "third_party_cookies",
                     "canvas_fingerprinting", "session_recording")
UNCATEGORISED <- "(uncategorised)"
DECOMP_REPS <- 500

# Shift-share on group totals: shares from w, intensities from wt / w.
decompose <- function(w_old, wt_old, w_young, wt_young) {
    s_old <- w_old / sum(w_old); s_young <- w_young / sum(w_young)
    t_old <- ifelse(w_old > 0, wt_old / ifelse(w_old > 0, w_old, 1), 0)
    t_young <- ifelse(w_young > 0, wt_young / ifelse(w_young > 0, w_young, 1), 0)
    total <- sum(s_old * t_old) - sum(s_young * t_young)
    out <- lapply(c("young", "old"), function(base) {
        if (base == "young") {
            comp <- sum((s_old - s_young) * t_young)
            site <- sum(s_young * (t_old - t_young))
        } else {
            comp <- sum((s_old - s_young) * t_old)
            site <- sum(s_old * (t_old - t_young))
        }
        c(gap = total, composition = comp, site_choice = site,
          interaction = total - comp - site)
    })
    setNames(out, c("young", "old"))
}

# A visit labelled "Business, Social Networking" is split in half rather than
# counted twice, so category shares still sum to one. Unlabelled visits get
# their own bucket instead of being dropped, which would silently reweight the
# panel toward whatever the meter happened to recognise.
# The per-visit category labels, exploded once. A visit labelled
# "Business, Social Networking" is split in half rather than counted twice, so
# category shares still sum to one. Unlabelled visits get their own bucket
# instead of being dropped, which would silently reweight the panel toward
# whatever the meter happened to recognise.
#
# The source file is 2 GB, so it is read once and the exploded table reused for
# every measure.
decomp_labels <- function() {
    v <- read_web_visits(c("caseid", "private_domain", "category"))
    v <- v[!is.na(private_domain) & nzchar(private_domain)]
    v[!nzchar(category) | is.na(category), category := UNCATEGORISED]
    v[, vid := .I]
    lab <- v[, .(label = trimws(unlist(strsplit(category, ",", fixed = TRUE)))),
             by = .(vid, caseid, private_domain)]
    lab[, w := 1 / .N, by = vid]
    lab[, .(w = sum(w)), by = .(caseid, private_domain, label)]
}

# Per person and label: visit weight, and weight x tracking. Both sum over
# people, so every group statistic the decomposition needs is a column sum --
# which is what makes resampling panelists an index into precomputed rows
# rather than a rebuild of four million visits.
decomp_matrices <- function(lab, bl, measure) {
    b <- as.data.table(bl)[, .(private_domain = gsub("_", ".", filename, fixed = TRUE),
                               m = get(measure))]
    d <- merge(lab, b, by = "private_domain", all.x = TRUE)
    d[is.na(m), m := 0]
    agg <- d[, .(w = sum(w), wt = sum(w * m)), by = .(caseid, label)]

    people <- sort(unique(agg$caseid)); labels <- sort(unique(agg$label))
    i <- match(agg$caseid, people); j <- match(agg$label, labels)
    W <- matrix(0, length(people), length(labels))
    WT <- matrix(0, length(people), length(labels))
    W[cbind(i, j)] <- agg$w
    WT[cbind(i, j)] <- agg$wt
    list(W = W, WT = WT, people = people)
}

build_age_gap_decomposition <- function(bl, person, path, reps = DECOMP_REPS,
                                        seed = BOOTSTRAP_SEED) {
    grp <- as.data.table(person)[, .(caseid, ag = as.character(agegroup_lab))]
    lab <- decomp_labels()
    rows <- lapply(DECOMP_MEASURES, function(m) {
        M <- decomp_matrices(lab, bl, m)
        g <- grp$ag[match(M$people, grp$caseid)]
        io <- which(g == OLD_GROUP); iy <- which(g == YOUNG_GROUP)
        pt <- decompose(colSums(M$W[io, , drop = FALSE]), colSums(M$WT[io, , drop = FALSE]),
                        colSums(M$W[iy, , drop = FALSE]), colSums(M$WT[iy, , drop = FALSE]))

        # Panelists are the unit of independent variation, so panelists are what
        # gets resampled.
        set.seed(seed)
        n <- nrow(M$W)
        draws <- vapply(seq_len(reps), function(b) {
            p <- sample.int(n, n, replace = TRUE)
            o <- which(g[p] == OLD_GROUP); y <- which(g[p] == YOUNG_GROUP)
            if (!length(o) || !length(y)) return(c(NA, NA, NA, NA))
            decompose(colSums(M$W[p[o], , drop = FALSE]), colSums(M$WT[p[o], , drop = FALSE]),
                      colSums(M$W[p[y], , drop = FALSE]),
                      colSums(M$WT[p[y], , drop = FALSE]))$young
        }, numeric(4))
        ci <- apply(draws, 1, quantile, c(.025, .975), na.rm = TRUE)

        y <- pt$young
        cat(sprintf("  %-24s gap %.3f = composition %.3f + site choice %.3f + interaction %.3f (%.0f%% site choice)\n",
                    m, y[["gap"]], y[["composition"]], y[["site_choice"]],
                    y[["interaction"]], 100 * y[["site_choice"]] / y[["gap"]]))
        c(VAR_LABELS[[m]],
          sprintf("%.3f", y[["gap"]]),
          sprintf("%.3f [%.3f, %.3f]", y[["composition"]], ci[1, 2], ci[2, 2]),
          sprintf("%.3f [%.3f, %.3f]", y[["site_choice"]], ci[1, 3], ci[2, 3]),
          sprintf("%.3f", y[["interaction"]]))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Is the age gradient linear?
# ---------------------------------------------------------------------------
# The paper bins age, so the gradient it reports could in principle be an
# artifact of where the bins were cut. Fitting birth year flexibly answers that,
# but "the smooth is significant" answers the wrong question: a natural cubic
# basis already contains a straight line, so a joint test of its columns cannot
# separate "there is an age effect" from "the age effect bends". The earlier R
# script collected exactly that ambiguous quantity into a table called
# `nonlinear_summary`, where an effective degrees of freedom near 1 with p<.001
# means a strong *linear* birth-year effect, not a nonlinear one.
#
# So both questions get their own test. The spline basis is residualised on
# [1, birthyr] and an orthonormal spanning set taken, leaving columns exactly
# orthogonal to the linear term; a gate refuses to continue if that orthogonality
# fails, since the nonlinearity test would then absorb part of the linear
# gradient. The penalised smooth is fit alongside with mgcv, which is what the
# original 2025 script used -- its effective degrees of freedom and smooth
# p-value were previously hardcoded into the Python port because mgcv has no
# equivalent there. In R they are computed.
SPLINE_DF <- 5

nonlinear_basis <- function(d) {
    basis <- splines::ns(d$birthyr, df = SPLINE_DF)
    linear <- cbind(1, d$birthyr)
    resid <- basis - linear %*% MASS::ginv(linear) %*% basis
    left <- svd(resid)$u[, seq_len(SPLINE_DF - 2), drop = FALSE]
    worst <- max(abs(crossprod(linear, left))) / nrow(d)
    if (worst > 1e-9)
        stop(sprintf("nonlinear basis is not orthogonal to the linear term (max %.2e); ",
                     worst), "the nonlinearity test would absorb part of the gradient")
    colnames(left) <- paste0("nl", seq_len(ncol(left)))
    left
}

build_age_spline_tests <- function(data, path) {
    d <- as.data.frame(data)
    d$agegroup_lab <- factor(as.character(d$agegroup_lab), levels = AGE_ORDER)
    nl <- nonlinear_basis(d)
    d <- cbind(d, nl)
    nlc <- colnames(nl)
    outcomes <- c(paste0("bl_", MEASURES, "_rate"), "top_org_share")
    labels <- c(VAR_LABELS[MEASURES], "Top organization share")

    fmt_p <- function(p) if (p < 0.001) "< .001" else sub("^0", "", sprintf("%.3f", p))
    rows <- lapply(seq_along(outcomes), function(i) {
        y <- outcomes[i]
        f <- as.formula(paste(y, "~ birthyr +", paste(nlc, collapse = " + "),
                              "+", FORMULA_RHS_NOAGE))
        m <- lm(f, data = d)
        V <- sandwich::vcovHC(m, type = "HC1")
        joint <- car::linearHypothesis(m, c("birthyr", nlc), vcov. = V)
        nonlin <- car::linearHypothesis(m, nlc, vcov. = V)
        g <- mgcv::gam(as.formula(paste(y, "~ s(birthyr) +", FORMULA_RHS_NOAGE)), data = d)
        s <- summary(g)$s.table
        c(labels[i], fmt_p(joint$`Pr(>F)`[2]), fmt_p(nonlin$`Pr(>F)`[2]),
          sprintf("%.2f", s[1, "edf"]), fmt_p(s[1, "p-value"]))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Is the age gap an artifact of which device people were metered on?
# ---------------------------------------------------------------------------
# Older and younger panelists do not use the same devices, and mobile and
# desktop browsing are tracked differently, so the age gap could in principle be
# a device effect wearing a demographic costume.
#
# The clean test is within-person: the same individual on both devices, every
# personal characteristic differenced out. This panel cannot support it. Read
# straight from the complete visit source, 1,108 of the 1,134 panelists browse on
# exactly one device type, 21 on two and 3 on three. Device is a person-level
# attribute here, not something that varies within a person, and two dozen people
# are no basis for a within-person estimate.
#
# What the data supports is three between-person checks, which together bound the
# concern rather than identify a device effect free of selection: the gradient
# estimated separately within each device group, device added to the Table 5
# specification, and the pooled estimate for reference.
DEVICE_MEASURES <- c("ddg_join_ads", "third_party_cookies", "canvas_fingerprinting",
                     "session_recording", "key_logging")

person_device <- function() {
    v <- read_web_visits(c("caseid", "device_type", "page_duration"))
    v <- v[nzchar(device_type)]
    v[, dev := fifelse(device_type == "Laptop/Desktop", "Desktop", "Mobile")]
    # A handful of panelists straddle; assign each to where they spent most of
    # their metered time rather than dropping them.
    d <- v[, .(t = sum(page_duration, na.rm = TRUE)), by = .(caseid, dev)]
    setorder(d, caseid, -t)
    d[!duplicated(caseid), .(caseid, device = dev)]
}

build_device_age_gradient <- function(data, path) {
    d <- merge(as.data.table(data), person_device(), by = "caseid", all.x = TRUE)
    d <- as.data.frame(d[!is.na(device)])
    d$agegroup_lab <- factor(as.character(d$agegroup_lab), levels = AGE_ORDER)
    cat(sprintf("  metered device: %s\n",
                paste(sprintf("%s %d", names(table(d$device)), table(d$device)),
                      collapse = ", ")))

    cell <- function(fit) {
        a <- fit[fit$term == AGE_TERM_LABEL, ]
        sprintf("%.3f%s", a$b, stars(a$p))
    }
    rows <- lapply(DEVICE_MEASURES, function(m) {
        y <- paste0("bl_", m, "_rate")
        c(VAR_LABELS[[m]],
          cell(fit_demo(y, d)),
          cell(fit_demo(y, d, rhs = paste(FORMULA_RHS, "+ factor(device)"))),
          cell(fit_demo(y, d[d$device == "Desktop", ])),
          cell(fit_demo(y, d[d$device == "Mobile", ])))
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}
