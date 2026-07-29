"""Do the results depend on treating walled gardens as tracker-free?

Blacklight loads one anonymous, logged-out page per domain. For a site whose
tracking happens behind a login, that returns nothing, and the domain enters
every estimate as a genuine zero. 8,097 of the 34,078 successful scans (23.8%)
are zero on all seven measures, and they carry 19.5% of all panel visits --
facebook.com alone is 7.2%, then amazon.com, instagram.com, paypal.com.

The paper's validity work bounds the *unscanned* 23.6% of visits. Nothing bounds
this stratum, because a successful scan that found nothing is trusted as a true
zero.

Bounding it properly would need the domains classified -- walled garden, or
redirect hop that is not a page view at all, or genuinely untracked. A quick
proxy using DuckDuckGo Tracker Radar membership does not work, because Tracker
Radar profiles facebook and amazon precisely for being third-party trackers
elsewhere, so it cannot separate a real page view from a hop.

So this asks the narrower question that does not need the classification: does
anything we conclude depend on the zero? Three specifications --

  published   all-zero domains contribute zero, in numerator and denominator
  excluded    their visits leave both numerator and denominator, so rates
              describe only domains where Blacklight could see something
  imputed     they are assigned the mean of the domains that did show tracking,
              the most generous reading, treating a walled garden as tracking
              like an average measured site

-- reported side by side for the exposure levels, the 65+ coefficient, and the
residual share under the strongest blocklist tier. This says nothing about what
facebook.com actually does. It says whether the answer turns on assuming it does
nothing.
"""

import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as blk  # noqa: E402
import config  # noqa: E402

SPECS = ["published", "excluded", "imputed"]
TIER = blk.HEADLINE_TIER


def load_domains():
    """Per-domain published and residual measures, flagged for the all-zero set."""
    resid = pd.read_csv(config.FP_DOMAIN_RESIDUAL)
    resid["private_domain"] = resid["filename"].str.replace("_", ".", regex=False)
    resid["all_zero"] = resid[config.MEASURES].sum(axis=1).eq(0)
    return resid


def person_rates(visits, domains, spec):
    """Visit-weighted per-person rates under one treatment of the all-zero set."""
    # third_party_cookie_domains rides along because it is the baseline the
    # cookie residual is actually comparable to -- see blk.base_col.
    extra = ["third_party_cookie_domains"]
    cols = (
        [f"bl_{m}" for m in config.MEASURES]
        + [f"bl_{m}_resid_{TIER}" for m in config.MEASURES]
        + [f"bl_{m}" for m in extra]
    )
    src = (
        [m for m in config.MEASURES]
        + [f"{m}_resid_{TIER}" for m in config.MEASURES]
        + extra
    )

    d = visits.merge(
        domains[["private_domain", "all_zero"] + src],
        on="private_domain",
        how="left",
        validate="m:1",
    )
    # astype(bool) matters: after a left merge the column is object dtype, and
    # `~` on object dtype is integer bitwise NOT (~True == -2), not logical
    # negation, which turns the mask into a list of -1/-2 labels.
    az = d["all_zero"].fillna(False).astype(bool)

    if spec == "excluded":
        d = d.loc[~az].copy()
    elif spec == "imputed":
        # Mean over domains that did show tracking, so the fill is "an average
        # measured site" rather than an average including the zeros themselves.
        nonzero = domains.loc[~domains["all_zero"]]
        for s in src:
            d.loc[az, s] = nonzero[s].mean()

    num = pd.DataFrame(
        {c: d[s].fillna(0) * d["visits"] for c, s in zip(cols, src)}
    ).assign(caseid=d["caseid"].to_numpy())
    num = num.groupby("caseid").sum()
    den = d.groupby("caseid")["visits"].sum()
    return num.div(den, axis=0).reset_index()


def main():
    visits = pd.read_csv(config.FP_YG_IND_DOMAIN)
    domains = load_domains()
    user = blk.load_user()
    demo = user[["caseid", "gender_lab", "race_lab", "educ_lab", "agegroup_lab"]]

    az = domains["all_zero"]
    v = visits.merge(
        domains[["private_domain", "all_zero"]], on="private_domain", how="left"
    )
    share = (
        v.loc[v["all_zero"].fillna(False).astype(bool), "visits"].sum()
        / v["visits"].sum()
    )
    print(
        f"All-zero scans: {int(az.sum()):,} of {len(domains):,} domains "
        f"({az.mean():.1%}), carrying {share:.1%} of panel visits\n"
    )

    out = {}
    for spec in SPECS:
        r = person_rates(visits, domains, spec).merge(demo, on="caseid", how="inner")
        out[spec] = r
        print(f"  {spec:10s} n = {len(r):,} panelists")

    rows = []
    for measure in blk.HEADLINE_MEASURES:
        row = {"measure": blk.BASE_LABELS[measure]}
        for spec in SPECS:
            d = out[spec]
            y, y_r = f"bl_{measure}", f"bl_{measure}_resid_{TIER}"
            fit = smf.ols(f"{y} ~ {blk.FORMULA_RHS}", data=d).fit(cov_type="HC1")
            row[f"{spec}_mean"] = d[y].mean()
            row[f"{spec}_coef"] = fit.params[blk.AGE_TERM]
            row[f"{spec}_p"] = fit.pvalues[blk.AGE_TERM]
            # The residual share needs the baseline the residual is comparable
            # to, which for cookies is the domain count, not the cookie count.
            base = d[blk.base_col(measure)].mean()
            row[f"{spec}_resid_share"] = (
                100 * d[y_r].mean() / base if base else float("nan")
            )
        rows.append(row)
    res = pd.DataFrame(rows)

    print("\nExposure per visit\n")
    print(f"{'measure':24s}" + "".join(f"{s:>14s}" for s in SPECS))
    for _, r in res.iterrows():
        print(f"{r['measure']:24s}" + "".join(f"{r[f'{s}_mean']:14.4f}" for s in SPECS))

    print("\n65+ coefficient (HC1)\n")
    print(f"{'measure':24s}" + "".join(f"{s:>14s}" for s in SPECS))
    for _, r in res.iterrows():
        cells = "".join(
            f"{r[f'{s}_coef']:11.4f}{blk.stars(r[f'{s}_p']):<3s}" for s in SPECS
        )
        print(f"{r['measure']:24s}{cells}")

    print(f"\nResidual share under tier {TIER} (% of unblocked exposure surviving)\n")
    print(f"{'measure':24s}" + "".join(f"{s:>14s}" for s in SPECS))
    for _, r in res.iterrows():
        print(
            f"{r['measure']:24s}"
            + "".join(f"{r[f'{s}_resid_share']:13.1f}%" for s in SPECS)
        )

    # The conclusions at issue are the sign and significance of the age gap and
    # the size of the residual share. Both should hold across all three.
    print("\nDoes any conclusion turn on the zero?\n")
    for _, r in res.iterrows():
        signs = {np.sign(r[f"{s}_coef"]) for s in SPECS}
        sig = {r[f"{s}_p"] < 0.05 for s in SPECS}
        spread = max(r[f"{s}_resid_share"] for s in SPECS) - min(
            r[f"{s}_resid_share"] for s in SPECS
        )
        verdict = (
            "stable" if len(signs) == 1 and len(sig) == 1 else "CHANGES ACROSS SPECS"
        )
        print(
            f"  {r['measure']:24s} age gap {verdict:22s} "
            f"residual share spans {spread:5.1f} pp"
        )

    res.to_csv(
        os.path.join(config.BLOCKING_DATA_DIR, "allzero_sensitivity.csv"), index=False
    )
    tex = pd.DataFrame(
        {
            "Measure": res["measure"],
            "Published": res.apply(
                lambda r: f"{r['published_mean']:,.3f} ({r['published_coef']:+,.3f}"
                f"{blk.stars(r['published_p'])})",
                axis=1,
            ),
            "Excluded": res.apply(
                lambda r: f"{r['excluded_mean']:,.3f} ({r['excluded_coef']:+,.3f}"
                f"{blk.stars(r['excluded_p'])})",
                axis=1,
            ),
            "Imputed": res.apply(
                lambda r: f"{r['imputed_mean']:,.3f} ({r['imputed_coef']:+,.3f}"
                f"{blk.stars(r['imputed_p'])})",
                axis=1,
            ),
        }
    )
    blk.pandas_to_tex(tex, blk.table_path("allzero_sensitivity.tex"))
    print("\nWrote tables/allzero_sensitivity.tex")
    print("(cells are mean exposure per visit, with the 65+ coefficient in parentheses)")


if __name__ == "__main__":
    sys.exit(main())
