"""07_demo_differences.py
Demographic differences in tracking exposure: the paper's Tables 5 and 6.

Port of 07_demo_differences.R. The R version was the only regression code in an
otherwise Python repo, it carried its own label vocabulary that disagreed with
constants.py, and fixest's significant-digit default produced 2, 3 and 4 decimal
places inside a single row. The port is low-risk because the specification was
already replicated and gated in statsmodels: implications/02_demo_robustness.py
fits the identical model and hard-fails against the published Table 5 values.

Specification, unchanged from the R: OLS of each exposure measure on gender,
race, education and age group, Huber-White (HC1) standard errors, references
male / white / high school or below / under 25.

Cumulative outcomes for ad trackers, third-party cookies and top-organisation
visits are divided by 100 so their columns stay narrow; those columns are headed
"(00s)" because nothing in the R table said so, which invited the reading that
Facebook Pixel exposure (383) exceeds ad-tracker exposure (274) when the truth is
383 against 27,407.

Multiplicity follows the R: raw-p stars in the tex, and a Bonferroni check
against 0.05/12 -- the twelve non-intercept demographic coefficients -- printed
to the console beside the unadjusted verdict, never written into the table.

Input:  data/combined_yg_bl_who_derived_hist_tracking.csv
Output: tables/demo_differences_exposure_rate.tex   (Table 5)
        tables/demo_differences_cum_exposure.tex    (Table 6)
"""

import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "implications"))

import importlib  # noqa: E402

from utilities import pandas_to_tex  # noqa: E402

_demo = None


def _load_demo():
    """implications/02_demo_robustness, whose fit()/stars() we reuse verbatim."""
    global _demo
    if _demo is None:
        saved_path, saved_cfg = list(sys.path), sys.modules.pop("config", None)
        sys.path.insert(0, os.path.join(_HERE, "implications"))
        try:
            _demo = importlib.import_module("02_demo_robustness")
        finally:
            sys.path[:] = saved_path
            sys.modules.pop("config", None)
            if saved_cfg is not None:
                sys.modules["config"] = saved_cfg
    return _demo


REPO = os.path.abspath(os.path.join(_HERE, ".."))
FP_COMBINED = os.path.join(REPO, "data", "combined_yg_bl_who_derived_hist_tracking.csv")
FP_RATE = os.path.join(REPO, "tables", "demo_differences_exposure_rate")
FP_CUM = os.path.join(REPO, "tables", "demo_differences_cum_exposure")

# Cumulative outcomes rescaled by 100 so the columns stay narrow.
RESCALE_100 = ["bl_ddg_join_ads", "bl_third_party_cookies", "top_org_visits"]

MEASURES = [
    "ddg_join_ads",
    "third_party_cookies",
    "fb_pixel",
    "google_analytics",
    "key_logging",
    "session_recording",
    "canvas_fingerprinting",
]

# Column headers. Short forms, from the shared label source in constants.py
# plus the two org-share columns the measure list does not cover.
SHORT = {
    "ddg_join_ads": "Ad",
    "third_party_cookies": "Cookies",
    "fb_pixel": "FB Pixel",
    "google_analytics": "GA",
    "key_logging": "Keylogger",
    "session_recording": "Session rec",
    "canvas_fingerprinting": "Canvas FP",
}

BONFERRONI_FAMILY = 12  # the twelve non-intercept demographic coefficients


def fmt(x, digits):
    """fixest's number format: `digits` significant figures, capped at `digits`
    decimal places.

    Reproduced rather than replaced so the ported tables are byte-identical to
    the R output and the paper does not shift under a language change. It gives
    2.809 -> 2.81 and 0.0350 -> 0.035, which is what the published Table 5
    prints; a plain `:.3f` would render those as 2.809 and 0.035 and change
    every large coefficient in the table.
    """
    if pd.isna(x):
        return ""
    if x == 0:
        return f"{0:.{digits}f}"
    from math import floor, log10

    exp = floor(log10(abs(x)))
    dp = min(max(digits - 1 - exp, 0), digits)
    out = f"{x:.{dp}f}"
    # A tiny negative coefficient formats as "-0.000"; drop the sign.
    return out[1:] if out.startswith("-0.") and float(out) == 0 else out


def cell(row, digits):
    """Coefficient with LaTeX significance superscript, as etable writes it."""
    stars = _load_demo().stars(row.p)
    sup = f"$^{{{stars}}}$" if stars else ""
    return f"{fmt(row.b, digits)}{sup}"


def build(data, yvars, headers, digits, fp, label):
    """One table: coefficients, stars, SEs, and the fitstat block beneath."""
    print(f"\n--- {label} ---")
    coefs, ses, stats = {}, {}, {}
    for y, head in zip(yvars, headers):
        res = _load_demo().fit(y, data)
        coefs[head] = res.apply(lambda r: cell(r, digits), axis=1)
        ses[head] = res.apply(
            lambda r: f"({fmt(r.se, digits)})" if pd.notna(r.se) else "", axis=1
        )
        stats[head] = {
            "Dependent variable mean": fmt(data[y].mean(), digits),
            "R$^2$": f"{res.attrs['r2']:.3f}",
            "Observations": f"{res.attrs['n']:,}",
        }
        print(f"  {head:12s} n={res.attrs['n']:,}  R2={res.attrs['r2']:.3f}")

    # etable puts the standard error on its own unlabelled row beneath each
    # coefficient; interleave to match.
    coef_df, se_df = pd.DataFrame(coefs), pd.DataFrame(ses)
    interleaved = []
    for term in coef_df.index:
        interleaved.append(coef_df.loc[term].rename(term))
        interleaved.append(se_df.loc[term].rename(""))
    body = pd.DataFrame(interleaved)
    out = pd.concat([body, pd.DataFrame(stats)])
    pandas_to_tex(out.reset_index(), fp)
    print(f"  Saved: tables/{os.path.basename(fp)}.tex")
    return {h: _load_demo().fit(y, data) for y, h in zip(yvars, headers)}


def bonferroni(models, label):
    """The R's console-side check: raw p against 0.05/12, shown beside unadjusted."""
    threshold = 0.05 / BONFERRONI_FAMILY
    print(f"\nBonferroni check -- {label}, {BONFERRONI_FAMILY} coefficients per outcome")
    print(f"  threshold {0.05}/{BONFERRONI_FAMILY} = {threshold:.5f}")
    for head, res in models.items():
        surviving = int((res["p"] < threshold).sum())
        unadj = int((res["p"] < 0.05).sum())
        print(
            f"  {head:12s} {unadj:2d}/{BONFERRONI_FAMILY} unadjusted, "
            f"{surviving:2d}/{BONFERRONI_FAMILY} Bonferroni"
        )


def main():
    print("=== Demographic differences in exposure ===")
    data = pd.read_csv(FP_COMBINED)
    if len(data) != 1134:
        raise ValueError(f"expected the 1,134-panelist analytic sample, got {len(data)}")

    data = data.copy()
    for col in RESCALE_100:
        data[col] = data[col] / 100

    cum_heads = [
        f"{SHORT[m]} (00s)" if f"bl_{m}" in RESCALE_100 else SHORT[m] for m in MEASURES
    ] + ["Top share (00s)"]
    rate_heads = [SHORT[m] for m in MEASURES] + ["Top share"]

    # Three significant digits for rates: the behavioural coefficients are
    # ~0.01-0.04, and two digits collapses 0.035 to 0.04 and 0.014 to 0.01.
    rate_models = build(
        data,
        [f"bl_{m}_rate" for m in MEASURES] + ["top_org_share"],
        rate_heads,
        3,
        FP_RATE,
        "Table 5: exposure rate",
    )
    cum_models = build(
        data,
        [f"bl_{m}" for m in MEASURES] + ["top_org_visits"],
        cum_heads,
        2,
        FP_CUM,
        "Table 6: cumulative exposure",
    )

    bonferroni(rate_models, "exposure rate")
    bonferroni(cum_models, "cumulative exposure")
    print("\n=== Demographic Differences Complete ===")


if __name__ == "__main__":
    sys.exit(main())
