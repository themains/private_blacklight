"""21_robustness_denominator.py
Is the age gap an artifact of dividing by a small number of visits?

The paper's headline estimand is a mean of ratios: each panelist's tracker
encounters divided by their own visits, then averaged with equal weight across
people. That construction has a known weak point. A panelist with two visits
contributes a rate estimated from two visits, and it enters the average with the
same weight as a rate estimated from forty thousand. Thirteen panelists have
fewer than ten visits and seventy-seven have fewer than a hundred, so the
question is whether the age result rests on them.

It does not, and the direction is worth stating plainly: every restriction that
removes the noisy denominators makes the gap *larger*, and so does weighting each
panelist by their visits (which changes the estimand from the average person to
the average visit). The published number is the smallest of the six.

That is the useful form of a robustness check. It does not merely fail to
overturn the result; it shows the published specification is the conservative
member of the family, so a reader who prefers any of the alternatives would
conclude something stronger.

Input:  data/combined_yg_bl_who_derived_hist_tracking.csv
Output: tables/robustness_denominator.tex   (ms appendix, sm:robustness)
"""

import os
import sys

import pandas as pd
import statsmodels.formula.api as smf

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "implications"))

from utilities import pandas_to_tex  # noqa: E402

REPO = os.path.abspath(os.path.join(_HERE, ".."))
FP_COMBINED = os.path.join(REPO, "data", "combined_yg_bl_who_derived_hist_tracking.csv")
FP_TABLE = os.path.join(REPO, "tables", "robustness_denominator")

OUTCOMES = [
    ("bl_ddg_join_ads_rate", "Ad trackers"),
    ("bl_third_party_cookies_rate", "Third-party cookies"),
]
# Thresholds chosen to bracket where a per-visit rate stops being noise: the
# minimum in the sample is 2 visits, and 100 removes the bottom 6.8%.
THRESHOLDS = [10, 50, 100, 250]


def _config():
    """implications/config.py -- the same specification as Tables 5 and 6."""
    import importlib

    saved = sys.modules.pop("config", None)
    try:
        return importlib.import_module("config")
    finally:
        sys.modules.pop("config", None)
        if saved is not None:
            sys.modules["config"] = saved


config = _config()
AGE_TERM = "C(agegroup_lab, Treatment('<25'))[T.65+]"


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def age_gap(yvar, data, weights=None):
    if weights is None:
        model = smf.ols(f"{yvar} ~ {config.FORMULA_RHS}", data)
    else:
        model = smf.wls(f"{yvar} ~ {config.FORMULA_RHS}", data, weights=data[weights])
    fitted = model.fit(cov_type="HC1")
    return fitted.params[AGE_TERM], fitted.bse[AGE_TERM], fitted.pvalues[AGE_TERM]


def main():
    print("=== Robustness of the age gap to the rate denominator ===")
    data = pd.read_csv(FP_COMBINED)
    if len(data) != 1134:
        raise ValueError(f"expected the 1,134-panelist analytic sample, got {len(data)}")

    print(
        f"panelists with fewer than 10 visits: {int((data.tt_visits < 10).sum())}; "
        f"fewer than 100: {int((data.tt_visits < 100).sum())}; "
        f"minimum {int(data.tt_visits.min())}"
    )

    specs = [("Published (all panelists)", data, None)]
    specs += [
        (f"Drop $<{k}$ visits", data[data.tt_visits >= k], None) for k in THRESHOLDS
    ]
    specs += [("Visit-weighted", data, "tt_visits")]

    rows, published = [], {}
    for label, sub, weights in specs:
        row = {"Specification": label, "$n$": f"{len(sub):,}"}
        for yvar, name in OUTCOMES:
            b, se, p = age_gap(yvar, sub, weights)
            row[name] = f"{b:.3f}{stars(p)}"
            row[f"{name} SE"] = f"({se:.3f})"
            if label.startswith("Published"):
                published[name] = b
            elif b < published[name]:
                print(
                    f"  note: {label} gives a SMALLER {name} gap "
                    f"({b:.3f} < {published[name]:.3f})"
                )
        rows.append(row)
        print(
            f"  {label:26s} n={len(sub):5,}  "
            + "  ".join(f"{name} {row[name]:>10s}" for _, name in OUTCOMES)
        )

    frame = pd.DataFrame(rows)
    pandas_to_tex(frame, FP_TABLE)
    print(f"\nSaved: tables/{os.path.basename(FP_TABLE)}.tex")

    smallest = min(
        (float(r[name].rstrip("*")), r["Specification"])
        for r in rows
        for _, name in OUTCOMES
        if name == OUTCOMES[0][1]
    )
    if not smallest[1].startswith("Published"):
        raise ValueError(
            f"the published specification is no longer the most conservative on "
            f"{OUTCOMES[0][1]}: {smallest[1]} gives {smallest[0]:.3f}. The claim in "
            "the manuscript that the published estimate is the floor must be revised."
        )
    print("gate: the published specification remains the smallest of the six.")
    print("=== Robustness Complete ===")


if __name__ == "__main__":
    sys.exit(main())
