# ---------------------------------------------------------------------------
# Does every number in the manuscript come from somewhere?
#
# Four data corrections in a row moved tables and left sentences behind. The
# reason each one went unnoticed is that a number in prose and the same number
# in a table have no mechanical relationship, so nothing can notice when they
# diverge. This makes the relationship mandatory.
#
# A numeral in the prose passes if it is one of:
#
#   in a table   it appears in some tables/*.tex, so regenerating the table
#                and forgetting the sentence produces a mismatch here
#   a macro      it is not in the prose at all, because the prose says
#                \CovMean and tables/numbers.tex supplies the value
#   allowlisted  it is a structural constant, not an estimate: another paper's
#                figure, a software version, a p-value threshold, a design
#                parameter we chose. Each entry carries its reason.
#
# Anything else is a number typed by hand that nothing will catch drifting,
# which is the bug this file exists to prevent.
#
# What this does NOT catch: a prose number that coincidentally equals some
# unrelated value in some table. With roughly 1,500 artifact values and
# rounding tolerance, small integers nearly always find a match, so a stale
# "77 panelists" sailed through while the same error in "86,659" was caught.
# The check is strong for distinctive numbers and weak for small ones. Reading
# the sentence against its source is still the only complete answer.
# ---------------------------------------------------------------------------

# Structural constants. The reason matters more than the number: if you cannot
# write one, the value is probably an estimate and belongs in the registry.
ALLOWED <- c(
    # Significance thresholds and the Bonferroni-adjusted level.
    "0.001" = "p-value threshold",
    "0.01"  = "p-value threshold",
    "0.05"  = "p-value threshold",
    "0.1"   = "p-value threshold",
    "0.00417" = "Bonferroni level, 0.05/12",
    # Other people's studies, cited from their papers.
    "250000" = "Dambra2022 sample size",
    "200000" = "trackingthetrackers sample size",
    "21"     = "trackingthetrackers page loads, millions",
    "42"     = "trackingthetrackers German reach",
    "38000"  = "Tracker Radar third-party domains",
    "19000"  = "Tracker Radar parent organizations",
    "8400"   = "berke2025whose sample size",
    "1300"   = "pugliese2020long sample size",
    # Panel administration, from YouGov's documentation rather than our data.
    "1200"   = "panelists recruited",
    "2000"   = "YouGov joining points",
    "1000"   = "YouGov completion points, and the bootstrap draw count",
    "3"      = "installation guide page reference",
    "4"      = "installation guide page reference",
    # Instrument versions and the vendor's cache window.
    "3.10.0" = "Blacklight version, 2026 audit",
    "3.4.0"  = "Blacklight version, 2025 audit",
    "138"    = "Chromium version, 2026 audit",
    "126"    = "Chromium version, 2025 audit",
    "24"     = "Blacklight cache window, hours",
    "48"     = "Blacklight cache window and the hour mark reported",
    "12"     = "hour mark reported, and the count of demographic predictors",
    # Design parameters we chose, not quantities we estimated.
    "10000"  = "placebo random tracker sets",
    "0.5"    = "median regression tau",
    "200"    = "unscanned domains sampled for the audit",
    "500"    = "widest-reach domains rescanned",
    "100"    = "domains per audit stratum",
    "7"      = "tracking measures",
    "2"      = "strata, and the minimum visit count",
    "1"      = "counting threshold",
    "10"     = "counting threshold",
    "13"     = "third parties carrying session recording"
)

# LaTeX float tuning, page geometry and other typesetting values live in the
# preamble and say nothing about the data.
PREAMBLE_CMDS <- paste(
    "renewcommand", "setlength", "includepdf", "fontsize", "usepackage",
    "interfootnotelinepenalty", "geometry", "definecolor", "newcommand",
    "setcounter", "hypersetup", "captionsetup", "subcaptionsetup",
    sep = "|")

strip_noise <- function(tex) {
    lines <- strsplit(tex, "\n", fixed = TRUE)[[1]]
    lines <- lines[!grepl("^\\s*%", lines)]
    x <- paste(lines, collapse = "\n")
    # Generated floats carry their own numbers and are checked by being
    # generated. perl = TRUE for the lazy quantifier: without it the greedy
    # match runs from the first \begin{table} to the last \end{table} and
    # deletes most of the manuscript, which looks like a clean pass.
    x <- gsub("\\\\begin\\{(table|figure)\\*?\\}.*?\\\\end\\{\\1\\*?\\}", " ", x,
              perl = TRUE)
    x <- gsub(sprintf("\\\\(%s)[^\n]*", PREAMBLE_CMDS), " ", x)
    # Figure and column widths: 0.495\textwidth is typesetting, not a result.
    x <- gsub("[0-9.]+\\\\(text|line|column)(width|height)", " ", x)
    x <- gsub("(width|scale|height)\\s*=\\s*[0-9.]+", " ", x)
    x <- gsub("\\\\(url|href)\\{[^}]*\\}(\\{[^}]*\\})?", " ", x)
    x <- gsub("\\\\cite[tp]?\\*?\\{[^}]*\\}", " ", x)
    x <- gsub("\\\\(label|ref|cref|Cref|input|includegraphics)\\{[^}]*\\}", " ", x)
    # The thin-space comma. Without this, 19{,}701 reads as 19 and 701, which
    # manufactures orphans and hides the number actually written.
    gsub("{,}", "", x, fixed = TRUE)
}

prose_numbers <- function(path) {
    x <- strip_noise(paste(readLines(path, warn = FALSE), collapse = "\n"))
    m <- gregexpr("[0-9][0-9,]*(\\.[0-9]+)?|\\.[0-9]+", x)[[1]]
    if (m[1] == -1L) return(character(0))
    v <- regmatches(x, gregexpr("[0-9][0-9,]*(\\.[0-9]+)?|\\.[0-9]+", x))[[1]]
    unique(gsub(",", "", v))
}

artifact_numbers <- function(dir) {
    fs <- list.files(dir, pattern = "\\.tex$", full.names = TRUE)
    v <- unlist(lapply(fs, function(f) {
        x <- gsub("{,}", "", paste(readLines(f, warn = FALSE), collapse = "\n"),
                  fixed = TRUE)
        regmatches(x, gregexpr("[0-9][0-9,]*(\\.[0-9]+)?|\\.[0-9]+", x))[[1]]
    }))
    unique(gsub(",", "", v))
}

# Years and crawl stamps are structure, not claims.
is_structural <- function(v) grepl("^(19|20)[0-9]{2}$|^(19|20)[0-9]{6}$", v)

check_prose <- function(ms = here("ms", "blacklight.tex"),
                        tables = TABLES_DIR) {
    prose <- prose_numbers(ms)
    art <- artifact_numbers(tables)
    # Prose rounds. "6.19" in a sentence and 6.193 in a table are the same
    # claim, so a prose number matches an artifact value that rounds to it at
    # the precision the prose actually wrote. Demanding equality instead would
    # flag every honest rounding and bury the real drift among them. The
    # precision comes from the written string, so 19,701 still fails against
    # 19,702: at zero decimals they are different numbers.
    decimals <- function(v) {
        if (!grepl(".", v, fixed = TRUE)) return(0L)
        nchar(sub("^[^.]*\\.", "", v))
    }
    art_num <- suppressWarnings(as.numeric(art))
    art_num <- art_num[!is.na(art_num)]
    allow_num <- suppressWarnings(as.numeric(names(ALLOWED)))
    allow_num <- allow_num[!is.na(allow_num)]

    matches <- function(v, pool) {
        x <- suppressWarnings(as.numeric(v))
        if (is.na(x)) return(FALSE)
        any(round(pool, decimals(v)) == x)
    }
    in_table <- vapply(prose, matches, logical(1), pool = art_num,
                       USE.NAMES = FALSE)
    in_allow <- vapply(prose, matches, logical(1), pool = allow_num,
                       USE.NAMES = FALSE)
    bad <- prose[!is_structural(prose) & !in_table & !in_allow]

    cat(sprintf("  prose numbers: %d; in a table: %d; allowlisted: %d\n",
                length(prose), sum(in_table), sum(in_allow)))
    if (length(bad)) {
        cat("\n  Numbers in the manuscript that match no table, no macro and no\n")
        cat("  allowlist entry. Each is typed by hand and cannot be caught\n")
        cat("  drifting. Register it in the pipeline and cite the macro, or add\n")
        cat("  it to ALLOWED with the reason it is not an estimate.\n\n")
        for (v in bad) cat(sprintf("      %s\n", v))
        stop(length(bad), " unsourced number(s) in the manuscript", call. = FALSE)
    }
    cat("  every number in the manuscript resolves\n")
    invisible(TRUE)
}
