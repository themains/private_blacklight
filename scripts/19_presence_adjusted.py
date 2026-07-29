"""19_presence_adjusted.py
Holding browsing volume constant without assuming exposure is proportional to it.

The paper reports demographic differences two ways, and the difference between
them is how each holds browsing volume constant. Equation (6) divides cumulative
exposure by visits, which *imposes* proportionality between browsing and
exposure. Equation (7) does not impose it: it enters volume and volume squared
directly on the right-hand side of a median regression on cumulative exposure and
lets the data say whether the relationship is proportional, concave, or something
else. Work on other online risks adjusts this way, so reporting both is what
makes a difference in our demographic coefficients read as a difference in the
phenomenon rather than in the arithmetic.

Every measure is fit twice -- demographics alone, then demographics plus the
volume terms. The pair is the point; the manuscript's claim is about what moves
between the two columns.

Two implementation notes that matter for correctness:

  - statsmodels solves the median regression by iteratively reweighted least
    squares, which is an approximation to the linear program the problem
    actually is. The approximation is visible here: rescaling the outcome by
    1,000 moved the Age 65+ coefficient by about 1%, which is solver tolerance
    rather than data. Every reported fit is therefore re-solved exactly through
    scipy's HiGHS and the two must agree.
  - Some bootstrap resamples do not converge. They are counted and reported, not
    silently dropped, following bootstrap_ci in blocking/common.py.

Input:  data/combined_yg_bl_who_derived_hist_tracking.csv
Output: tables/presence_adjusted_median.tex   (supplementary regression table)
"""

import importlib
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.optimize import linprog
from scipy.stats import norm

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import constants  # noqa: E402

REPO = os.path.abspath(os.path.join(_HERE, ".."))
FP_COMBINED = os.path.join(REPO, "data", "combined_yg_bl_who_derived_hist_tracking.csv")
FP_TABLE = os.path.join(REPO, "tables", "presence_adjusted_median")

TAU = 0.5
BOOTSTRAP_REPS = 1000
BOOTSTRAP_SEED = 20250110  # the seed the residual module already uses
LP_TOLERANCE = 0.01  # relative, on the objective; see check_lp_optimality

MEASURES = [
    "ddg_join_ads",
    "third_party_cookies",
    "fb_pixel",
    "google_analytics",
    "key_logging",
    "session_recording",
    "canvas_fingerprinting",
]
EXTRA = ("top_org_visits", "Top organization visits")

PRESENCE_TERMS = ["visits_scaled", "I(visits_scaled ** 2)"]
PRESENCE_LABELS = {
    "visits_scaled": "Total visits (scaled)",
    "I(visits_scaled ** 2)": "Total visits$^2$ (scaled)",
}

# The two values the manuscript paragraph names explicitly.
PROSE_TERMS = ["Educ: College", "Age: 65+"]
PROSE_MEASURES = ["Ad Trackers", "Third-Party Cookies"]
PROSE_OUTCOMES = ["bl_ddg_join_ads", "bl_third_party_cookies"]


def _load_config():
    """implications/config.py, whose formula and labels also drive Tables 5-6.

    Imported through a path swap because the module name `config` is generic and
    several subdirectories define one; same loader shape as 07_demo_differences.
    """
    saved_path, saved_cfg = list(sys.path), sys.modules.pop("config", None)
    sys.path.insert(0, os.path.join(_HERE, "implications"))
    try:
        cfg = importlib.import_module("config")
        return cfg.FORMULA_RHS, dict(cfg.COEF_LABELS)
    finally:
        sys.path[:] = saved_path
        sys.modules.pop("config", None)
        if saved_cfg is not None:
            sys.modules["config"] = saved_cfg


FORMULA_RHS, DEMO_LABELS = _load_config()
COEF_LABELS = {**DEMO_LABELS, **PRESENCE_LABELS}


def rescale(series):
    """Map onto the unit interval, the scaling this adjustment conventionally uses."""
    lo, hi = series.min(), series.max()
    return (series - lo) / (hi - lo)


def fit_median(yvar, data, presence):
    """Median regression, with the volume terms only if asked for."""
    rhs = FORMULA_RHS + (" + " + " + ".join(PRESENCE_TERMS) if presence else "")
    return smf.quantreg(f"{yvar} ~ {rhs}", data).fit(q=TAU)


def check_lp_optimality(result, label):
    """Re-solve the same median regression exactly and compare objectives.

    Quantile regression minimises asymmetrically weighted absolute residuals.
    Writing each residual as u - v with u, v >= 0 makes that a standard-form
    linear program, which HiGHS solves exactly where iteratively reweighted least
    squares only approaches the optimum. Objectives are compared rather than
    coefficients: with collinear regressors the argmin need not be unique, but
    its value is.
    """
    y = np.asarray(result.model.endog, dtype=float)
    x = np.asarray(result.model.exog, dtype=float)
    n, p = x.shape

    cost = np.concatenate([np.zeros(p), np.full(n, TAU), np.full(n, 1 - TAU)])
    a_eq = np.hstack([x, np.eye(n), -np.eye(n)])
    bounds = [(None, None)] * p + [(0, None)] * (2 * n)
    solved = linprog(cost, A_eq=a_eq, b_eq=y, bounds=bounds, method="highs")
    if not solved.success:
        raise RuntimeError(f"{label}: the reference LP did not solve ({solved.message})")

    residual = y - x @ np.asarray(result.params, dtype=float)
    ours = float(np.sum(np.where(residual >= 0, TAU, TAU - 1) * residual))
    exact = float(solved.fun)
    gap = (ours - exact) / max(abs(exact), 1.0)
    if gap > LP_TOLERANCE:
        raise ValueError(
            f"{label}: the statsmodels fit is {gap:.2%} above the exact LP optimum "
            f"({ours:,.1f} vs {exact:,.1f}); the solution has not converged and "
            "its coefficients are not the median regression's"
        )
    return gap


def bootstrap_se(yvar, data, presence, reps=BOOTSTRAP_REPS, seed=BOOTSTRAP_SEED):
    """Resample panelists, refit, take the spread of the coefficients.

    Panelists are the unit of independent variation, so they are the unit
    resampled. Draws that fail to fit are counted and returned rather than
    quietly dropped, so a standard error built on the draws that happened to
    converge cannot pass for one built on all of them.
    """
    rng = np.random.default_rng(seed)
    n = len(data)
    draws, failed = [], 0
    for _ in range(reps):
        sample = data.iloc[rng.integers(0, n, n)]
        try:
            draws.append(fit_median(yvar, sample, presence).params)
        except Exception:
            failed += 1
    if len(draws) < reps // 2:
        raise ValueError(
            f"{yvar}: only {len(draws)} of {reps} bootstrap draws fit; the standard "
            "errors would describe the draws that happened to converge"
        )
    return pd.DataFrame(draws).std(), failed


def coefficient_frame(fitted, se):
    """Labelled coefficients, bootstrap standard errors, and normal-approximation p."""
    terms = [t for t in fitted.params.index if t in COEF_LABELS]
    frame = pd.DataFrame(
        {
            "b": fitted.params[terms].to_numpy(),
            "se": np.asarray(se.reindex(terms), dtype=float),
        },
        index=pd.Index([COEF_LABELS[t] for t in terms]),
    )
    frame["p"] = 2 * (1 - norm.cdf((frame["b"] / frame["se"]).abs()))
    return frame


def estimate(yvar, label, data):
    """Both specifications for one outcome, with bootstrapped standard errors."""
    out = {}
    for presence in (False, True):
        key = "presence" if presence else "raw"
        fitted = fit_median(yvar, data, presence)
        gap = check_lp_optimality(fitted, f"{label} [{key}]")
        se, failed = bootstrap_se(yvar, data, presence)
        frame = coefficient_frame(fitted, se)
        frame.attrs.update(
            n=int(fitted.nobs),
            failed=failed,
            lp_gap=gap,
            intercept=float(fitted.params["Intercept"]),
        )
        out[key] = frame

    # The demographic block must be the one behind Tables 5 and 6, or the
    # "adjusting for volume changes X" claim is comparing two different models.
    # Membership, not sequence: patsy orders the design matrix its own way and
    # the table reindexes onto COEF_LABELS regardless, so ordering carries no
    # information about whether the specifications agree.
    got = {t for t in out["raw"].index if t in set(DEMO_LABELS.values())}
    want = set(DEMO_LABELS.values())
    if got != want:
        raise ValueError(
            f"{label}: demographic terms differ from the Table 5-6 specification. "
            f"missing {sorted(want - got)}; unexpected {sorted(got - want)}"
        )
    return out


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def cell(row):
    if pd.isna(row.b):
        return ""
    return f"{row.b:,.0f}{stars(row.p)} ({row.se:,.0f})"


def panel(results, key, order):
    """One specification: a row per coefficient, a column per outcome."""
    columns = {label: res[key].apply(cell, axis=1) for label, res in results.items()}
    frame = pd.DataFrame(columns).reindex(order).fillna("")
    return frame.reset_index(names="Coefficient")


def write_table(results, fp):
    """Two stacked panels rather than sixteen side-by-side columns.

    Eight outcomes crossed with two specifications is seventeen columns, which
    no page can carry legibly. Stacking puts the same information on nine, and
    it stacks the way the claim reads: the paragraph is about what moves between
    Panel A and Panel B for a given outcome, which is a vertical comparison.
    """
    order = list(dict.fromkeys(COEF_LABELS.values()))
    a = panel(results, "raw", [t for t in order if t in DEMO_LABELS.values()])
    b = panel(results, "presence", order)
    ncol = a.shape[1]
    head = r"\multicolumn{%d}{l}{\textit{%s}} \\"

    lines = [head % (ncol, "Panel A. Demographics only")]
    lines += [" & ".join(r) + r" \\" for r in a.astype(str).to_numpy()]
    lines += [
        r"\addlinespace",
        head % (ncol, "Panel B. Demographics and browsing volume"),
    ]
    lines += [" & ".join(r) + r" \\" for r in b.astype(str).to_numpy()]

    with open(f"{fp}.tex", "w") as f:
        f.write("\n".join(lines) + "\n")
    return ncol


def report_manuscript_values(results, data):
    """Every value ms/blacklight.tex:445 needs, so none of them is typed by hand."""
    print("\n=== Values for the Equation (7) paragraph ===")
    for label, yvar in zip(PROSE_MEASURES, PROSE_OUTCOMES):
        raw, pres = results[label]["raw"], results[label]["presence"]
        print(f"\n{label}")
        for term in PROSE_TERMS:
            print(
                f"  {term:24s} {raw.loc[term, 'b']:10,.0f} -> "
                f"{pres.loc[term, 'b']:9,.0f}   "
                f"SE {pres.loc[term, 'se']:8,.0f}   p = {pres.loc[term, 'p']:.3f}"
            )
        for term in PRESENCE_LABELS.values():
            print(
                f"  {term:24s} {'':10s}    {pres.loc[term, 'b']:9,.0f}   "
                f"SE {pres.loc[term, 'se']:8,.0f}   p = {pres.loc[term, 'p']:.3f}"
            )
        # The previous paragraph states the age gap as a share of the under-25
        # mean, so give the adjusted gap on the same footing. The denominator is
        # the observed under-25 median, NOT the fitted intercept: with volume
        # and volume squared on the right-hand side the intercept is the fitted
        # median at zero visits, which is both outside the data (the minimum is
        # two visits) and negative here, so dividing by it returns a meaningless
        # -195%.
        gap = pres.loc["Age: 65+", "b"]
        base = float(data.loc[data["agegroup_lab"] == "<25", yvar].median())
        share = f"{gap / base:.0%}" if base else "undefined (under-25 median is zero)"
        print(f"  {'65+ vs under-25 median':24s} {gap:9,.0f} / {base:,.0f} = {share}")


def main():
    print("=== Volume-adjusted median regressions (Equation 7) ===")
    data = pd.read_csv(FP_COMBINED)
    if len(data) != 1134:
        raise ValueError(f"expected the 1,134-panelist analytic sample, got {len(data)}")
    data = data.assign(visits_scaled=rescale(data["tt_visits"]))

    print(
        f"volume = tt_visits rescaled to [0, 1] "
        f"(median {data.tt_visits.median():,.0f}, max {data.tt_visits.max():,.0f}); "
        f"median regression at tau = {TAU}, {BOOTSTRAP_REPS} bootstrap draws, "
        f"seed {BOOTSTRAP_SEED}"
    )

    outcomes = [(f"bl_{m}", constants.var_labels[f"bl_{m}"]) for m in MEASURES]
    outcomes.append(EXTRA)

    results = {}
    for yvar, label in outcomes:
        res = estimate(yvar, label, data)
        results[label] = res
        print(
            f"  {label:24s} n = {res['presence'].attrs['n']:,}  "
            f"LP gap {res['presence'].attrs['lp_gap']:.1e}  "
            f"failed draws {res['raw'].attrs['failed']}/{res['presence'].attrs['failed']}"
        )

    ncol = write_table(results, FP_TABLE)
    print(
        f"\nSaved: tables/{os.path.basename(FP_TABLE)}.tex ({ncol} columns, two panels)"
    )

    report_manuscript_values(results, data)
    print("\n=== Volume Adjustment Complete ===")


if __name__ == "__main__":
    sys.exit(main())
