"""How many US adults does the measured exposure correspond to?

The panel is a convenience sample with no survey weight attached, so raw
percentages describe the 1,134 people and nobody else. Raking their demographic
margins onto the CPS gives a projection: not a probability-sample estimate, but
an answer to "if the country browsed the way people with these demographics
browsed, how many would have met a keylogger in a month?"

Margins come from scripts/08_cps_benchmark.py, which already computes weighted
CPS ASEC 2022 shares for adults 18+ under Table 1's exact category definitions.
Iterative proportional fitting matches all four simultaneously.

What this does and does not fix. Raking corrects the sample's age, gender,
education and race composition. It does nothing about selection into a browsing
panel, or about how people who agree to be metered differ from those who do not
within a demographic cell. Every figure below inherits that limitation, and the
paper's zero-fill for unscanned domains on top of it.
"""

import os
import sys
import zipfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocking"))

import common as blk  # noqa: E402
import config as blk_config  # noqa: E402

FP_MARGINS = os.path.join(blk_config.DATA_DIR, "cps", "cps_asec_2022_margins.csv")
FP_ASEC_ZIP = os.path.join(blk_config.DATA_DIR, "cps", "asecpub22csv.zip")

MARGIN_VARS = {
    "gender": "gender_lab",
    "race": "race_lab",
    "educ": "educ_lab",
    "agegroup": "agegroup_lab",
}

MEASURES = [(m, blk.MEASURE_LABELS[m]) for m in blk.HEADLINE_MEASURES]

TIER = blk.HEADLINE_TIER
TRIM_PCT = (2.5, 97.5)
PCTILES = (2.5, 97.5)
MAX_ITER = 200
TOL = 1e-8
BOOTSTRAP_REPS = 500
BOOTSTRAP_SEED = blk.BOOTSTRAP_SEED


def adult_population(fp_zip):
    """Weighted count of US adults 18+ in the 2022 ASEC."""
    with zipfile.ZipFile(fp_zip) as zf:
        with zf.open("pppub22.csv") as f:
            df = pd.read_csv(f, usecols=["A_AGE", "MARSUPWT"])
    df = df[df["A_AGE"] >= 18]
    total = df["MARSUPWT"].sum()
    if total > 1e9:  # some vintages carry two implied decimals
        total /= 100
    assert 2.3e8 < total < 2.8e8, total
    return total


def rake(data, targets, max_iter=MAX_ITER, tol=TOL, quiet=False):
    """Iterative proportional fitting onto one-way margins."""
    w = np.ones(len(data))
    for it in range(max_iter):
        before = w.copy()
        for var, col in MARGIN_VARS.items():
            want = targets[targets["variable"] == var].set_index("cat")["cps_perc"]
            want = want / want.sum()
            for cat, share in want.items():
                mask = (data[col] == cat).to_numpy()
                if not mask.any():
                    raise ValueError(f"No panelists in {col} == {cat!r}")
                w[mask] *= share * w.sum() / w[mask].sum()
        if np.max(np.abs(w - before)) < tol:
            if not quiet:
                print(f"  raking converged in {it + 1} iterations")
            break
    else:
        if not quiet:
            print(f"  raking hit {max_iter} iterations without converging")
    return w * len(data) / w.sum()


def check_margins(data, w, targets):
    rows = []
    for var, col in MARGIN_VARS.items():
        want = targets[targets["variable"] == var].set_index("cat")["cps_perc"]
        got = pd.Series(w, index=data.index).groupby(data[col]).sum() / w.sum() * 100
        for cat in want.index:
            rows.append(
                {
                    "variable": var,
                    "cat": cat,
                    "target": want[cat],
                    "achieved": got.get(cat, 0.0),
                    "diff_pp": got.get(cat, 0.0) - want[cat],
                }
            )
    return pd.DataFrame(rows)


def weights_for(data, targets, quiet=True):
    """Raked and trimmed weights, normalised to sum to n."""
    w = rake(data, targets, quiet=quiet)
    lo, hi = np.percentile(w, TRIM_PCT)
    w = np.clip(w, lo, hi)
    return w * len(data) / w.sum(), lo, hi


def bootstrap_shares(user, targets, measures, tier, reps=BOOTSTRAP_REPS):
    """Percentile intervals on the weighted exposure shares.

    Weights are re-raked inside every replicate. Holding the weights fixed and
    resampling only the outcome would treat the post-stratification as known
    rather than estimated, and understate the interval.
    """
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = len(user)
    draws = {(m, kind): [] for m, _ in measures for kind in ("raw", "resid")}

    for _ in range(reps):
        sample = user.iloc[rng.integers(0, n, size=n)]
        try:
            w, _, _ = weights_for(sample, targets)
        except (ValueError, ZeroDivisionError):
            continue  # a draw missing a demographic cell cannot be raked
        for measure, _ in measures:
            draws[(measure, "raw")].append(
                np.average(sample[f"bl_{measure}"] > 0, weights=w)
            )
            draws[(measure, "resid")].append(
                np.average(sample[f"bl_{measure}_resid_{tier}"] > 0, weights=w)
            )

    out, valid = {}, None
    for key, values in draws.items():
        valid = len(values) / reps
        out[key] = (
            np.percentile(values, PCTILES)
            if valid > 0.5
            else (float("nan"), float("nan"))
        )
    return out, valid


def main():
    user = pd.read_csv(blk_config.FP_USER_RESIDUAL)
    targets = pd.read_csv(FP_MARGINS)
    print(f"Panelists: {len(user):,}")

    w = rake(user, targets)

    check = check_margins(user, w, targets)
    worst = check["diff_pp"].abs().max()
    print(f"  worst margin deviation after raking: {worst:.4f} pp")
    if worst > 0.1:
        print(check.to_string(index=False, float_format="%.3f"))
        raise AssertionError("Raked margins do not reproduce CPS targets.")

    # Extreme weights let a handful of panelists drive a national number.
    lo, hi = np.percentile(w, TRIM_PCT)
    w_trim = np.clip(w, lo, hi)
    w_trim = w_trim * len(user) / w_trim.sum()
    deff = 1 + np.var(w_trim) / np.mean(w_trim) ** 2
    print(
        f"  weights trimmed to [{lo:.3f}, {hi:.3f}]; design effect {deff:.2f}; "
        f"effective n {len(user) / deff:,.0f}"
    )

    pop = adult_population(FP_ASEC_ZIP)
    print(f"  CPS 2022 adult population: {pop:,.0f}\n")

    user = user.assign(w=w_trim)
    rows = []
    for measure, label in MEASURES:
        exposed = user[f"bl_{measure}"] > 0
        exposed_r = user[f"bl_{measure}_resid_{TIER}"] > 0
        share = np.average(exposed, weights=user["w"])
        share_r = np.average(exposed_r, weights=user["w"])
        rows.append(
            {
                "measure": label,
                "unweighted_pct": 100 * exposed.mean(),
                "weighted_pct": 100 * share,
                "projected_m": pop * share / 1e6,
                "weighted_pct_resid": 100 * share_r,
                "projected_m_resid": pop * share_r / 1e6,
            }
        )

    print(
        f"Bootstrapping projection intervals ({BOOTSTRAP_REPS} replicates, "
        "re-raking each)..."
    )
    ci, valid = bootstrap_shares(user, targets, MEASURES, TIER)
    print(f"  usable replicates: {valid:.0%}\n")

    out = pd.DataFrame(rows)
    for i, (measure, _) in enumerate(MEASURES):
        lo, hi = ci[(measure, "raw")]
        rlo, rhi = ci[(measure, "resid")]
        out.loc[i, "projected_m_lo"] = pop * lo / 1e6
        out.loc[i, "projected_m_hi"] = pop * hi / 1e6
        out.loc[i, "projected_m_resid_lo"] = pop * rlo / 1e6
        out.loc[i, "projected_m_resid_hi"] = pop * rhi / 1e6

    print("Share of adults who encountered each behavior at least once in the month")
    print("(resid = would still encounter it behind EasyList+EasyPrivacy;")
    print(" brackets are 95% bootstrap intervals over panelists)\n")
    for _, r in out.iterrows():
        print(
            f"  {r['measure']:24s} "
            f"{r['projected_m']:6.1f}M [{r['projected_m_lo']:.1f}, "
            f"{r['projected_m_hi']:.1f}]   ->  behind a blocker "
            f"{r['projected_m_resid']:6.1f}M [{r['projected_m_resid_lo']:.1f}, "
            f"{r['projected_m_resid_hi']:.1f}]"
        )

    pd.DataFrame({"caseid": user["caseid"], "w_rake": w, "w_trim": w_trim}).to_csv(
        os.path.join(blk_config.BLOCKING_DATA_DIR, "poststrat_weights.csv"), index=False
    )
    check.to_csv(
        os.path.join(blk_config.BLOCKING_DATA_DIR, "poststrat_margin_check.csv"),
        index=False,
    )
    out.to_csv(
        os.path.join(blk_config.BLOCKING_DATA_DIR, "population_projection.csv"),
        index=False,
    )

    tex = pd.DataFrame(
        {
            "Measure": out["measure"],
            "Sample (\\%)": out["unweighted_pct"].map(lambda x: f"{x:,.1f}"),
            "Weighted (\\%)": out["weighted_pct"].map(lambda x: f"{x:,.1f}"),
            "US adults (m)": out.apply(
                lambda r: f"{r['projected_m']:,.1f} [{r['projected_m_lo']:,.1f}, "
                f"{r['projected_m_hi']:,.1f}]",
                axis=1,
            ),
            "Behind a blocker (m)": out.apply(
                lambda r: f"{r['projected_m_resid']:,.1f} "
                f"[{r['projected_m_resid_lo']:,.1f}, {r['projected_m_resid_hi']:,.1f}]",
                axis=1,
            ),
        }
    )
    blk.pandas_to_tex(tex, blk.table_path("population_projection.tex"))
    print("\nWrote tables/population_projection.tex")


if __name__ == "__main__":
    sys.exit(main())
