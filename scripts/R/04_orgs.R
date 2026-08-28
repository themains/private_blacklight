# 04_orgs.R
# Attribute third-party hosts to parent organizations.

# ---------------------------------------------------------------------------
# Registered domain, against a pinned public suffix list
# ---------------------------------------------------------------------------
# The Python pipeline used tldextract, which fetches the list at run time into
# ~/.cache and pins nothing, so organization attribution was not reproducible
# from the repository. data/tracker_lists/public_suffix_list.dat is that
# resolved rule set, frozen. Standard algorithm: the registered domain is the
# longest matching rule plus one more label; "*" matches any single label; a
# "!" rule is an exception that shortens the match by one.
psl_rules <- local({
    cache <- NULL
    function() {
        if (is.null(cache)) {
            x <- readLines(file.path(DATA_DIR, "tracker_lists", "public_suffix_list.dat"),
                           warn = FALSE)
            x <- x[nzchar(x) & !startsWith(x, "//")]
            cache <<- list(
                normal    = new.env(hash = TRUE, parent = emptyenv()),
                wildcard  = sub("^\\*\\.", "", x[startsWith(x, "*.")]),
                exception = sub("^!", "", x[startsWith(x, "!")])
            )
            for (r in x[!startsWith(x, "*.") & !startsWith(x, "!")])
                assign(r, TRUE, envir = cache$normal)
        }
        cache
    }
})

registered_domain <- function(host) {
    p <- psl_rules()
    vapply(host, function(h) {
        if (is.na(h) || !nzchar(h)) return(NA_character_)
        lab <- strsplit(tolower(h), ".", fixed = TRUE)[[1]]
        n <- length(lab)
        if (n < 2) return("")   # single label: no registrable domain
        best <- 0L
        for (i in seq_len(n)) {
            cand <- paste(lab[i:n], collapse = ".")
            if (cand %in% p$exception) { best <- n - i; break }
            if (!is.null(p$normal[[cand]])) { best <- max(best, n - i + 1L); next }
            if (i > 1 && paste(lab[(i + 1):n], collapse = ".") %in% p$wildcard)
                best <- max(best, n - i + 1L)
        }
        # No rule matched any suffix -- a bare IP, a hostname with no public
        # suffix, junk. tldextract returns empty rather than guessing, and so
        # do we: these carry no registrable domain to attribute to an owner.
        if (best == 0L) return("")
        if (best >= n) return(h)            # host is itself a suffix
        paste(lab[(n - best):n], collapse = ".")
    }, character(1), USE.NAMES = FALSE)
}

# ---------------------------------------------------------------------------
# Organization attribution
# ---------------------------------------------------------------------------
# Each scan names the third-party hosts it contacted. Mapping those to parent
# organizations through DuckDuckGo's Tracker Radar answers how much of one
# person's browsing a single company can observe.
#
# data/tracker_lists/ddg_domain_map.json is the committed mapping. The vintage
# that produced the published numbers was an unpinned checkout that is gone;
# this one differs by 57 domains and moves top_org_share by at most 0.0015,
# leaving the median at 0.5447 and Table 5's 65+ coefficient unchanged at
# display precision.
# One walk of the scan payloads, reused by everything that needs to know which
# third parties a domain loads: organization attribution here, and the Google
# reach check in 10_validity. Returns registrable third-party domains, so the
# pinned public suffix list is applied once rather than per consumer.
extract_third_parties <- function(json_dir = FP_BL_JSON_DIR) {
    files <- sort(list.files(json_dir, pattern = "\\.json$"))
    message(sprintf("Extracting third parties from %s scans",
                    format(length(files), big.mark = ",")))
    out <- vector("list", length(files))
    for (i in seq_along(files)) {
        j <- jsonlite::fromJSON(file.path(json_dir, files[i]), simplifyVector = FALSE)
        tp <- j$hosts$requests$third_party
        if (!length(tp)) next
        out[[i]] <- data.table(
            private_domain = j$host %||% gsub("_", ".", sub("\\.json$", "", files[i]),
                                              fixed = TRUE),
            tp = unlist(tp, use.names = FALSE))
        if (i %% 10000 == 0) message(sprintf("  %s/%s", i, length(files)))
    }
    d <- rbindlist(out)
    d[, tp_domain := registered_domain(tp)]
    unique(d[nzchar(tp_domain), .(private_domain, tp_domain)])
}

domain_org_pairs <- function(tp = extract_third_parties()) {
    raw <- jsonlite::fromJSON(file.path(DATA_DIR, "tracker_lists", "ddg_domain_map.json"),
                              simplifyVector = FALSE)
    owner <- vapply(raw, function(x) x$entityName %||% NA_character_, character(1))
    d <- as.data.table(tp)[, org := owner[tp_domain]]
    unique(d[!is.na(org), .(private_domain, org)])
}

# Per person: how many organizations see them, how much the biggest one sees,
# and how unevenly that attention is divided.
build_org_measures <- function(pairs, weight = "visits") {
    visits <- visit_panel()[!is.na(private_domain)]
    visits[, w := get(weight)]
    cap <- merge(visits, pairs, by = "private_domain", allow.cartesian = TRUE)[
        , .(captured = sum(w)), by = .(caseid, org)]
    tt <- visits[, .(tt = sum(w)), by = caseid]
    top <- cap[, .(top_org_visits = max(captured), n_orgs = .N), by = caseid]
    out <- merge(tt, top, by = "caseid", all.x = TRUE)
    out[is.na(top_org_visits), `:=`(top_org_visits = 0, n_orgs = 0)]
    out[, top_org_share := top_org_visits / tt][, tt := NULL][]
}

# The same concentration question weighted by time rather than page loads. A
# visit and an hour are different units of attention, and the manuscript reports
# both so the concentration result cannot be an artifact of counting page loads.
build_org_share_duration <- function(pairs) {
    d <- build_org_measures(pairs, weight = "duration")
    d[, .(caseid, top_org_share_duration = top_org_share)]
}

# Concentration: how unevenly one person's browsing is divided among the
# organizations that see any of it. Gini over each panelist's captured-visit
# counts, so 0 means every organization sees the same amount and 1 means one
# organization sees everything.
gini <- function(x) {
    x <- sort(x[x > 0])
    n <- length(x)
    if (n < 2) return(NA_real_)
    sum((2 * seq_len(n) - n - 1) * x) / (n * sum(x))
}

# Reach counts the panelists an organization tracks at all; dominance counts
# those for whom it observes more than any other. The gap between the two is
# the point: many organizations reach a lot of people, few dominate anyone.
build_org_reach <- function(pairs) {
    visits <- visit_panel()[!is.na(private_domain)]
    cap <- merge(visits, pairs, by = "private_domain", allow.cartesian = TRUE)[
        , .(captured = sum(visits)), by = .(caseid, org)]
    reach <- cap[, .(reach = uniqueN(caseid)), by = org]
    top <- cap[cap[, .I[which.max(captured)], by = caseid]$V1]
    dom <- top[, .(dominance = .N), by = org]
    out <- merge(reach, dom, by = "org", all.x = TRUE)
    out[is.na(dominance), dominance := 0L][]
}

build_org_gini <- function(pairs) {
    visits <- visit_panel()[!is.na(private_domain)]
    cap <- merge(visits, pairs, by = "private_domain", allow.cartesian = TRUE)[
        , .(captured = sum(visits)), by = .(caseid, org)]
    cap[, .(gini_exposure = gini(captured)), by = caseid]
}
