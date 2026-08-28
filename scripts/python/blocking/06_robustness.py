"""Does the age result depend on how age and the outcome were coded?

Two choices in the headline specification are load-bearing and were never
examined.

The first is the reference cell. Every age contrast in the paper is against
`<25`, which is the smallest group in the sample at n=93. A conclusion that
rests on 93 people is worth checking against age codings that do not.

The second is the shape of the outcome. Exposure rates are strongly
right-skewed (skew 3.0-4.2 for the behavioral measures) with 8-15% of panelists
at zero, and OLS on a mean is not obviously the right summary of that. OLS stays
primary because it is what the paper reports and comparability matters more than
elegance, but a reach measure -- did this person meet the behavior at all --
matches the underlying question and makes no distributional assumption.

Three age codings of the same intensity outcome, which are comparable with each
other:

  bins        65+ vs <25, the paper's coding                     (primary)
  vs_rest     65+ vs everyone else, no small reference cell
  continuous  birthyr, the variable 18_age_spline.py splines, per decade

and separately, a fourth specification that is *not* comparable with them and is
never averaged into them:

  binary      did this person meet the behavior at all, 65+ vs <25

Reach and intensity are different questions. Blocking can cut how much tracking
someone meets while leaving untouched whether they meet any, and for session
recording and key logging that is exactly what it does. Reported as its own
panel, with a degeneracy flag: where nearly everyone is exposed either way -- ad
trackers reach 99.6% of the panel -- a reach contrast has almost no variation to
work with and its coefficient should not be read.
"""

import os
import sys

import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as blk  # noqa: E402
import config  # noqa: E402

# The paper's controls, minus the age term each alternative replaces.
CONTROLS = (
    "C(gender_lab, Treatment('Male'))"
    " + C(race_lab, Treatment('White'))"
    " + C(educ_lab, Treatment('HS or Below'))"
)

SPECS = ["bins", "vs_rest", "continuous", "binary"]


def age_effect(yvar, data, spec):
    """The 65+-versus-younger effect under one age coding."""
    if spec == "bins":
        model = smf.ols(f"{yvar} ~ {blk.FORMULA_RHS}", data=data).fit(cov_type="HC1")
        return (
            model.params[blk.AGE_TERM],
            model.bse[blk.AGE_TERM],
            model.pvalues[blk.AGE_TERM],
        )

    if spec == "vs_rest":
        d = data.assign(age65=(data["agegroup_lab"] == blk.OLD).astype(int))
        model = smf.ols(f"{yvar} ~ age65 + {CONTROLS}", data=d).fit(cov_type="HC1")
        return model.params["age65"], model.bse["age65"], model.pvalues["age65"]

    if spec == "continuous":
        # birthyr runs backwards against age, so negate to read as "per decade
        # older" and keep the sign comparable with the other specifications.
        model = smf.ols(f"{yvar} ~ birthyr + {CONTROLS}", data=data).fit(cov_type="HC1")
        return (
            -10 * model.params["birthyr"],
            10 * model.bse["birthyr"],
            model.pvalues["birthyr"],
        )

    if spec == "binary":
        d = data[data["agegroup_lab"].isin([blk.OLD, blk.YOUNG])].copy()
        d["any_exposure"] = (d[yvar] > 0).astype(int)
        d["age65"] = (d["agegroup_lab"] == blk.OLD).astype(int)
        model = smf.ols(f"any_exposure ~ age65 + {CONTROLS}", data=d).fit(cov_type="HC1")
        return model.params["age65"], model.bse["age65"], model.pvalues["age65"]

    raise ValueError(spec)


def main():
    user = blk.load_user()
    tier = blk.HEADLINE_TIER
    print(f"Panelists: {len(user):,}")
    print(f"Age cells: {user['agegroup_lab'].value_counts().to_dict()}\n")

    rows = []
    for measure in blk.HEADLINE_MEASURES:
        y_pre = f"{blk.base_col(measure)}_rate"
        y_post = f"bl_{measure}_resid_{tier}_rate"
        for spec in SPECS:
            b_pre, se_pre, p_pre = age_effect(y_pre, user, spec)
            b_post, se_post, p_post = age_effect(y_post, user, spec)
            rows.append(
                {
                    "measure": blk.BASE_LABELS[measure],
                    "measure_key": measure,
                    "spec": spec,
                    "unblocked": b_pre,
                    "unblocked_se": se_pre,
                    "unblocked_p": p_pre,
                    "residual": b_post,
                    "residual_se": se_post,
                    "residual_p": p_post,
                    "pct_of_unblocked": 100 * b_post / b_pre if b_pre else float("nan"),
                    "reach_unblocked": (user[y_pre] > 0).mean(),
                    "reach_residual": (user[y_post] > 0).mean(),
                }
            )

    out = pd.DataFrame(rows)
    rate_specs = [s for s in SPECS if s != "binary"]

    print("Panel 1 -- intensity (trackers per visit), three age codings")
    print("Residual age effect as a share of the unblocked one. A tight range")
    print("across codings means the reading does not hinge on the <25 cell.\n")
    for measure in blk.HEADLINE_MEASURES:
        sub = out[(out["measure_key"] == measure) & (out["spec"].isin(rate_specs))]
        print(f"  {blk.MEASURE_LABELS[measure]}")
        for _, r in sub.iterrows():
            print(
                f"    {r['spec']:11s} unblocked {r['unblocked']:8.4f}"
                f"{blk.stars(r['unblocked_p']):<3s}  residual {r['residual']:8.4f}"
                f"{blk.stars(r['residual_p']):<3s}  "
                f"({r['pct_of_unblocked']:6.1f}% of unblocked)"
            )
        span = sub["pct_of_unblocked"]
        print(f"    -> range across codings: {span.min():.0f}% to {span.max():.0f}%\n")

    print("\nPanel 2 -- reach (met the behavior at all), a different question")
    print("Degenerate where almost everyone is exposed regardless.\n")
    for measure in blk.HEADLINE_MEASURES:
        r = out[(out["measure_key"] == measure) & (out["spec"] == "binary")].iloc[0]
        degenerate = min(r["reach_unblocked"], r["reach_residual"]) > 0.95
        note = "  (degenerate: reach is near-universal either way)" if degenerate else ""
        print(
            f"  {blk.MEASURE_LABELS[measure]:24s} "
            f"reach {r['reach_unblocked']:.1%} -> {r['reach_residual']:.1%}   "
            f"gap {r['unblocked']:+.3f}{blk.stars(r['unblocked_p'])} -> "
            f"{r['residual']:+.3f}{blk.stars(r['residual_p'])}{note}"
        )

    out.to_csv(
        os.path.join(config.BLOCKING_DATA_DIR, "robustness_age_coding.csv"), index=False
    )

    tex = out.pivot(index="measure", columns="spec", values="pct_of_unblocked")
    tex = tex[SPECS].reset_index()
    tex.columns = ["Measure", "65+ vs <25", "65+ vs rest", "Per decade", "Any exposure"]
    for c in tex.columns[1:]:
        tex[c] = tex[c].map(lambda x: f"{x:,.0f}")
    blk.pandas_to_tex(tex, blk.table_path("robustness_age_coding.tex"))
    print("\nWrote tables/robustness_age_coding.tex")
    print("(cells are the residual age effect as a percentage of the unblocked one)")


if __name__ == "__main__":
    sys.exit(main())
