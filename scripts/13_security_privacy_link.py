"""Do the same people bear both the privacy risk and the security risk?

The panel that produced the tracking measures also produced a security measure:
data/yg/ind_data.csv carries, for the same 1,134 panelists under the same
caseid, counts of the domains they visited that antivirus vendors flagged as
malicious or suspicious (see the bad_domains project). Nothing had to be built
to join them.

That makes one question cheap to ask and worth recording: are heavy tracking
exposure and heavy security exposure borne by the same individuals, or do they
fall on different people? A positive association would mean a subset of the
population absorbs both kinds of online risk at once -- which is a different
claim from either literature's, and one neither can make alone.

This is a pointer, not a finding. Both measures are counts driven partly by how
much a person browsed, so the raw correlation is largely a volume artifact; the
rate-based and browsing-adjusted versions below are the ones to read. A serious
treatment is its own paper. The point here is that the artifact supports it.
"""

import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocking"))

import common as blk  # noqa: E402
import config as blk_config  # noqa: E402

FP_IND = os.path.join(blk_config.DATA_DIR, "yg", "ind_data.csv")

MEASURES = [
    (m, blk.MEASURE_LABELS[m])
    for m in blk.HEADLINE_MEASURES
    if m != "third_party_cookies"
]

TIER = blk.HEADLINE_TIER


def main():
    user = pd.read_csv(blk_config.FP_USER_RESIDUAL)
    sec = pd.read_csv(
        FP_IND, usecols=["caseid", "malicious", "suspicious", "harmless", "visits"]
    )

    df = user.merge(sec, on="caseid", how="inner", validate="1:1").copy()
    print(
        f"Panelists on both sides: {len(df):,} "
        f"(privacy {len(user):,}, security {len(sec):,})"
    )

    df["bad_domains"] = df["malicious"] + df["suspicious"]
    df["bad_rate"] = df["bad_domains"] / df["tt_domains"]
    print(
        f"\nFlagged domains per panelist: mean {df['bad_domains'].mean():.1f}, "
        f"median {df['bad_domains'].median():.0f}, max {df['bad_domains'].max():.0f}"
    )
    print(f"Share of a panelist's domains flagged: mean {df['bad_rate'].mean():.2%}")

    rows = []
    for measure, label in MEASURES:
        cum, rate = f"bl_{measure}", f"bl_{measure}_rate"
        resid_rate = f"bl_{measure}_resid_{TIER}_rate"

        # Both counts scale with how much someone browsed, so the count-on-count
        # correlation mostly measures browsing volume. Rates divide it out.
        rows.append(
            {
                "measure": label,
                "r_counts": df[cum].corr(df["bad_domains"]),
                "r_rates": df[rate].corr(df["bad_rate"]),
                "r_rates_resid": df[resid_rate].corr(df["bad_rate"]),
                "rho_rates": df[rate].corr(df["bad_rate"], method="spearman"),
            }
        )
    corr = pd.DataFrame(rows)

    print("\nPerson-level association between tracking and security exposure")
    print(
        "(counts = cumulative, inflated by browsing volume; rates = per visit "
        "vs per domain)\n"
    )
    print(corr.to_string(index=False, float_format="%.3f"))

    # Does security exposure still predict tracking exposure once demographics
    # and browsing volume are held fixed?
    print("\n\nFlagged-domain rate as a predictor of tracking exposure")
    print("(OLS, HC1, Table 5 demographics plus log browsing volume)\n")
    df["log_visits"] = np.log(df["tt_visits"].clip(lower=1))
    adj = []
    for measure, label in MEASURES:
        model = smf.ols(
            f"bl_{measure}_rate ~ bad_rate + log_visits + {blk.FORMULA_RHS}",
            data=df,
        ).fit(cov_type="HC1")
        adj.append(
            {
                "measure": label,
                "coef": model.params["bad_rate"],
                "se": model.bse["bad_rate"],
                "p": model.pvalues["bad_rate"],
            }
        )
        print(
            f"  {label:24s} {model.params['bad_rate']:9.3f} "
            f"(se {model.bse['bad_rate']:.3f})  p={model.pvalues['bad_rate']:.3f}"
        )
    adj = pd.DataFrame(adj)

    # Do the two risks land on the same demographic groups?
    print("\n\nWho bears each risk (mean by age group)\n")
    by_age = df.groupby("agegroup_lab").agg(
        n=("caseid", "size"),
        ad_trackers=("bl_ddg_join_ads_rate", "mean"),
        keylogging=("bl_key_logging_rate", "mean"),
        bad_domain_rate=("bad_rate", "mean"),
    )
    print(by_age.to_string(float_format="%.4f"))

    out = corr.merge(adj, on="measure", suffixes=("", "_adj"))
    out.to_csv(
        os.path.join(blk_config.BLOCKING_DATA_DIR, "security_privacy_link.csv"),
        index=False,
    )

    tex = pd.DataFrame(
        {
            "Measure": out["measure"],
            "$r$ (counts)": out["r_counts"].map(lambda x: f"{x:,.3f}"),
            "$r$ (rates)": out["r_rates"].map(lambda x: f"{x:,.3f}"),
            "$\\rho$ (rates)": out["rho_rates"].map(lambda x: f"{x:,.3f}"),
            "Adjusted coef.": out.apply(
                lambda r: f"{r['coef']:,.3f} ({r['se']:,.3f})", axis=1
            ),
        }
    )
    blk.pandas_to_tex(tex, blk.table_path("security_privacy_link.tex"))
    print("\nWrote tables/security_privacy_link.tex")


if __name__ == "__main__":
    sys.exit(main())
