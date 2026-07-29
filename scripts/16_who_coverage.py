"""16_who_coverage.py
Recompute the WhoTracksMe rates on the visits WhoTracksMe actually covers.

WhoTracksMe profiles 4,261 of the 64,074 panel domains (6.7%), covering 71% of
visits. `02_combine_yg_blacklight.ipynb` dropped its all-NaN rows and then let a
left join fill the rest with zero, so 29% of every panelist's browsing counted
as zero trackers rather than as unknown.

Absence is not zero, on two independent grounds:

  - WhoTracksMe never reports a value below 1.02 trackers per page load. Across
    all 4,261 covered domains there is not a single zero, so its data-generating
    process cannot produce "measured none".
  - Blacklight scanned the same domains. Visit-weighted, the domains WTM lacks
    carry 5.42 ad trackers and 8.02 third-party cookies per visit, against
    6.81 / 7.60 on the ones it covers. Cookies are higher on the missing set.
    They are ordinary tracked sites; WTM simply has no telemetry for lower
    traffic domains.

The fix is in `02_combine_yg_blacklight.ipynb`, but that notebook cannot run
here: it needs all three RealityMine visit files and `realityMine_web` is
restricted on Dataverse. This script applies the same correction to the derived
analytic file, which is what every downstream script actually reads, and it
reproduces the published bl_* columns exactly first so the recomputation is
known to be faithful before anything is rewritten.

Input:  data/yg/yg_ind_domain.csv
        data/whotracksme_domain.csv
        data/combined_yg_bl_who_derived_hist_tracking.csv
Output: data/combined_yg_bl_who_derived_hist_tracking.csv  (who_* rates, who_coverage)
        tables/individual_who_exposure_rate_summary.tex
        tables/individual_who_cumulative_exposure_summary.tex
"""

import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from utilities import pandas_to_tex  # noqa: E402

REPO = os.path.abspath(os.path.join(_HERE, ".."))
FP_VISITS = os.path.join(REPO, "data", "yg", "yg_ind_domain.csv")
FP_WHO = os.path.join(REPO, "data", "whotracksme_domain.csv")
FP_COMBINED = os.path.join(REPO, "data", "combined_yg_bl_who_derived_hist_tracking.csv")
FP_RATE_TABLE = os.path.join(REPO, "tables", "individual_who_exposure_rate_summary")
FP_CUM_TABLE = os.path.join(REPO, "tables", "individual_who_cumulative_exposure_summary")

COVERAGE_KEY = "Trackers Per Page Load"

WHO_LABELS = {
    "who_trackers_per_page_load": "Trackers/Page Load",
    "who_tracking_requests_per_page_load": "Tracking Requests/Page Load",
    "who_trackers_requests_all_requests": "% of requests to trackers",
    "who_data_saved": "Data Saved",
    "who_advertising": "Advertising",
    "who_site_analytics": "Site Analytics",
    "who_social_media": "Social Media",
    "who_customer_interaction": "Customer Interaction",
    "who_audio_video_player": "Audio/Video Player",
    "who_consent_management": "Consent Management",
    "who_hosting": "Hosting Services",
    "who_misc": "Miscellaneous",
    "who_utilities": "Utilities",
    "who_adult_advertising": "Adult Advertising",
}


def main():
    print("=== WhoTracksMe coverage-conditional rates ===")

    visits = pd.read_csv(FP_VISITS)
    who = pd.read_csv(FP_WHO)
    comb = pd.read_csv(FP_COMBINED)

    # Drop anything a previous run added, so re-running recomputes from the
    # published columns instead of merging onto its own output and producing
    # suffixed duplicates.
    DERIVED = ["who_visits", "who_coverage"]
    comb = comb.drop(columns=[c for c in DERIVED if c in comb.columns])

    covered = set(who.loc[who[COVERAGE_KEY].notna(), "domain_name"])
    print(
        f"WhoTracksMe covers {len(covered):,} of {who['domain_name'].nunique():,} "
        f"domains ({len(covered) / who['domain_name'].nunique():.1%})"
    )

    v = visits.assign(who_covered=visits["private_domain"].isin(covered))
    per_person = v.groupby("caseid").agg(
        tt_visits=("visits", "sum"),
        who_visits=("visits", lambda s: s[v.loc[s.index, "who_covered"]].sum()),
    )
    per_person["who_coverage"] = per_person["who_visits"] / per_person["tt_visits"]

    covered_share = per_person["who_visits"].sum() / per_person["tt_visits"].sum()
    print(f"visit mass covered: {covered_share:.1%}")
    print(
        "per-person who_coverage: "
        f"mean {per_person['who_coverage'].mean():.3f}, "
        f"min {per_person['who_coverage'].min():.3f}, "
        f"max {per_person['who_coverage'].max():.3f}, "
        f"{int((per_person['who_coverage'] < 0.5).sum())} below 0.5"
    )

    # Gate: the rebuilt denominator must reproduce the published tt_visits, or
    # the recomputation is not operating on the same visit set the paper used.
    chk = comb[["caseid", "tt_visits"]].merge(
        per_person["tt_visits"].rename("rebuilt"), on="caseid", validate="1:1"
    )
    worst = (chk["tt_visits"] - chk["rebuilt"]).abs().max()
    if worst > 1e-6:
        raise ValueError(
            f"rebuilt tt_visits differs from the published file by {worst:,.4f}; "
            "the visit set does not match and the who_* rates would not either"
        )
    print(f"gate: rebuilt tt_visits matches published exactly ({len(chk):,} panelists)")

    who_cols = [
        c
        for c in comb.columns
        if c.startswith("who_")
        and c not in DERIVED
        and not c.endswith(("_rate", "_al1", "_al3", "_al5", "_al10"))
    ]
    before = {c: comb[f"{c}_rate"].mean() for c in who_cols if f"{c}_rate" in comb}

    out = comb.merge(
        per_person[["who_visits", "who_coverage"]],
        on="caseid",
        how="left",
        validate="1:1",
    )
    denom = out["who_visits"].replace(0, pd.NA)
    for c in who_cols:
        if f"{c}_rate" in out.columns:
            out[f"{c}_rate"] = out[c] / denom

    print("\nMean per-user rate, all-visits denominator -> WTM-covered denominator\n")
    for c in who_cols:
        if f"{c}_rate" not in out.columns:
            continue
        after = out[f"{c}_rate"].mean()
        label = WHO_LABELS.get(c, c)
        print(
            f"  {label:32s} {before[c]:8.3f} -> {after:8.3f}  "
            f"({after / before[c]:.2f}x)"
            if before[c]
            else f"  {label:32s} n/a"
        )

    out.to_csv(FP_COMBINED, index=False)
    print(f"\nSaved: {os.path.relpath(FP_COMBINED, REPO)}")

    # Regenerate the two summary tables. Neither is referenced by
    # ms/blacklight.tex -- the manuscript cites the WhoTracksMe paper but uses
    # no WhoTracksMe measure -- so these are repo artifacts, not paper tables.
    for cols, fp, kind in [
        (
            [f"{c}_rate" for c in who_cols if f"{c}_rate" in out.columns],
            FP_RATE_TABLE,
            "rate",
        ),
        (who_cols, FP_CUM_TABLE, "cumulative"),
    ]:
        summ = (
            out[cols]
            .describe(percentiles=[0.25, 0.5, 0.75])
            .T.reset_index(names="var")
            .drop(columns="count")
            .assign(var=lambda d: d["var"].str.replace("_rate", "", regex=False))
            .assign(var=lambda d: d["var"].map(lambda x: WHO_LABELS.get(x, x)))
        )
        num = summ.select_dtypes("number").columns
        summ[num] = summ[num].map(lambda x: f"{x:,.2f}")
        pandas_to_tex(summ, fp)
        print(f"Saved: tables/{os.path.basename(fp)}.tex ({kind}, {len(summ)} rows)")

    print("\n=== WhoTracksMe Coverage Complete ===")


if __name__ == "__main__":
    sys.exit(main())
