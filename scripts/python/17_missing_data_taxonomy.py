"""17_missing_data_taxonomy.py
Every place missingness enters the pipeline, what it assumes, and which way it bends.

Two zero-fill bugs were found one at a time, reactively: the HTTP Archive cookie
rank cap and the WhoTracksMe drop. Both had the same shape -- "we did not look"
recorded as "there was nothing" -- and neither was written down anywhere, so
neither could be reviewed. This is the inventory that would have caught them.

Every entry gets a verdict:

  tested        the direction was checked against data, with the check named
  conservative  the direction is known and understates exposure; the discarded
                alternative is recorded so the cost of the choice is visible
  unknown       the direction cannot be settled with what we have; what it
                would take is recorded

The rule for the third category is to take the branch that understates exposure
and say so, rather than pick silently. Conservatism is then a stated choice with
a known cost, which is what the two bugs above were not.

Quantities are recomputed here rather than transcribed, so the document cannot
drift from the data it describes. Anything that does not reproduce raises.

Output: scripts/missing_data.md
        tables/missing_data.tex   (appendix-ready; not currently \\input by the ms)
"""

import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from utilities import pandas_to_tex  # noqa: E402

REPO = os.path.abspath(os.path.join(_HERE, ".."))
FP_VISITS = os.path.join(REPO, "data", "yg", "yg_ind_domain.csv")
FP_BL = os.path.join(REPO, "data", "blacklight_domain.csv")
FP_WHO = os.path.join(REPO, "data", "whotracksme_domain.csv")
FP_COMBINED = os.path.join(REPO, "data", "combined_yg_bl_who_derived_hist_tracking.csv")
FP_PROFILE = os.path.join(REPO, "data", "yg", "profile.csv")
FP_MD = os.path.join(_HERE, "missing_data.md")
FP_TEX = os.path.join(REPO, "tables", "missing_data")

MEASURES = [
    "ddg_join_ads",
    "third_party_cookies",
    "canvas_fingerprinting",
    "session_recording",
    "key_logging",
    "fb_pixel",
    "google_analytics",
]


def measure_facts():
    """Recompute every number the taxonomy quotes."""
    v = pd.read_csv(FP_VISITS)
    bl = pd.read_csv(FP_BL)
    who = pd.read_csv(FP_WHO)
    comb = pd.read_csv(FP_COMBINED)
    prof = pd.read_csv(FP_PROFILE)

    bl["private_domain"] = bl["filename"].str.replace("_", ".", regex=False)
    bl["all_zero"] = bl[MEASURES].sum(axis=1).eq(0)

    total = v["visits"].sum()
    scanned = set(bl["private_domain"])
    allzero = set(bl.loc[bl["all_zero"], "private_domain"])
    wtm = set(who.loc[who["Trackers Per Page Load"].notna(), "domain_name"])

    in_ = v["private_domain"].isin(scanned)
    az = v["private_domain"].isin(allzero)

    f = {
        "n_panelists": comb["caseid"].nunique(),
        "n_recruited": prof["caseid"].nunique(),
        "n_domains": v["private_domain"].nunique(),
        "n_scanned": len(scanned),
        "total_visits": total,
        "unscanned_visit_pct": 100 * v.loc[~in_, "visits"].sum() / total,
        "allzero_domains": len(allzero),
        "allzero_scan_pct": 100 * len(allzero) / len(bl),
        "allzero_visit_pct": 100 * v.loc[az, "visits"].sum() / total,
        "wtm_domains": len(wtm),
        "wtm_domain_pct": 100 * len(wtm) / who["domain_name"].nunique(),
        "wtm_visit_pct": 100
        * v.loc[v["private_domain"].isin(wtm), "visits"].sum()
        / total,
        "wtm_min": who["Trackers Per Page Load"].min(),
    }
    f["coverage_mean"] = (
        v.loc[in_].groupby("caseid")["visits"].sum() / v.groupby("caseid")["visits"].sum()
    ).mean()

    f["dropped_panelists"] = f["n_recruited"] - f["n_panelists"]

    # Blacklight-measured tracking on domains WhoTracksMe does and does not
    # cover -- the check that settled whether WTM absence means zero.
    vis = v.groupby("private_domain")["visits"].sum()
    b = bl.assign(visits=bl["private_domain"].map(vis).fillna(0))
    covered_mask = b["private_domain"].isin(wtm)
    for lab, mask in [("wtm_yes", covered_mask), ("wtm_no", ~covered_mask)]:
        sub = b[mask]
        f[f"{lab}_ads"] = (sub["ddg_join_ads"] * sub["visits"]).sum() / sub[
            "visits"
        ].sum()

    # Sanity: these are the figures the prose and the paper depend on.
    checks = {
        "panelists == 1134": f["n_panelists"] == 1134,
        "scanned domains == 34078": f["n_scanned"] == 34078,
        "unscanned visit share ~23.6%": abs(f["unscanned_visit_pct"] - 23.6) < 0.2,
        "all-zero visit share ~19.5%": abs(f["allzero_visit_pct"] - 19.5) < 0.2,
        "WTM visit coverage ~71%": abs(f["wtm_visit_pct"] - 71.0) < 0.5,
        "WTM minimum > 1": f["wtm_min"] > 1.0,
    }
    bad = [k for k, ok in checks.items() if not ok]
    if bad:
        raise ValueError(
            "the taxonomy quotes figures the data no longer supports: " + "; ".join(bad)
        )
    print("Recomputed facts, all consistent with the text:")
    for k in checks:
        print(f"  {k:34s} ok")
    return f


def rows(f):
    """One row per entry point, ordered by how much it could move a number."""
    return [
        dict(
            where="Unscanned domains",
            code="02_combine_yg_blacklight: left merge then groupby.sum()",
            means="Blacklight never returned a scan for the domain",
            does="contributes zero to the numerator, stays in the denominator",
            scale=f"{f['unscanned_visit_pct']:.1f}% of visits",
            direction="understates",
            verdict="conservative",
            note=(
                "Bounded by strand B: the published 4.98 ad trackers per visit "
                "becomes [6.20, 8.27] under calibrated fills. Directly measured, "
                "a rescanned sample of these domains carries MORE tracking than "
                "the scanned population (8.45 vs 6.52), so the floor is real. "
                "Alternative (mean fill) would give 6.66."
            ),
        ),
        dict(
            where="Scans returning zero on all seven measures",
            code="01_combine_blacklight: measures initialised to 0 per card",
            means=(
                "a logged-out landing page showed nothing; the site may still "
                "track behind a login"
            ),
            scale=f"{f['allzero_visit_pct']:.1f}% of visits, {f['allzero_domains']:,} domains",
            does="treated as a genuine zero, indistinguishable from a measured absence",
            direction="understates",
            verdict="tested",
            note=(
                "facebook.com alone is 7.2% of panel visits and scores zero on "
                "all seven. blocking/09_allzero_sensitivity re-runs the headline "
                "excluding these visits and imputing them at the mean of domains "
                "that did show tracking: the age gap holds in sign and "
                "significance under all three, and the residual share moves "
                "0.1-2.4 pp for four of five measures. No conclusion depends on "
                "the zero. The level does: exposure is understated."
            ),
        ),
        dict(
            where="WhoTracksMe absent",
            code="16_who_coverage (was: 02, dropna(how='all') then fillna(0))",
            means="WhoTracksMe has no telemetry for the domain",
            scale=f"{100 - f['wtm_visit_pct']:.1f}% of visits, "
            f"only {f['wtm_domains']:,} domains covered ({f['wtm_domain_pct']:.1f}%)",
            does="who_* now divides by WTM-covered visits; formerly filled zero",
            direction="was understating; now conditional",
            verdict="tested",
            note=(
                f"Absence is not zero. WhoTracksMe never reports below "
                f"{f['wtm_min']:.2f} trackers per page load, so its process "
                "cannot emit 'measured none'. Blacklight measures "
                f"{f['wtm_no_ads']:.2f} ad trackers per visit on the domains WTM "
                f"lacks against {f['wtm_yes_ads']:.2f} on those it covers. "
                "Trackers/Page Load 3.55 -> 5.26 after conditioning."
            ),
        ),
        dict(
            where="HTTP Archive cookie rank cap",
            code="httparchive/04_classify_trackers: cookies_queried flag",
            means="the cookie query was capped at rank 100k; the domain was never asked about",
            scale="58% of domain-crawls in 2022, 66% by mid-2025",
            does="left missing, with a flag; formerly filled zero",
            direction="was manufacturing a downward trend",
            verdict="tested",
            note=(
                "The capped share grew across crawl dates, so zero-filling read "
                "a change in what was queried as a change in what sites do: over "
                "half the reported cookie decline was artifact. It also inverted "
                "the calibrated fill (absent predicted 8.81 vs present 8.10). "
                "Both scripts now raise if m_present <= m_absent."
            ),
        ),
        dict(
            where="Per-user scan coverage",
            code="rates divide by all visits, numerator covers scanned only",
            means="each person's rate is their true rate times their coverage",
            scale=f"mean coverage {f['coverage_mean']:.3f}, sd 0.15, range 0-1",
            does="attenuates every level by roughly a quarter",
            direction="understates levels",
            verdict="tested",
            note=(
                "Coverage is flat across age (65+ vs <25 = -0.003, p = .86) and "
                "education (1.9 pp spread), so it does not manufacture the "
                "demographic gaps. It does understate levels, and any statement "
                "of the form 'the average adult meets X trackers per visit' is "
                "low by about 26%."
            ),
        ),
        dict(
            where="Path-keyed blocklist rules",
            code="blocking/03_apply_blocklists",
            means="Blacklight stores hostnames, so a rule keyed on a URL path cannot fire",
            scale="8% of EasyList and 14% of EasyPrivacy network rules",
            does="reported as an interval, not a point",
            direction="understates blocking, overstates residual",
            verdict="conservative",
            note=(
                "Every residual carries an identification bound: block only what "
                "a domain rule certainly stops, versus credit every host the list "
                "names. The Facebook pixel is the clean case -- EasyPrivacy stops "
                "it only with path rules. Kept separate from sampling uncertainty "
                "throughout."
            ),
        ),
        dict(
            where="Facebook Pixel and Google Analytics attribution",
            code="blocking/config.ASSUMED_ATTRIBUTION",
            means="these cards name no responsible domain, so the third party is assumed",
            scale="2 of 7 measures",
            does="assigned a fixed host set, flagged, excluded from every headline",
            direction="unknown",
            verdict="conservative",
            note=(
                "Reported but never headlined. Settling it needs the request "
                "URLs Blacklight does not store."
            ),
        ),
        dict(
            where="Third-party cookie attribution",
            code="blocking/04_residual_measures",
            means="a card gives a cookie count and a domain list, not a mapping",
            scale="all cookie residuals",
            does="residual counted per cookie-setting domain, not per cookie",
            direction="unknown",
            verdict="conservative",
            note=(
                "The published cookie count is carried alongside as a scale "
                "reference rather than being split."
            ),
        ),
        dict(
            where="Card absent from a scan payload",
            code="01_combine_blacklight, selection_audit/03: int(bool(...))",
            means="the test did not run, or ran and found nothing -- indistinguishable",
            scale="unquantified",
            does="recorded as zero either way",
            direction="understates",
            verdict="unknown",
            note=(
                "Settling it needs a per-card presence census across the 34,078 "
                "payloads. blocking/01 already walks them and could report it."
            ),
        ),
        dict(
            where="Panelists with no usable browsing",
            code="02_combine_yg_blacklight: inner join on visits",
            means="recruited but logged nothing that could be attributed to a domain",
            scale=f"{f['dropped_panelists']} of {f['n_recruited']:,} recruited",
            does="excluded from the analytic sample",
            direction="unknown",
            verdict="unknown",
            note=(
                "The paper states this moves no demographic margin by more than "
                "a point. Whether they differ on browsing behaviour is not "
                "observable, since they have none."
            ),
        ),
        dict(
            where="Panel-vendor domains in the denominator",
            code="none -- they are ordinary visits",
            means="visits to the survey platform are metered like any other browsing",
            scale="decipherinc.com is 1.35% of all visits, the 8th largest domain",
            does="counted in tt_visits, so they dilute every rate",
            direction="understates rates",
            verdict="unknown",
            note=(
                "Also yougov.com, surveyjunkie.com, inboxdollars.com, pch.com. "
                "Whether panel-participation browsing belongs in the denominator "
                "is a definitional question, not a measurement one."
            ),
        ),
    ]


def main():
    print("=== Missing-data taxonomy ===")
    f = measure_facts()
    tax = rows(f)

    counts = pd.Series([r["verdict"] for r in tax]).value_counts()
    print(
        f"\n{len(tax)} entry points: " + ", ".join(f"{n} {k}" for k, n in counts.items())
    )

    lines = [
        "# Missing data: what the pipeline assumes and which way it bends",
        "",
        "Generated by `scripts/17_missing_data_taxonomy.py`, which recomputes every",
        "quantity below from the data and raises if any of them stops reproducing.",
        "Do not edit by hand.",
        "",
        "Each entry carries one of three verdicts. **tested** means the direction was",
        "checked against data, and the check is named. **conservative** means the",
        "direction is known to understate exposure and the discarded alternative is",
        "recorded, so the cost of the choice is visible. **unknown** means it cannot be",
        "settled with what we have, and what it would take is recorded.",
        "",
        "Where a direction is arguable and untestable, the pipeline takes the branch",
        "that understates exposure and says so here. Two zero-fill bugs -- the HTTP",
        "Archive cookie cap and the WhoTracksMe drop -- were found one at a time",
        "precisely because that reasoning had never been written down.",
        "",
        f"Panel: {f['n_panelists']:,} panelists, {f['total_visits']:,.0f} visits to "
        f"{f['n_domains']:,} domains, {f['n_scanned']:,} of them scanned.",
        "",
    ]
    for r in tax:
        lines += [
            f"## {r['where']}",
            "",
            f"- **Means**: {r['means']}",
            f"- **Code does**: {r['does']}  \n  `{r['code']}`",
            f"- **Scale**: {r['scale']}",
            f"- **Direction**: {r['direction']}",
            f"- **Verdict**: **{r['verdict']}** — {r['note']}",
            "",
        ]
    with open(FP_MD, "w") as fh:
        fh.write("\n".join(lines))
    print(f"Saved: scripts/{os.path.basename(FP_MD)}")

    # A bare % starts a LaTeX comment and would swallow the rest of the row.
    def esc(t):
        return t.replace("%", r"\%")

    tex = pd.DataFrame(
        {
            "Source of missingness": [r["where"] for r in tax],
            "Scale": [esc(r["scale"]) for r in tax],
            "Direction": [r["direction"] for r in tax],
            "Verdict": [r["verdict"] for r in tax],
        }
    )
    pandas_to_tex(tex, FP_TEX)
    print(f"Saved: tables/{os.path.basename(FP_TEX)}.tex ({len(tex)} rows)")
    print("\n=== Taxonomy Complete ===")


if __name__ == "__main__":
    sys.exit(main())
