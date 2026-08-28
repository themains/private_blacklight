"""15_format_ms_tables.py
Wrap pipeline table fragments into the float environments the manuscript inputs.

ms/blacklight.tex reads tables/tab2_formatted .. tab6_formatted, and none of
them existed in the repo or in git history -- they were maintained by hand
outside version control, which is where a number can drift away from the script
that produced it without anything noticing. This script closes that gap: the
numbers still come from the pipeline fragments, and only the caption, column
headers and label are added here.

Input:  tables/individual_blacklight_cumulative_exposure_summary.tex  (03_exposure)
        tables/individual_blacklight_exposure_rate_summary.tex        (03_exposure)
        tables/demo_differences_exposure_rate.tex                     (07_demo_differences)
        tables/demo_differences_cum_exposure.tex                      (07_demo_differences)
        tables/bl_top_contributors_domain.tex                         (05_top_bltracker_domain)
Output: tables/tab2_formatted.tex  (Table 2, tab:cumulative-exposure)
        tables/tab3_formatted.tex  (Table 3, tab:exposure-rate)
        tables/tab4_formatted.tex  (Table 4, tab:bl_top_contributors_domain)
        tables/tab5_formatted.tex  (Table D.1, tab:demo_differences_cum_exposure)
        tables/tab6_formatted.tex  (Table D.2, tab:demo_differences_exposure_rate)
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

REPO = os.path.abspath(os.path.join(_HERE, ".."))
TABLES = os.path.join(REPO, "tables")

# The seven measures are not commensurable: ad trackers and third-party cookies
# are counts of distinct third parties, the other five are binary presence
# flags. Said once here so every caption inherits it.
MEASURE_NOTE = (
    "Ad trackers and third-party cookies are counts of distinct third-party "
    "domains; the remaining measures are binary indicators of whether the "
    "technique was present on the domain. Visits to domains Blacklight did not "
    "scan contribute zero, so every figure is a lower bound."
)

BARE = {
    "tab2_formatted": dict(
        fragment="individual_blacklight_cumulative_exposure_summary.tex",
        label="tab:cumulative-exposure",
        align="lrrrrrrrrr",
        header=(
            r"Measure & Mean & SD & Min & P25 & Median & P75 & Max & "
            r"$\geq 1$ & $\geq 10$ \\"
        ),
        caption=(
            "Cumulative tracking exposure per panelist over the month. "
            "The final two columns give the share of panelists who encountered "
            "the technique at least once and at least ten times. " + MEASURE_NOTE
        ),
    ),
    "tab3_formatted": dict(
        fragment="individual_blacklight_exposure_rate_summary.tex",
        label="tab:exposure-rate",
        align="lrrrrrrr",
        header=r"Measure & Mean & SD & Min & P25 & Median & P75 & Max \\",
        caption=(
            "Tracking exposure per visit. For ad trackers and third-party "
            "cookies this is the number of distinct third parties encountered "
            "per visit and can exceed one; for the binary measures it is the "
            "share of visits on which the technique was present. " + MEASURE_NOTE
        ),
    ),
    "tab4_formatted": dict(
        fragment="bl_top_contributors_domain.tex",
        label="tab:bl_top_contributors_domain",
        align="lrrrrrrr",
        # Column order must follow tracker_cols in 05_top_bltracker_domain:
        # ads, cookies, fb_pixel, google_analytics, session_recording,
        # key_logging, canvas_fingerprinting. The previous header listed Canvas
        # and Session before FB and GA, mislabelling four of the seven columns.
        # The first column holds a rank, not a domain name.
        header=(
            r"Rank & Ad trackers & Cookies & FB Pixel & GA Remkt. & "
            r"Session rec & Keylogger & Canvas FP \\"
        ),
        caption=(
            "Domains contributing the most tracking exposure, visit-weighted "
            "across the panel."
        ),
    ),
}

# Both regression tables are bare rows since 07_demo_differences.py replaced
# the fixest version, which used to emit its own adjustbox tabular.
REG_HEAD = (
    r"Ad & Cookies & FB Pixel & GA Remkt. & Keylogger & Session rec & Canvas FP & Top org share"
)
BARE["tab5_formatted"] = dict(
    fragment="demo_differences_cum_exposure.tex",
    label="tab:demo_differences_cum_exposure",
    align="l" + "c" * 8,
    header=(
        r"Measure & Ad (00s) & Cookies (00s) & FB Pixel & GA Remkt. & Keylogger & "
        r"Session rec & Canvas FP & Top org visits (00s) \\"
    ),
    caption=(
        "Demographic differences in cumulative tracking exposure. OLS with "
        "Huber-White (HC1) standard errors in parentheses. Ad trackers, "
        "third-party cookies and top-organisation visits are expressed in "
        "hundreds. $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$."
    ),
)
BARE["tab6_formatted"] = dict(
    fragment="demo_differences_exposure_rate.tex",
    label="tab:demo_differences_exposure_rate",
    align="l" + "c" * 8,
    header="Measure & " + REG_HEAD + r" \\",
    caption=(
        "Demographic differences in tracking exposure per visit. OLS with "
        "Huber-White (HC1) standard errors in parentheses. Reference "
        "categories are male, white, high school or below, and under 25. "
        "$^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$."
    ),
)

WRAPPED = {}


def read_fragment(name):
    path = os.path.join(TABLES, name)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} is missing. It is produced by the pipeline -- see this "
            "module's docstring for which script writes it."
        )
    body = open(path).read().strip()
    if not body:
        raise ValueError(
            f"{path} is empty. The R script this replaced truncated it for 13 "
            "months via a cat()/writeLines bug; run 07_demo_differences.py first."
        )
    return body


def build_bare(spec):
    """Fragment is bare tabular rows: supply tabular, header and rules."""
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{" + spec["caption"] + "}",
            r"\label{" + spec["label"] + "}",
            r"\begin{adjustbox}{max width=\textwidth}",
            r"\begin{tabular}{" + spec["align"] + "}",
            r"\toprule",
            spec["header"],
            r"\midrule",
            read_fragment(spec["fragment"]),
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{adjustbox}",
            r"\end{table}",
        ]
    )


def build_wrapped(spec):
    """Fragment is already a centred adjustbox tabular: add the float only."""
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{" + spec["caption"] + "}",
            r"\label{" + spec["label"] + "}",
            read_fragment(spec["fragment"]),
            r"\end{table}",
        ]
    )


def main():
    print("=== Formatting manuscript tables ===")
    written = []
    for stem, spec in BARE.items():
        out = os.path.join(TABLES, f"{stem}.tex")
        with open(out, "w") as f:
            f.write(build_bare(spec) + "\n")
        written.append((stem, spec["label"], spec["fragment"]))
        print(f"  Saved: tables/{stem}.tex  <- {spec['fragment']}")

    for stem, spec in WRAPPED.items():
        out = os.path.join(TABLES, f"{stem}.tex")
        with open(out, "w") as f:
            f.write(build_wrapped(spec) + "\n")
        written.append((stem, spec["label"], spec["fragment"]))
        print(f"  Saved: tables/{stem}.tex  <- {spec['fragment']}")

    print(f"\n{len(written)} manuscript tables formatted from pipeline fragments.")
    print("=== Formatting Complete ===")


if __name__ == "__main__":
    sys.exit(main())
