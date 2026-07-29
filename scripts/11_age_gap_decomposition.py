"""Why are older panelists more exposed -- where they browse, or what they pick?

"Older users encounter more trackers" is a fact without a mechanism. It has two
very different readings. Older panelists might spend their time in categories
that are more heavily tracked, in which case the gap is about *what* they browse.
Or, within the same categories, they might land on more heavily tracked sites, in
which case it is about *which* sites they choose. The two imply different
remedies, so they are worth separating.

A shift-share split does it. Writing a group's exposure as a sum over categories
of (share of visits) x (tracking per visit in that category), the gap between two
groups decomposes into

  composition   different category mix, holding tracking intensity fixed
  site choice   different tracking within the same categories, holding mix fixed
  interaction   the residual cross term

This is preferred to a regression-based Oaxaca here because it reads directly off
observed quantities and sidesteps the choice of reference coefficients. Both base
groups are reported, since the split is not symmetric in which group supplies the
weights.

Standard errors come from resampling panelists.

Two things bound the exercise. Categories are read per visit, which restricts it
to the 29.5% of panel visits carrying device-file labels; a gate first checks the
age gap on that subsample resembles the published full-sample gap, so the
decomposition is explaining the same phenomenon. And because visits carry
several labels, each visit is split fractionally across its labels so shares sum
to one; uncategorised visits form their own bucket rather than being dropped.
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocking"))

import common as blk  # noqa: E402
import config as blk_config  # noqa: E402

FP_VISIT_PANEL = os.path.join(blk_config.BLOCKING_DATA_DIR, "visit_panel.parquet")

MEASURES = [
    (m, blk.MEASURE_LABELS[m]) for m in blk.HEADLINE_MEASURES if m != "key_logging"
]

OLD, YOUNG = blk.OLD, blk.YOUNG
BOOTSTRAP_REPS = 500
BOOTSTRAP_SEED = blk.BOOTSTRAP_SEED
UNCATEGORISED = "(uncategorised)"


def explode_fractional(visits):
    """One row per (visit, label), each carrying 1/k of the visit."""
    df = visits.copy()
    df["label"] = df["category"].fillna(UNCATEGORISED).str.split(", ")
    df["k"] = df["label"].str.len()
    df = df.explode("label")
    df["label"] = df["label"].str.strip()
    df["w"] = 1.0 / df["k"]
    return df


def person_label_matrix(df, measure):
    """Per person and label: visit weight, and weight x tracking.

    Both quantities sum over people, so every group statistic the decomposition
    needs is a column sum of these matrices. That is what makes resampling
    panelists cheap -- a bootstrap draw is an index into precomputed rows rather
    than a rebuild of two million visits.
    """
    agg = df.groupby(["caseid", "label"]).agg(w=("w", "sum"), wt=(measure, lambda x: 0.0))
    agg["wt"] = (
        df.assign(_wt=df["w"] * df[measure]).groupby(["caseid", "label"])["_wt"].sum()
    )
    w = agg["w"].unstack(fill_value=0.0)
    wt = agg["wt"].unstack(fill_value=0.0)
    wt = wt.reindex(columns=w.columns, fill_value=0.0)
    return w, wt


def decompose(w_old, wt_old, w_young, wt_young):
    """Shift-share on group totals: shares from w, intensities from wt / w."""
    with np.errstate(invalid="ignore", divide="ignore"):
        s_old = w_old / w_old.sum()
        s_young = w_young / w_young.sum()
        t_old = np.where(w_old > 0, wt_old / np.where(w_old > 0, w_old, 1), 0.0)
        t_young = np.where(w_young > 0, wt_young / np.where(w_young > 0, w_young, 1), 0.0)

    total = (s_old * t_old).sum() - (s_young * t_young).sum()
    out = {}
    for base in ("young", "old"):
        if base == "young":
            composition = ((s_old - s_young) * t_young).sum()
            site_choice = (s_young * (t_old - t_young)).sum()
        else:
            composition = ((s_old - s_young) * t_old).sum()
            site_choice = (s_old * (t_old - t_young)).sum()
        out[base] = {
            "gap": total,
            "composition": composition,
            "site_choice": site_choice,
            "interaction": total - composition - site_choice,
        }
    return out


def shift_share(df, measure, group_col, old=OLD, young=YOUNG):
    w, wt = person_label_matrix(df, measure)
    groups = df.groupby("caseid")[group_col].first().reindex(w.index)
    is_old = (groups == old).to_numpy()
    is_young = (groups == young).to_numpy()

    wv, wtv = w.to_numpy(), wt.to_numpy()
    res = decompose(
        wv[is_old].sum(0), wtv[is_old].sum(0), wv[is_young].sum(0), wtv[is_young].sum(0)
    )
    shares = pd.DataFrame(
        {
            "label": w.columns,
            "s_old": wv[is_old].sum(0) / wv[is_old].sum(),
            "s_young": wv[is_young].sum(0) / wv[is_young].sum(),
        }
    )
    return res, shares, (wv, wtv, is_old, is_young)


def bootstrap(matrices, reps=BOOTSTRAP_REPS):
    """Resample panelists; percentile intervals for each component."""
    wv, wtv, is_old, is_young = matrices
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = wv.shape[0]
    draws = {k: [] for k in ("gap", "composition", "site_choice", "interaction")}

    for _ in range(reps):
        pick = rng.integers(0, n, size=n)
        o, y = is_old[pick], is_young[pick]
        if not o.any() or not y.any():
            continue
        res = decompose(
            wv[pick][o].sum(0),
            wtv[pick][o].sum(0),
            wv[pick][y].sum(0),
            wtv[pick][y].sum(0),
        )
        for k in draws:
            draws[k].append(res["young"][k])

    return {
        k: (
            (np.percentile(v, 2.5), np.percentile(v, 97.5))
            if len(v) > reps * 0.5
            else (float("nan"), float("nan"))
        )
        for k, v in draws.items()
    }


def gate_subsample(visits, user):
    """The gap on the categorisable subsample must track the published gap."""
    rate = visits.groupby("caseid")[[m for m, _ in MEASURES]].mean().reset_index()
    merged = rate.merge(user[["caseid", "agegroup_lab"]], on="caseid", how="inner")
    print("\nGate -- age gap on the visit subsample vs the published full sample")
    rows = []
    for measure, label in MEASURES:
        sub = merged[merged["agegroup_lab"].isin([OLD, YOUNG])]
        gap_sub = sub.groupby("agegroup_lab")[measure].mean().get(
            OLD, np.nan
        ) - sub.groupby("agegroup_lab")[measure].mean().get(YOUNG, np.nan)
        full = user[user["agegroup_lab"].isin([OLD, YOUNG])]
        gap_full = full.groupby("agegroup_lab")[f"bl_{measure}_rate"].mean().get(
            OLD, np.nan
        ) - full.groupby("agegroup_lab")[f"bl_{measure}_rate"].mean().get(YOUNG, np.nan)
        rows.append(
            {
                "measure": label,
                "gap_subsample": gap_sub,
                "gap_full": gap_full,
                "same_sign": bool(np.sign(gap_sub) == np.sign(gap_full)),
            }
        )
    gate = pd.DataFrame(rows)
    print(gate.to_string(index=False, float_format="%.4f"))
    if not gate["same_sign"].all():
        print(
            "\n  WARNING: the subsample gap reverses sign on some measures. "
            "The decomposition below describes the subsample, not the paper's "
            "estimand -- read it with that in mind."
        )
    return gate


def main():
    visits = pd.read_parquet(FP_VISIT_PANEL)
    user = pd.read_csv(blk_config.FP_USER_RESIDUAL)
    visits = visits.merge(user[["caseid", "agegroup_lab"]], on="caseid", how="inner")

    gate = gate_subsample(visits, user)
    gate.to_csv(
        os.path.join(blk_config.BLOCKING_DATA_DIR, "decomposition_gate.csv"), index=False
    )

    df = explode_fractional(visits)
    n_old = df[df["agegroup_lab"] == OLD]["caseid"].nunique()
    n_young = df[df["agegroup_lab"] == YOUNG]["caseid"].nunique()
    print(f"\nComparing {OLD} (n={n_old}) with {YOUNG} (n={n_young})")
    print(f"Categories: {df['label'].nunique():,}")

    results, shares = [], None
    for measure, label in MEASURES:
        res, share_tbl, matrices = shift_share(df, measure, "agegroup_lab")
        ci = bootstrap(matrices)
        if shares is None:
            shares = share_tbl
        for base in ("young", "old"):
            row = {"measure": label, "base": base, **res[base]}
            if base == "young":
                for k, (lo, hi) in ci.items():
                    row[f"{k}_lo"], row[f"{k}_hi"] = lo, hi
            results.append(row)

    out = pd.DataFrame(results)
    print("\nDecomposition of the 65+ minus <25 gap in trackers per visit")
    print(
        "(young base; 95% percentile intervals from "
        f"{BOOTSTRAP_REPS} resamples of panelists)\n"
    )
    for measure, label in MEASURES:
        r = out[(out["measure"] == label) & (out["base"] == "young")].iloc[0]
        alt = out[(out["measure"] == label) & (out["base"] == "old")].iloc[0]
        print(f"  {label}: total gap {r['gap']:.4f}")
        for comp in ("composition", "site_choice", "interaction"):
            pct = 100 * r[comp] / r["gap"] if r["gap"] else float("nan")
            print(
                f"    {comp:12s} {r[comp]:8.4f} ({pct:5.1f}% of gap)  "
                f"CI [{r[f'{comp}_lo']:.4f}, {r[f'{comp}_hi']:.4f}]  "
                f"| old-base {alt[comp]:.4f}"
            )
        print()

    out.to_csv(
        os.path.join(blk_config.BLOCKING_DATA_DIR, "age_gap_decomposition.csv"),
        index=False,
    )

    tex = out[out["base"] == "young"].copy()
    tex_out = pd.DataFrame(
        {
            "Measure": tex["measure"],
            "Total gap": tex["gap"].map(lambda x: f"{x:,.3f}"),
            "Composition": tex.apply(
                lambda r: f"{r['composition']:,.3f} [{r['composition_lo']:,.3f}, "
                f"{r['composition_hi']:,.3f}]",
                axis=1,
            ),
            "Site choice": tex.apply(
                lambda r: f"{r['site_choice']:,.3f} [{r['site_choice_lo']:,.3f}, "
                f"{r['site_choice_hi']:,.3f}]",
                axis=1,
            ),
            "Interaction": tex["interaction"].map(lambda x: f"{x:,.3f}"),
        }
    )
    blk.pandas_to_tex(tex_out, blk.table_path("age_gap_decomposition.tex"))
    print("Wrote tables/age_gap_decomposition.tex")


if __name__ == "__main__":
    sys.exit(main())
