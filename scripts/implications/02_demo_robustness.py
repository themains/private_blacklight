"""Step 02: are the paper's demographic comparisons robust to the threats?

Holds the specification behind Tables 5 and 6 (OLS on
gender/race/education/age-group dummies with the same reference categories,
Huber-White HC1 errors) in statsmodels, then asks three questions:

  gate      Replication first: the zero-fill (published) rate regressions
            must reproduce ms Table 5's benchmark coefficients within
            rounding before any new scenario is interpreted.
  coverage  Does per-user scan coverage vary by demographics? If missingness
            is demographically flat, zero-filling cannot manufacture or mask
            group gaps. (Outcome in percentage points.)
  scenarios Do the Table-5 coefficients hold when unscanned visits are
            filled per strand B's calibrated scenarios instead of zeroed?
  drift     Is the June-2022 -> Jan-2025 change in same-instrument per-user
            exposure demographically patterned? If not, scan timing does not
            tilt cross-group comparisons.

Writes: tables/implications_coverage_by_demo.tex
        tables/implications_demo_fill_scenarios.tex
        tables/implications_drift_by_demo.tex
        figures/implications_demo_scenarios.{pdf,png}
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import config

sys.path.insert(0, os.path.abspath(".."))
from utilities import pandas_to_tex, save_mpl_fig  # noqa: E402

LABELS = list(config.COEF_LABELS.values())


def fit(yvar, data):
    model = smf.ols(f"{yvar} ~ {config.FORMULA_RHS}", data=data).fit(cov_type="HC1")
    coefs = pd.DataFrame({"b": model.params, "se": model.bse, "p": model.pvalues})
    coefs.index = [config.COEF_LABELS.get(i, i) for i in coefs.index]
    coefs = coefs.reindex(LABELS)
    coefs.attrs["r2"] = model.rsquared
    coefs.attrs["n"] = int(model.nobs)
    return coefs


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def cell(row):
    return f"{row.b:.2f}{stars(row.p)} ({row.se:.2f})"


def run_gate(data):
    print("=== Replication gate vs ms Table 5 ===")
    ok = True
    fitted = {}
    for yvar in ["bl_ddg_join_ads_rate", "bl_third_party_cookies_rate"]:
        fitted[yvar] = fit(yvar, data)
    for (yvar, label), target in config.TABLE5_BENCHMARKS.items():
        got = fitted[yvar].loc[label, "b"]
        match = abs(got - target) <= config.GATE_TOLERANCE
        ok &= match
        print(
            f"{yvar:32} {label:18} published {target:+.2f}  "
            f"replicated {got:+.2f}  {'OK' if match else 'MISMATCH'}"
        )
    n = fitted["bl_ddg_join_ads_rate"].attrs["n"]
    print(f"n = {n}")
    if not ok:
        raise SystemExit(
            "Replication gate FAILED: statsmodels spec does not reproduce "
            "ms Table 5. Investigate before interpreting scenarios."
        )


def run_coverage(data):
    data = data.assign(coverage_pct=100 * data["coverage"])
    res = fit("coverage_pct", data)
    out = pd.DataFrame(
        {"term": res.index, "coverage_pct": res.apply(cell, axis=1).values}
    )
    pandas_to_tex(out, os.path.join(config.TABLES_DIR, "implications_coverage_by_demo"))
    print("\n=== Per-user scan coverage (pp) by demographics ===")
    print(res.round(2).to_string())
    print(f"R2 = {res.attrs['r2']:.3f}, n = {res.attrs['n']}")
    print("wrote tables/implications_coverage_by_demo.tex")
    return res


def run_scenarios(data):
    results = {}
    for k in config.MEASURES:
        for s in config.SCENARIOS:
            results[(k, s)] = fit(f"{k}_{s}", data)

    out = pd.DataFrame({"term": LABELS})
    for k in config.MEASURES:
        for s in config.SCENARIOS:
            out[f"{k}_{s}"] = results[(k, s)].apply(cell, axis=1).values
    pandas_to_tex(
        out, os.path.join(config.TABLES_DIR, "implications_demo_fill_scenarios")
    )
    print("\n=== Table-5 spec under fill scenarios ===")
    for k in config.MEASURES:
        show = pd.DataFrame({s: results[(k, s)]["b"] for s in config.SCENARIOS})
        print(f"\n{k} (coefficients):")
        print(show.round(2).to_string())
    print("wrote tables/implications_demo_fill_scenarios.tex")

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.6), sharey=True)
    markers = ["o", "s", "^", "D"]
    shades = ["0.0", "0.35", "0.6", "0.8"]
    ypos = np.arange(len(LABELS))
    for ax, k in zip(axes, config.MEASURES):
        for j, s in enumerate(config.SCENARIOS):
            r = results[(k, s)]
            off = (j - 1.5) * 0.18
            ax.errorbar(
                r["b"],
                ypos + off,
                xerr=1.96 * r["se"],
                fmt=markers[j],
                color=shades[j],
                ms=4,
                lw=1,
                capsize=2,
                label=s if k == config.MEASURES[0] else None,
            )
        ax.axvline(0, color="0.8", lw=1, zorder=0)
        ax.set_title(
            (
                "Ad trackers / visit"
                if k == "ddg_join_ads"
                else "Third-party cookies / visit"
            ),
            fontsize=10,
        )
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(ypos)
    axes[0].set_yticklabels([x.replace("--", "–") for x in LABELS])
    axes[0].invert_yaxis()
    fig.legend(
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=9,
        title="Unscanned-visit fill scenario",
        title_fontsize=9,
    )
    plt.tight_layout(rect=(0, 0.1, 1, 1))
    save_mpl_fig(os.path.join(config.FIGURES_DIR, "implications_demo_scenarios"))
    plt.close()
    return results


def run_drift(data):
    # The same spec on the same-instrument rates at each date shows how much
    # of any 2025-measured gap already existed under June-2022 measurement;
    # the drift column is their difference.
    out = pd.DataFrame({"term": LABELS})
    print("\n=== Same-instrument gaps by measurement date, and drift ===")
    for k in config.MEASURES:
        for stem in [f"ha22_{k}", f"ha25_{k}", f"drift_{k}"]:
            res = fit(stem, data)
            out[stem] = res.apply(cell, axis=1).values
            print(f"\n{stem}:")
            print(res.round(3).to_string())
            print(f"R2 = {res.attrs['r2']:.3f}, n = {res.attrs['n']}")
    pandas_to_tex(out, os.path.join(config.TABLES_DIR, "implications_drift_by_demo"))
    print("wrote tables/implications_drift_by_demo.tex")


def main():
    demo = pd.read_csv(
        config.FP_COMBINED,
        usecols=[
            "caseid",
            "gender_lab",
            "race_lab",
            "educ_lab",
            "agegroup_lab",
            "bl_ddg_join_ads_rate",
            "bl_third_party_cookies_rate",
        ],
    )
    rates = pd.read_csv(config.FP_USER_RATES)
    data = demo.merge(rates, on="caseid", how="inner", validate="1:1")
    print(f"analysis rows: {len(data)}")

    run_gate(data)
    run_coverage(data)
    run_scenarios(data)
    run_drift(data)


if __name__ == "__main__":
    main()
