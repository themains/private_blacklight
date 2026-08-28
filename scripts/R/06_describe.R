# 06_describe.R
# Descriptive exhibits: the sample against the CPS, exposure levels, the
# domains contributing most tracking, and the organization figures.

# ---------------------------------------------------------------------------
# Tables 2 and 3: exposure per panelist
# ---------------------------------------------------------------------------
# Cumulative counts get thousands separators and no decimals; per-visit rates
# get two. The last two columns of the cumulative table are the share of
# panelists meeting the technique at least once and at least ten times.
AL_SHOWN <- c(1, 10)

build_exposure_summary <- function(data, kind = c("cumulative", "rate"), path) {
    kind <- match.arg(kind)
    suffix <- if (kind == "rate") "_rate" else ""
    digits <- if (kind == "rate") 2 else 0
    fmt <- function(x) formatC(x, format = "f", digits = digits, big.mark = ",")

    rows <- lapply(MEASURES_DESC, function(m) {
        v <- data[[paste0("bl_", m, suffix)]]
        q <- stats::quantile(v, c(0.25, 0.5, 0.75), na.rm = TRUE)
        cells <- c(VAR_LABELS[m], fmt(mean(v, na.rm = TRUE)), fmt(sd(v, na.rm = TRUE)),
                   fmt(min(v, na.rm = TRUE)), fmt(q[1]), fmt(q[2]), fmt(q[3]),
                   fmt(max(v, na.rm = TRUE)))
        if (kind == "cumulative")
            cells <- c(cells, vapply(AL_SHOWN, function(k)
                fmt_pct(100 * mean(data[[paste0("bl_", m, "_al", k)]], na.rm = TRUE)),
                character(1)))
        cells
    })
    out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Table 1: the sample against the CPS
# ---------------------------------------------------------------------------
# CPS margins are a committed 350-byte artifact (data/cps/cps_asec_2022_margins.csv)
# derived once from the ASEC public-use file, which is gitignored at 157MB. The
# derivation lives in scripts/python/08_cps_benchmark.py --refresh; a normal run
# reads the artifact and never touches census.gov.
FP_CPS_MARGINS <- file.path(DATA_DIR, "cps", "cps_asec_2022_margins.csv")
DEMO_VARS <- c("gender_lab", "race_lab", "educ_lab", "agegroup_lab")

demo_counts <- function(data) {
    out <- rbindlist(lapply(DEMO_VARS, function(v)
        data.table(cat = names(table(data[[v]])), n = as.integer(table(data[[v]])))))
    out[, cat := factor(cat, levels = DEMO_CAT_ORDER)]
    setorder(out, cat)
    out[, perc := 100 * n / nrow(data)][]
}

build_demo_summary <- function(data, path) {
    panel <- demo_counts(data)
    cps <- fread(FP_CPS_MARGINS)
    d <- merge(panel, cps[, .(cat, cps_perc)], by = "cat", all.x = TRUE, sort = FALSE)
    stopifnot(!any(is.na(d$cps_perc)))
    d[, diff := round(perc, 1) - round(cps_perc, 1)]

    out <- data.frame(
        cat  = DEMO_CAT_LABELS[as.character(d$cat)] |> coalesce_labels(as.character(d$cat)),
        n    = formatC(d$n, format = "d", big.mark = ","),
        perc = fmt_pct(d$perc), cps = fmt_pct(d$cps_perc),
        diff = sprintf("$%+.1f$", d$diff), stringsAsFactors = FALSE)

    # \addlinespace between gender / race / education / age, so the fragment
    # drops in with the spacing the table had when its rows were typed by hand.
    breaks <- cumsum(vapply(DEMO_VARS, function(v) length(unique(data[[v]])), integer(1)))
    write_tex(out, path, group_breaks = head(breaks, -1))
    invisible(d)
}

coalesce_labels <- function(x, fallback) ifelse(is.na(x), fallback, x)

# Chi-square goodness of fit against the CPS, and the deviation summary. This
# is the note under Table 1; the manuscript \input's it rather than carrying the
# numbers in prose.
build_demo_summary_note <- function(d, path) {
    var_of <- rep(c("gender", "race", "education", "age"),
                  times = c(2, 5, 4, length(AGE_ORDER)))
    tests <- vapply(split(seq_len(nrow(d)), var_of)[c("gender", "race", "education", "age")],
        function(ix) {
            obs <- d$n[ix]
            exp <- d$cps_perc[ix] / 100 * sum(obs)
            exp <- exp * sum(obs) / sum(exp)
            t <- stats::chisq.test(obs, p = exp / sum(exp))
            sprintf("$\\chi^2(%d)=%.1f$, $%s$", length(ix) - 1L, t$statistic,
                    if (t$p.value < 0.001) "p<.001" else sub("=0\\.", "=.", sprintf("p=%.2f", t$p.value)))
        }, character(1))

    dev <- abs(d$diff)
    worst <- DEMO_CAT_LABELS[as.character(d$cat[which.max(dev)])]
    if (is.na(worst)) worst <- as.character(d$cat[which.max(dev)])
    note <- sprintf(
        "$\\chi^2$ goodness-of-fit tests of the sample against the CPS shares: %s. Mean absolute deviation across the %d categories is %.1f percentage points; the maximum is %.1f (%s).",
        paste(sprintf("%s %s", c("gender", "race", "education", "age"), tests), collapse = "; "),
        nrow(d), mean(dev), max(dev), worst)
    cat(note, "\n", sep = "", file = if (grepl("\\.tex$", path)) path else paste0(path, ".tex"))
    invisible(note)
}

# ---------------------------------------------------------------------------
# Table 4: the domains contributing the most tracking
# ---------------------------------------------------------------------------
# Exposure is visit-weighted, so a domain's contribution is its per-visit
# measure times the visits the panel made to it. Ranked separately per measure;
# the annotation is the domain's total panel traffic.
TOP_N_DOMAINS <- 50

traffic_str <- function(x) {
    ifelse(x < 1000, formatC(x, format = "d"),
    ifelse(x < 10000, sprintf("%.1fk", x / 1000), sprintf("%.0fk", x / 1000)))
}

build_top_contributors <- function(bl, path, n_show = TOP_N_DOMAINS) {
    visits <- visit_panel()[!is.na(private_domain),
                                      .(visits = sum(visits)), by = private_domain]
    bl <- as.data.table(bl)[, private_domain := gsub("_", ".", filename, fixed = TRUE)]
    d <- merge(visits, bl, by = "private_domain", all.x = TRUE)
    # Ties are real: iheart.com and nextdoor.com both take 5,128 visits and both
    # carry the Facebook Pixel, so their weighted exposure is identical. The
    # Python version resolved such ties by row order in the raw visit files, one
    # of which is restricted -- unreproducible and arbitrary. Break ties on
    # traffic, then alphabetically, so the ranking is defined.
    setorder(d, -visits, private_domain)
    d[, label := paste0(private_domain, " (", traffic_str(visits), ")")]

    cols <- lapply(MEASURES_DESC, function(m) {
        e <- d[[m]] * d$visits
        keep <- which(!is.na(e) & e > 0)
        top <- keep[order(-e[keep])][seq_len(min(n_show, length(keep)))]
        d$label[top]
    })
    out <- data.frame(ix = seq_len(n_show),
                      do.call(cbind, lapply(cols, `length<-`, n_show)),
                      stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(out)
}

# ---------------------------------------------------------------------------
# Organization tracking: four distributions (Figure 5)
# ---------------------------------------------------------------------------
# Each panel is a density over panelists with its summary statistics inset, so
# the shape and the numbers travel together. Inset rather than a caption because
# a reader comparing four panels should not have to leave the figure.
SUMM_STATS <- c(n = "n", Mean = "mean", SD = "sd", `Min.` = "min",
                `25p` = "q25", `50p` = "q50", `75p` = "q75", `Max.` = "max")

summary_inset <- function(x) {
    q <- stats::quantile(x, c(.25, .5, .75))
    v <- c(n = length(x), mean = mean(x), sd = sd(x), min = min(x),
           q25 = q[[1]], q50 = q[[2]], q75 = q[[3]], max = max(x))
    data.frame(
        stat = names(SUMM_STATS),
        value = ifelse(names(SUMM_STATS) == "n",
                       formatC(v[SUMM_STATS], format = "d", big.mark = ","),
                       formatC(round(v[SUMM_STATS], 1), format = "f", digits = 1,
                               big.mark = ",")),
        stringsAsFactors = FALSE)
}

build_distribution <- function(x, xlab, path, bins = 50) {
    tbl <- summary_inset(x)
    lab <- paste(sprintf("%-7s %s", tbl$stat, tbl$value), collapse = "\n")
    p <- ggplot(data.frame(x = x), aes(x)) +
        geom_histogram(aes(y = after_stat(density)), bins = bins,
                       fill = "#8a8a8a", colour = NA) +
        annotate("text", x = Inf, y = Inf, label = lab, hjust = 1.05, vjust = 1.2,
                 size = 1.9, family = "mono", lineheight = 1.1) +
        labs(x = xlab, y = "Density") +
        theme_blacklight(grid = "none") +
        theme(axis.text.y = element_blank())
    save_fig(p, path, width = FIG_HALF_W, height = FIG_HALF_W)
}

# Reach against dominance. Most organizations touch many panelists; almost none
# are the largest observer for anyone. Log-x because reach spans three orders of
# magnitude; the named points are the organizations that dominate at all.
build_reach_dominance <- function(reach, path, label_min = 10) {
    d <- as.data.frame(reach)
    d$lab <- ifelse(d$dominance >= label_min, sub(",? (Inc|LLC|Corporation)\\.?$", "", d$org), NA)
    p <- ggplot(d, aes(reach, dominance)) +
        geom_point(colour = "#8a8a8a", size = 0.8, alpha = 0.7) +
        ggrepel::geom_text_repel(aes(label = lab), size = 2.2, na.rm = TRUE,
                                 min.segment.length = 0, segment.size = 0.2,
                                 max.overlaps = Inf) +
        scale_x_log10() +
        labs(x = "Reach (panelists tracked at least once)",
             y = "Dominance (panelists whose top observer it is)") +
        theme_blacklight(grid = "both")
    save_fig(p, path, width = FIG_HALF_W, height = FIG_HALF_W)
}

# ---------------------------------------------------------------------------
# Two online risks, opposite age gradients
# ---------------------------------------------------------------------------
# The same panel carries a security measure -- domains antivirus vendors flagged
# as malicious or suspicious -- over the same month. Tracking rises with age;
# flagged-domain exposure falls. That divergence is the Discussion's point, so
# the script refuses to write the table if it stops holding.
FP_IND <- file.path(DATA_DIR, "yg", "ind_data.csv")

build_risk_divergence <- function(data, path) {
    sec <- fread(FP_IND, select = c("caseid", "malicious", "suspicious"))
    d <- merge(as.data.table(data), sec, by = "caseid")
    d[, bad_rate := (malicious + suspicious) / tt_domains]
    # Read from CSV the column is plain character, and "<25" sorts after the
    # numeric labels. Restore the substantive order.
    d[, agegroup_lab := factor(as.character(agegroup_lab), levels = AGE_ORDER)]

    by_age <- d[, .(n = .N,
                    ad_trackers = mean(bl_ddg_join_ads_rate),
                    bad_domain_rate = mean(bad_rate)),
                by = agegroup_lab][order(agegroup_lab)]

    rho <- stats::cor(by_age$ad_trackers, by_age$bad_domain_rate, method = "spearman")
    if (rho > -0.5)
        stop(sprintf("the two risks no longer diverge across age groups (rho = %+.2f); ",
                     rho), "the Discussion passage must be revised", call. = FALSE)
    message(sprintf("risk divergence: Spearman across %d age-group means = %+.2f",
                    nrow(by_age), rho))

    out <- data.frame(
        age = ifelse(as.character(by_age$agegroup_lab) == "<25", "$<$25",
                     gsub("-", "--", as.character(by_age$agegroup_lab), fixed = TRUE)),
        n = formatC(by_age$n, format = "d", big.mark = ","),
        ads = sprintf("%.2f", by_age$ad_trackers),
        bad = sprintf("%.1f", 100 * by_age$bad_domain_rate), stringsAsFactors = FALSE)
    write_tex(out, path)
    invisible(by_age)
}

# ---------------------------------------------------------------------------
# How fast exposure accumulates
# ---------------------------------------------------------------------------
# Timestamps live only in the raw RealityMine files, not in the aggregated
# panel. realityMine_web is the complete record: it is a strict superset of the
# desktop and mobile files (every one of their 167,894 person-domain pairs
# appears in it, with identical durations), so it alone is read here. Adding the
# device files back changes nothing -- checked, they give the same curve to
# three decimals -- because a first encounter is a minimum, and a minimum is
# unchanged by counting the same visit twice.
#
# The file is 2.0 GB and restricted on Dataverse (doi:10.7910/DVN/VIV4TS), so it
# is not committed.
CUM_HOUR_MARKS <- c(0, 12, 24, 36, 48)
CUM_START <- "2022-05-31 18:00:00"
# What the figure reports, so a change in the curve is caught rather than
# quietly published. Last moved when 434 retried scans joined the corpus, which
# let first encounters register on domains previously counted as tracker-free:
# 0.501 -> 0.504 at twelve hours, 0.791 -> 0.793 at forty-eight.
CUM_EXPECTED <- c(0.067, 0.504, 0.717, 0.747, 0.793)

build_cum_exposure <- function(bl, table_path, figure_path) {
    b <- as.data.table(bl)[, private_domain := gsub("_", ".", filename, fixed = TRUE)]
    v <- read_web_visits(c("caseid", "private_domain", "session_start_time"))
    v <- v[!is.na(private_domain) & nzchar(private_domain)]
    v[, t := as.POSIXct(session_start_time, tz = "UTC")]

    # One row per person-domain, the first time they met it.
    setorder(v, caseid, private_domain, t)
    first <- v[!duplicated(v[, .(caseid, private_domain)])]
    m <- merge(first, b, by = "private_domain")
    m <- m[rowSums(!is.na(m[, ..MEASURES_DESC])) > 0]
    m[, vh := as.POSIXct(trunc(t, "hours"))]
    n <- uniqueN(m$caseid)
    start <- as.POSIXct(CUM_START, tz = "UTC")

    share_by <- function(k, hours) {
        fe <- m[get(k) > 0, .(fh = min(vh)), by = caseid]
        vapply(hours, function(h) sum(fe$fh <= start + h * 3600) / n, numeric(1))
    }
    res <- vapply(MEASURES_DESC, share_by, numeric(length(CUM_HOUR_MARKS)),
                  hours = CUM_HOUR_MARKS)

    got <- round(res[, "ddg_join_ads"], 3)
    if (!isTRUE(all.equal(unname(got), CUM_EXPECTED)))
        stop("cumulative exposure curve moved: ad trackers ",
             paste(got, collapse = ", "), " against ",
             paste(CUM_EXPECTED, collapse = ", "))
    cat(sprintf("  gate: cumulative exposure curve reproduces (n = %d panelists)\n", n))

    out <- data.frame(measure = VAR_LABELS[MEASURES_DESC],
                      matrix(fmt3(t(res)), nrow = length(MEASURES_DESC)),
                      stringsAsFactors = FALSE)
    if (!grepl("\\.tex$", table_path)) table_path <- paste0(table_path, ".tex")
    cat(paste(c("\\midrule", paste0(do.call(paste, c(out, sep = " & ")), " \\\\")),
              collapse = "\n"), file = table_path)

    # The full curve, not just the five marks: how quickly each technique
    # reaches the panel over the first two days.
    hours <- seq(0, 48, by = 1)
    curve <- rbindlist(lapply(MEASURES_DESC, function(k) data.table(
        measure = VAR_LABELS[[k]], hour = hours, share = share_by(k, hours))))
    curve[, measure := factor(measure, levels = VAR_LABELS[MEASURES_DESC])]
    g <- ggplot(curve, aes(hour, 100 * share, group = measure, linetype = measure,
                           colour = measure)) +
        geom_line(linewidth = .5) +
        scale_x_continuous(breaks = CUM_HOUR_MARKS) +
        scale_y_continuous(limits = c(0, 100)) +
        scale_colour_grey(start = 0, end = .72, name = NULL) +
        scale_linetype_manual(values = c(1, 2, 3, 4, 5, 6, 1), name = NULL) +
        labs(x = "Hours since measurement began",
             y = "Panelists who have met the technique (%)") +
        theme_blacklight(grid = "both") +
        theme(legend.position = "right", legend.key.width = unit(1.4, "lines"))
    save_fig(g, figure_path, width = FIG_FULL_W, height = 3.2)
    invisible(res)
}
