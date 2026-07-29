"""18_age_spline.py
Is the age gradient in exposure linear? A flexible check on birth year.

Replaces GAMs_age.R, which fit mgcv penalized smooths and drew them with
gratia. That script had not run since April 2025 and could not run now: its
outcome list ends in top_org_share, which is absent from its own label map, so
the loop died on a subscript error at the eighth figure; it also depended on
`data`, `yvars_rate` and `savefig` existing in the session from two other
scripts, and gratia is no longer installed.

mgcv's REML smooth has no equivalent in Python -- statsmodels' GLMGam cannot
select a penalty for a Gaussian response here -- so this is a different
estimator, not a port: a natural cubic regression spline in birth year with the
same covariates, fit by OLS with the HC1 errors the rest of the paper uses.

That change makes an ambiguity in the R output visible. mgcv's smooth p-value
tests the whole smooth, so an EDF near 1 with p < .001 -- which is what canvas
fingerprinting and Google Analytics produced -- means a strong *linear* birth
year effect, not a nonlinear one, even though the R script collected those
columns into a table called `nonlinear_summary`. The two questions are
separated here: a joint test of any birth-year effect, and a test of the
nonlinear basis alone after the linear term is projected out.

Against the mgcv reference the joint test agrees on seven of eight outcomes.
The exception is Google Analytics, and the cause is the standard error rather
than the spline: its per-visit rate is severely heteroskedastic (mean 0.010,
maximum 0.99), and the same joint test gives p = .287 classically against
p = .001 under HC1. mgcv reports classical errors; every regression in the
paper reports HC1.

Not referenced by the manuscript. This is a diagnostic for the age results in
Section 4, whose published evidence on functional form is
figures/lowess_age_bl.pdf.

Input:  data/combined_yg_bl_who_derived_hist_tracking.csv
Output: figures/age_spline_<outcome>.{pdf,png}   (8 figures, repo artifacts)
        tables/age_spline_tests.tex
"""

import os
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import patsy  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import constants  # noqa: E402
from utilities import pandas_to_tex  # noqa: E402

REPO = os.path.abspath(os.path.join(_HERE, ".."))
FP_COMBINED = os.path.join(REPO, "data", "combined_yg_bl_who_derived_hist_tracking.csv")
FIGURES = os.path.join(REPO, "figures")
FP_TESTS = os.path.join(REPO, "tables", "age_spline_tests")

MEASURES = [
    "ddg_join_ads",
    "third_party_cookies",
    "fb_pixel",
    "google_analytics",
    "key_logging",
    "session_recording",
    "canvas_fingerprinting",
]
EXTRA = ("top_org_share", "Top organization share")

# Five basis functions: one linear direction plus three nonlinear ones. Enough
# curvature to show a bend without spending degrees of freedom on wiggle the
# 1,134 panelists cannot identify.
SPLINE_DF = 5
COVARIATES = "gender_lab + race_lab + educ_lab"

# mgcv 1.9.4, gam(y ~ s(birthyr) + gender_lab + race_lab + educ_lab,
# method="REML"), for reference. Printed beside the spline result so the change
# of estimator is visible rather than silently absorbed.
MGCV_REFERENCE = {
    "bl_ddg_join_ads_rate": (2.112, 0.0),
    "bl_third_party_cookies_rate": (1.784, 0.0),
    "bl_fb_pixel_rate": (1.001, 0.20033),
    "bl_google_analytics_rate": (1.005, 0.083412),
    "bl_key_logging_rate": (1.858, 1.6339e-06),
    "bl_session_recording_rate": (2.094, 0.015509),
    "bl_canvas_fingerprinting_rate": (1.001, 0.00019812),
    "top_org_share": (1.749, 0.00038874),
}

C_FIT = constants.palette7[0]
C_BAND = constants.palette7[6]
C_RUG = constants.palette7[4]
FIGSIZE = (5.2, 3.4)
DPI = 300


def nonlinear_basis(data):
    """Spline basis split into its linear direction and the rest.

    A natural cubic basis in birth year already contains a linear trend, so
    testing the basis columns jointly cannot separate "there is an age effect"
    from "the age effect bends". Residualising the basis on [1, birthyr] and
    taking an orthonormal spanning set leaves columns that are exactly
    orthogonal to the linear term, so the two questions get their own tests.
    """
    basis = patsy.dmatrix(
        f"cr(birthyr, df={SPLINE_DF}) - 1", data, return_type="dataframe"
    )
    linear = np.column_stack([np.ones(len(data)), data["birthyr"].to_numpy()])
    residual = basis.to_numpy() - linear @ np.linalg.pinv(linear) @ basis.to_numpy()
    left = np.linalg.svd(residual, full_matrices=False)[0][:, : SPLINE_DF - 2]

    worst = np.abs(linear.T @ left).max() / len(data)
    if worst > 1e-9:
        raise ValueError(
            f"nonlinear basis is not orthogonal to the linear term (max {worst:.2e}); "
            "the nonlinearity test would absorb part of the linear age gradient"
        )
    cols = [f"nl{i}" for i in range(left.shape[1])]
    return pd.DataFrame(left, columns=cols, index=data.index), cols


def test_one(data, yvar, cols):
    """Joint birth-year test, nonlinearity test, and the fitted age curve."""
    terms = " + ".join(cols)
    model = smf.ols(f"{yvar} ~ birthyr + {terms} + {COVARIATES}", data=data).fit(
        cov_type="HC1"
    )
    joint = model.f_test(" = 0, ".join(["birthyr"] + cols) + " = 0")
    nonlin = model.f_test(" = 0, ".join(cols) + " = 0")

    # Partial effect of birth year, as a deviation from the sample average age
    # effect. Centring the design rather than the fitted values is what makes
    # the band a band for the plotted quantity: on the raw design the interval
    # inherits the level uncertainty of the linear term, whose coefficient is
    # multiplied by a birth year near 1970, and swamps the curve by an order of
    # magnitude.
    age_terms = ["birthyr"] + cols
    beta = model.params[age_terms].to_numpy()
    design = data[age_terms].to_numpy()
    contrast = design - design.mean(axis=0)
    cov = model.cov_params().loc[age_terms, age_terms].to_numpy()
    curve = (
        pd.DataFrame(
            {
                "birthyr": data["birthyr"].to_numpy(),
                "fit": contrast @ beta,
                "se": np.sqrt(np.einsum("ij,jk,ik->i", contrast, cov, contrast)),
            }
        )
        .groupby("birthyr", as_index=False)
        .mean()
    )

    return dict(
        yvar=yvar,
        p_joint=float(joint.pvalue),
        p_nonlinear=float(nonlin.pvalue),
        f_joint=float(np.asarray(joint.fvalue).ravel()[0]),
        n=int(model.nobs),
        curve=curve,
    )


def draw(result, label):
    curve = result["curve"]
    fig, ax = plt.subplots(figsize=FIGSIZE, constrained_layout=True)
    ax.fill_between(
        curve["birthyr"],
        curve["fit"] - 1.96 * curve["se"],
        curve["fit"] + 1.96 * curve["se"],
        color=C_BAND,
        alpha=0.7,
        linewidth=0,
    )
    ax.plot(curve["birthyr"], curve["fit"], color=C_FIT, linewidth=1.4)
    ax.axhline(0, color=C_RUG, linewidth=0.6, linestyle="--")
    ax.set_xlabel("Birth year", fontsize=9)
    ax.set_ylabel(f"Exposure rate to\n{label}, centred", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(color=constants.palette7[6], linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.annotate(
        f"Any age effect $p$ {annotate_p(result['p_joint'])}\n"
        f"Nonlinearity $p$ {annotate_p(result['p_nonlinear'])}",
        xy=(0.03, 0.04),
        xycoords="axes fraction",
        fontsize=8,
        va="bottom",
    )

    stem = os.path.join(FIGURES, f"age_spline_{result['yvar']}")
    for ext in ("pdf", "png"):
        fig.savefig(f"{stem}.{ext}", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: figures/age_spline_{result['yvar']}.{{pdf,png}}")


def fmt_p(p):
    """Bare p for table cells: `< .001` below the floor, otherwise `.091`."""
    return "< .001" if p < 0.001 else f"{p:.3f}".lstrip("0")


def annotate_p(p):
    """Same value inside a sentence, where a bare `.091` needs its relation."""
    return fmt_p(p) if p < 0.001 else f"= {fmt_p(p)}"


def main():
    print("=== Age gradient: flexible spline in birth year ===")
    data = pd.read_csv(FP_COMBINED)
    if len(data) != 1134:
        raise ValueError(f"expected the 1,134-panelist analytic sample, got {len(data)}")

    basis, cols = nonlinear_basis(data)
    data = pd.concat([data, basis], axis=1)
    print(
        f"natural cubic spline, df={SPLINE_DF}: 1 linear + {len(cols)} nonlinear "
        f"directions, HC1 errors"
    )

    outcomes = [(f"bl_{m}_rate", constants.var_labels[f"bl_{m}_rate"]) for m in MEASURES]
    outcomes.append(EXTRA)

    print(
        f"\n{'outcome':30s} {'any age p':>10s} {'nonlin p':>9s} "
        f"{'mgcv edf':>9s} {'mgcv p':>10s}  verdict"
    )
    rows, agree, bends = [], 0, 0
    for yvar, label in outcomes:
        result = test_one(data, yvar, cols)
        bends += result["p_nonlinear"] < 0.05
        mgcv_edf, mgcv_p = MGCV_REFERENCE[yvar]
        same = (result["p_joint"] < 0.05) == (mgcv_p < 0.05)
        agree += same
        print(
            f"{label:30s} {result['p_joint']:10.3g} {result['p_nonlinear']:9.3g} "
            f"{mgcv_edf:9.2f} {mgcv_p:10.3g}  {'agrees' if same else 'DIFFERS'}"
        )
        rows.append(
            {
                "Measure": label,
                "Any age effect": fmt_p(result["p_joint"]),
                "Nonlinearity": fmt_p(result["p_nonlinear"]),
                "mgcv EDF": f"{mgcv_edf:.2f}",
                "mgcv smooth": fmt_p(mgcv_p),
            }
        )
        draw(result, label)

    print(f"\njoint test agrees with mgcv on {agree} of {len(outcomes)} outcomes")
    print(
        f"nonlinearity beyond a straight line: {bends} of {len(outcomes)} outcomes "
        f"at p < .05"
    )

    pandas_to_tex(pd.DataFrame(rows), FP_TESTS)
    print(f"Saved: tables/{os.path.basename(FP_TESTS)}.tex")
    print("\n=== Age Spline Complete ===")


if __name__ == "__main__":
    sys.exit(main())
