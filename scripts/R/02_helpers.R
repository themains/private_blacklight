# 02_helpers.R
# Table writers, formatters and the shared figure theme.

# ---------------------------------------------------------------------------
# LaTeX fragments
# ---------------------------------------------------------------------------
# The manuscript \input's table *bodies* only: one "a & b & c \\" line per row,
# no header, no rules, no trailing newline. This reproduces exactly what the
# Python pandas_to_tex() emitted, so fragments stay byte-comparable across the
# port.
write_tex <- function(df, path, group_breaks = NULL) {
    if (!grepl("\\.tex$", path)) path <- paste0(path, ".tex")
    cells <- lapply(df, function(col) if (is.character(col)) col else as.character(col))
    rows <- paste0(do.call(paste, c(cells, sep = " & ")), " \\\\")
    # group_breaks: row indices to follow with an \addlinespace, so a table with
    # labelled blocks keeps its spacing without the caller assembling the text.
    for (i in sort(unique(group_breaks), decreasing = TRUE))
        if (i >= 1 && i < length(rows)) rows <- append(rows, "\\addlinespace", after = i)
    cat(paste(rows, collapse = "\n"), file = path)
    invisible(path)
}

# ---------------------------------------------------------------------------
# Number registry
#
# Every quantity the manuscript quotes that no table carries is registered here
# and written to tables/numbers.tex as a LaTeX macro, so the prose cites the
# code that computed it rather than a digit someone typed once. Four data
# corrections in a row moved tables and left sentences behind; this is the fix
# for that, and 12_check_prose.R fails the build if a bare numeral appears in
# prose where a macro belongs.
#
# Macro names are letters only. TeX rejects digits and underscores in control
# sequence names, so SixtyFive rather than 65 or sixty_five.
# ---------------------------------------------------------------------------
.numbers <- new.env(parent = emptyenv())

num <- function(name, value, fmt = "%.1f") {
    if (!grepl("^[A-Za-z]+$", name))
        stop("macro name must be letters only, got '", name, "'", call. = FALSE)
    v <- if (is.character(value)) value else sprintf(fmt, value)
    # Registering the same name twice with different values means two things in
    # the pipeline claim to be the same quantity and are not.
    prev <- .numbers[[name]]
    if (!is.null(prev) && !identical(prev, v))
        stop("number '", name, "' registered as '", prev, "' and then '", v,
             "'", call. = FALSE)
    .numbers[[name]] <- v
    invisible(value)
}

# A coefficient, its standard error and its p-value taken from the same fit
# that produced a table cell, so the macro and the cell cannot drift apart.
# `scale` carries the table's own units: Table 5 reports in hundreds.
num_coef <- function(stem, models, measure, term, scale = 1) {
    m <- models[[measure]]
    if (is.null(m)) stop("no measure '", measure, "'", call. = FALSE)
    i <- match(term, COEF_ORDER)
    if (is.na(i)) stop("no term '", term, "' in COEF_ORDER", call. = FALSE)
    num(paste0(stem, "B"), tex_num(m$b[i] * scale))
    num(paste0(stem, "SE"), tex_num(m$se[i] * scale))
    num(paste0(stem, "P"), fmt_p(m$p[i]))
    invisible(m$b[i] * scale)
}

# The manuscript writes p-values as ".45" and very small ones as "< .001".
fmt_p <- function(p) {
    if (is.na(p)) return("--")
    if (p < 0.001) return("\\ensuremath{<} .001")
    sub("^0", "", sprintf("%.2f", p))
}

# The manuscript writes large numbers as $34{,}512$: in math mode a bare comma
# is punctuation and takes a trailing space, while {,} is an ordinary atom and
# does not. Macros must emit the same form or substituting one changes the
# typography.
tex_num <- function(x, digits = 0) {
    formatC(x, format = "f", digits = digits, big.mark = "{,}")
}

write_numbers <- function(path) {
    if (!grepl("\\.tex$", path)) path <- paste0(path, ".tex")
    nm <- sort(ls(.numbers))
    writeLines(vapply(nm, function(k)
        sprintf("\\newcommand{\\%s}{%s}", k, .numbers[[k]]), character(1)), path)
    cat(sprintf("  wrote %d numbers to %s\n", length(nm), basename(path)))
    invisible(nm)
}

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
stars <- function(p) {
    ifelse(is.na(p), "",
        ifelse(p < 0.01, "***", ifelse(p < 0.05, "**", ifelse(p < 0.1, "*", ""))))
}

# Thousands separators, fixed decimals; matches Python's f"{x:,.Nf}".
fmt_num <- function(x, digits = 2, big_mark = ",") {
    formatC(x, format = "f", digits = digits, big.mark = big_mark)
}

fmt_pct <- function(x, digits = 1) paste0(formatC(x, format = "f", digits = digits), "\\%")

# ---------------------------------------------------------------------------
# One visual grammar for every exhibit
# ---------------------------------------------------------------------------
# Figures are authored at the width they print at, so the scale factor is 1 and
# the base size below *is* the size on the page. The manuscript's text block is
# 468pt (6.5in); a figure placed at width=\textwidth should be saved at 6.5in.
# Saving larger and letting \includegraphics shrink it is what put type on the
# page at 3pt.
FIG_BASE_SIZE <- 9
FIG_FULL_W    <- 6.5     # = \textwidth
FIG_HALF_W    <- 3.15    # two per row
C_REFERENCE   <- "#800000"   # zero / parity lines only
C_SIGNIFICANT <- "#000000"
C_NULL        <- "#a8a8a8"
C_INTERVAL    <- "#c7c7c7"

theme_blacklight <- function(base_size = FIG_BASE_SIZE, grid = c("x", "y", "both", "none")) {
    grid <- match.arg(grid)
    th <- ggplot2::theme_minimal(base_size = base_size) +
        ggplot2::theme(
            panel.border      = ggplot2::element_blank(),
            panel.grid.minor  = ggplot2::element_blank(),
            panel.grid.major  = ggplot2::element_line(colour = "#e6e6e6", linewidth = 0.25),
            strip.text        = ggplot2::element_text(face = "bold", size = base_size),
            axis.title        = ggplot2::element_text(size = base_size),
            legend.position   = "bottom",
            # A legend sits under the panels and competes with nothing, so it
            # can run a point smaller than the axes without hurting legibility.
            legend.text       = ggplot2::element_text(size = base_size - 1),
            legend.title       = ggplot2::element_blank(),
            legend.key.width  = ggplot2::unit(1.4, "lines"),
            plot.title        = ggplot2::element_blank()
        )
    if (grid == "x") th <- th + ggplot2::theme(panel.grid.major.y = ggplot2::element_blank())
    if (grid == "y") th <- th + ggplot2::theme(panel.grid.major.x = ggplot2::element_blank())
    if (grid == "none") th <- th + ggplot2::theme(panel.grid.major = ggplot2::element_blank())
    th
}

# Reference line at a real benchmark (zero, parity). Never decorative.
geom_reference <- function(x = 0) {
    ggplot2::geom_vline(xintercept = x, linetype = "dashed",
                        colour = C_REFERENCE, linewidth = 0.3, alpha = 0.6)
}

# cairo_pdf, not the default device: the default pdf() has no UTF-8 glyph for
# an en dash and silently substitutes a hyphen.
save_fig <- function(plot, path, width = FIG_FULL_W, height = 4.0) {
    ggplot2::ggsave(paste0(path, ".pdf"), plot, width = width, height = height,
                    device = grDevices::cairo_pdf)
    ggplot2::ggsave(paste0(path, ".png"), plot, width = width, height = height, dpi = 300)
    invisible(path)
}

# ---------------------------------------------------------------------------
# Pinned reference data
# ---------------------------------------------------------------------------
# Blocklists, the Tracker Radar map and the public suffix list all decide
# numbers, and all have upstreams that change. Each directory carries a
# manifest.json recording provenance and a sha256. Verify before anything runs:
# a swapped list should fail in a second, not surface as a quietly different
# number three tables later.
check_pins <- function(dirs = c("blocklists", "tracker_lists")) {
    bad <- character()
    for (d in dirs) {
        mf <- file.path(DATA_DIR, d, "manifest.json")
        if (!file.exists(mf)) { bad <- c(bad, sprintf("missing manifest: %s", mf)); next }
        m <- jsonlite::fromJSON(mf, simplifyVector = FALSE)
        for (nm in names(m$lists)) {
            e <- m$lists[[nm]]
            p <- file.path(DATA_DIR, d, e$file)
            if (!file.exists(p)) { bad <- c(bad, sprintf("missing: %s", p)); next }
            got <- digest::digest(file = p, algo = "sha256")
            if (!identical(got, e$sha256))
                bad <- c(bad, sprintf("%s\n    expected %s\n    found    %s",
                                      p, e$sha256, got))
        }
    }
    if (length(bad))
        stop("pinned reference data changed:\n  ", paste(bad, collapse = "\n  "),
             "\n\nNumbers built on these will move. Restore the pinned file, or ",
             "update the manifest deliberately.", call. = FALSE)
    invisible(TRUE)
}

# Two decimals, trailing zeros dropped, matching how the Python tables printed
# str(round(x, 2)) -- 6.52 stays 6.52, 8.10 prints as 8.1.
fmt2 <- function(x) sub("\\.$", "", sub("0+$", "", sprintf("%.2f", x)))

# ---------------------------------------------------------------------------
# Complete manuscript floats
# ---------------------------------------------------------------------------
# The manuscript used to \input a body-only fragment into a hand-maintained
# table environment, which is how a transposed pair of columns once survived:
# the header lived in one file and the numbers in another, and nothing checked
# that they still described each other. Here the same builder that formats the
# cells also names the columns, so they cannot drift apart.
#
# `df` arrives already formatted as character columns, so kableExtra prints the
# strings it is given rather than rounding them again -- the numeric rows stay
# byte-identical to the verified fragments.
FLOAT_FONT_SIZE <- 9

write_float <- function(df, path, caption, label, header, align, notes = NULL) {
    if (!grepl("\\.tex$", path)) path <- paste0(path, ".tex")
    names(df) <- header
    # kbl prepends "tab:" itself, so hand it the bare stem.
    label <- sub("^tab:", "", label)
    tbl <- kableExtra::kbl(df, format = "latex", booktabs = TRUE, escape = FALSE,
                           align = align, caption = caption, label = label,
                           linesep = "", row.names = FALSE)
    # A fixed body size, so adjacent tables are set in the same type. Leaving
    # this to scale_down alone sizes each table by how wide it happens to be:
    # a ten-column table gets shrunk and an eight-column one does not, and two
    # tables on the same page come out visibly different. scale_down stays as a
    # backstop for anything that still overruns the text block.
    tbl <- kableExtra::kable_styling(tbl, latex_options = "scale_down",
                                     position = "center",
                                     font_size = FLOAT_FONT_SIZE)
    if (!is.null(notes))
        tbl <- kableExtra::footnote(tbl, general = notes, general_title = "",
                                    threeparttable = TRUE, escape = FALSE,
                                    footnote_as_chunk = TRUE)
    cat(as.character(tbl), file = path)
    invisible(path)
}

# Emit one of the five numbered manuscript tables from its already-formatted
# body, using the spec in FLOATS so caption, header and cells stay together.
emit_float <- function(df, key) {
    f <- FLOATS[[key]]
    write_float(df, file.path(TABLES_DIR, paste0(key, "_formatted")),
                f$caption, f$label, f$header, f$align)
}

# Three decimals with trailing zeros dropped, matching how the published table
# printed round(x, 3): 0.230 prints as 0.23.
fmt3 <- function(x) sub("\\.$", "", sub("0+$", "", sprintf("%.3f", x)))
