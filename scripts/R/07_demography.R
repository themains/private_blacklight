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

fit_demo <- function(yvar, data) {
    data <- data[!is.na(data[[yvar]]), ]
    # agegroup_lab is ordered; relevel() on an ordered factor would emit
    # polynomial contrasts, so drop the ordering first.
    data$agegroup_lab <- factor(as.character(data$agegroup_lab), levels = AGE_ORDER)
    f <- as.formula(paste(yvar, "~", FORMULA_RHS))
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

