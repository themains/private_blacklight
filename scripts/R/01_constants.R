# 01_constants.R
# Measure vocabulary, labels, the age cut, and the regression spec.
# One home for anything the tables, figures and prose must agree on.

# ---------------------------------------------------------------------------
# Blacklight measures
# ---------------------------------------------------------------------------
# Card type in the scan JSON -> column name. The two count cards carry
# bigNumber; the five behavioural cards are flags on testEventsFound.
BL_COUNT_CARDS <- c(ddg_join_ads = "ddg_join_ads", cookies = "third_party_cookies")
BL_FLAG_CARDS  <- c(
    canvas_fingerprinters = "canvas_fingerprinting",
    session_recorders     = "session_recording",
    key_logging           = "key_logging",
    fb_pixel_events       = "fb_pixel",
    ga                    = "google_analytics"
)

# Display order for the manuscript tables.
# The paper carries two measure orders. The descriptive tables and the prose
# ("session recording, keylogging and canvas fingerprinting") put session
# recording first; the regression tables swap it with keylogging. Nothing turns
# on the difference, but both are reproduced rather than silently unified --
# changing either would alter a published table.
MEASURES_DESC <- c("ddg_join_ads", "third_party_cookies", "fb_pixel",
                   "google_analytics", "session_recording", "key_logging",
                   "canvas_fingerprinting")

# Column order for Tables 5 and 6: keylogging precedes session recording.
MEASURES <- c("ddg_join_ads", "third_party_cookies", "fb_pixel", "google_analytics",
              "key_logging", "session_recording", "canvas_fingerprinting")

SHORT <- c(ddg_join_ads = "Ad", third_party_cookies = "Cookies",
           fb_pixel = "FB Pixel", google_analytics = "GA Remkt.",
           key_logging = "Keylogger", session_recording = "Session rec",
           canvas_fingerprinting = "Canvas FP")

VAR_LABELS <- c(
    ddg_join_ads          = "Ad Trackers",
    third_party_cookies   = "Third-Party Cookies",
    fb_pixel              = "Facebook Pixel",
    # Blacklight's `ga` card detects the "remarketing audiences" feature -- a
    # request to stats.g.doubleclick.net carrying a UA-/G-/AW- account id -- not
    # the presence of Google Analytics. A positive implies both; a negative means
    # remarketing was not detected, not that Analytics is absent.
    google_analytics      = "Google Analytics (Remarketing)",
    session_recording     = "Session Recording",
    key_logging           = "Keylogging",
    canvas_fingerprinting = "Canvas Fingerprinting"
)

# ---------------------------------------------------------------------------
# Age
# ---------------------------------------------------------------------------
# The panel was fielded June 2022 and profile.csv carries birthyr but no birth
# month, so age is accurate to +/-1 year. Edges are set so each label's boundary
# cohort *can* be that age: birthyr 1957 is 65 for roughly half the cohort,
# whereas 1958 is 63 or 64 and never 65. All five groups are then their nominal
# brackets, "<25" being birthyr 1998-2003, i.e. ages 18-24.
AGE_BINS   <- c(1929, 1957, 1972, 1987, 1997, 2003)
AGE_LABELS <- c("65+", "50-64", "35-49", "25-34", "<25")
AGE_ORDER  <- c("<25", "25-34", "35-49", "50-64", "65+")

agegroup_from_birthyr <- function(birthyr) {
    factor(cut(birthyr, breaks = AGE_BINS, labels = AGE_LABELS),
           levels = AGE_ORDER, ordered = TRUE)
}

# ---------------------------------------------------------------------------
# Demographics (Table 1 Panel B)
# ---------------------------------------------------------------------------
DEMO_CAT_ORDER <- c("Female", "Male", "White", "Hispanic", "Black", "Other", "Asian",
                    "HS or Below", "Some college", "College", "Postgrad", AGE_ORDER)

DEMO_CAT_LABELS <- c(
    "<25" = "$<$ 25 years old", "25-34" = "25--34 years old",
    "35-49" = "35--49 years old", "50-64" = "50--64 years old",
    "65+" = "65+ years old",
    "HS or Below" = "High school diploma or below",
    "Some college" = "Some college",
    "College" = "College graduate", "Postgrad" = "Postgraduate"
)

# ---------------------------------------------------------------------------
# Regression spec behind Tables 5 and 6
# ---------------------------------------------------------------------------
FORMULA_RHS <- paste(
    "relevel(factor(gender_lab), ref = 'Male')",
    "relevel(factor(race_lab), ref = 'White')",
    "relevel(factor(educ_lab), ref = 'HS or Below')",
    "relevel(factor(agegroup_lab), ref = '<25')",
    sep = " + "
)

# Grayscale line vocabulary, shared by every multi-measure figure.
PALETTE7 <- c("#000000", "#2f2f2f", "#4d4d4d", "#6c6c6c", "#8a8a8a", "#a8a8a8", "#c7c7c7")
LINETYPES7 <- c("solid", "dashed", "dotdash", "dotted", "longdash", "twodash", "12")

# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------
# The Python pipeline seeded numpy's PCG64. R cannot reproduce that stream, and
# freezing the draws to a file to fake it would be worse than the problem: it
# would make an RNG state look like data. We draw our own with the seed below,
# so bootstrap intervals and placebo p-values differ from the published ones in
# their last digits. Point estimates are unaffected -- they are not resampled.
BOOTSTRAP_SEED <- 20250110
BOOTSTRAP_REPS <- 1000
PLACEBO_DRAWS  <- 10000

# Cumulative outcomes rescaled by 100 so the table columns stay narrow.
RESCALE_100 <- c("bl_ddg_join_ads", "bl_third_party_cookies", "top_org_visits")

# The 65+ contrast is the paper's headline demographic comparison, named once
# here so every module that reports it reads the same row.
AGE_TERM_LABEL <- "Age: 65+"

# ---------------------------------------------------------------------------
# Manuscript floats
# ---------------------------------------------------------------------------
# Caption, label, column names and alignment for the five numbered tables, so
# the header that describes a column lives beside the code that fills it.
FLOATS <- list(
    tab2 = list(
        label = "cumulative-exposure",
        align = "lrrrrrrrrr",
        header = c("Measure", "Mean", "SD", "Min", "P25", "Median", "P75", "Max", "$\\geq 1$", "$\\geq 10$"),
        caption = paste(
            "Cumulative tracking exposure per panelist over the month. The",
            "final two columns give the share of panelists who encountered the",
            "technique at least once and at least ten times. Ad trackers and",
            "third-party cookies are counts of distinct third-party domains;",
            "the remaining measures are binary indicators of whether the",
            "technique was present on the domain. Visits to domains Blacklight",
            "did not scan contribute zero, so every figure is a lower bound."
        )
    ),
    tab3 = list(
        label = "exposure-rate",
        align = "lrrrrrrr",
        header = c("Measure", "Mean", "SD", "Min", "P25", "Median", "P75", "Max"),
        caption = paste(
            "Tracking exposure per visit. For ad trackers and third-party",
            "cookies this is the number of distinct third parties encountered",
            "per visit and can exceed one; for the binary measures it is the",
            "share of visits on which the technique was present. Ad trackers",
            "and third-party cookies are counts of distinct third-party",
            "domains; the remaining measures are binary indicators of whether",
            "the technique was present on the domain. Visits to domains",
            "Blacklight did not scan contribute zero, so every figure is a",
            "lower bound."
        )
    ),
    tab4 = list(
        label = "bl_top_contributors_domain",
        align = "lrrrrrrr",
        header = c("Rank", "Ad trackers", "Cookies", "FB Pixel", "GA Remkt.", "Session rec", "Keylogger", "Canvas FP"),
        caption = paste(
            "Domains contributing the most tracking exposure, visit-weighted",
            "across the panel."
        )
    ),
    tab5 = list(
        label = "demo_differences_cum_exposure",
        align = "lcccccccc",
        header = c("Measure", "Ad (00s)", "Cookies (00s)", "FB Pixel", "GA Remkt.", "Keylogger", "Session rec", "Canvas FP", "Top org visits (00s)"),
        caption = paste(
            "Demographic differences in cumulative tracking exposure. OLS with",
            "Huber-White (HC1) standard errors in parentheses. Ad trackers,",
            "third-party cookies and top-organisation visits are expressed in",
            "hundreds. $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$."
        )
    ),
    tab6 = list(
        label = "demo_differences_exposure_rate",
        align = "lcccccccc",
        header = c("Measure", "Ad", "Cookies", "FB Pixel", "GA Remkt.", "Keylogger", "Session rec", "Canvas FP", "Top org share"),
        caption = paste(
            "Demographic differences in tracking exposure per visit. OLS with",
            "Huber-White (HC1) standard errors in parentheses. Reference",
            "categories are male, white, high school or below, and under 25.",
            "$^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$."
        )
    )
)

# The Table 5 right-hand side without the age bins, for specifications that put
# birth year in continuously instead.
FORMULA_RHS_NOAGE <- paste(
    "relevel(factor(gender_lab), ref = 'Male')",
    "relevel(factor(race_lab), ref = 'White')",
    "relevel(factor(educ_lab), ref = 'HS or Below')",
    sep = " + "
)
