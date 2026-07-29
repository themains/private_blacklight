"""What blocking leaves behind, and for whom.

Two questions. How much exposure survives each defense, and whether the defenses
available today shrink the demographic gap in exposure or leave it standing.

The second question has a trap. Blocking lowers everyone's exposure, so the
absolute gap between age groups falls almost mechanically, and a claim that
protection is "regressive" is really a claim about the gap falling more slowly
than the level it sits on. The gap is therefore reported as a **log-ratio** --
how many times the 65+ mean exceeds the under-25 mean, before and after -- with
a bootstrap interval over panelists. An earlier version divided the regression
coefficient by the mean; that quantity puts one noisy estimate over another
whose denominator is 0.004 for session recording, and picking the measure that
cleared significance inflates its own magnitude. The log-ratio is scale-free,
symmetric between the groups, and does not blow up.

Absolute HC1 coefficients are reported alongside, from the paper's Table 5
specification, reused unchanged via blocking/common.py so the estimates are
comparable with it line for line.

Multiplicity: 7 measures x 3 tiers = 21 residual age-gap tests. Following
07_demo_differences.py, raw-p stars stay in the tex and a Bonferroni check
against 0.05/21 is printed beside the unadjusted verdict.
"""

import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as blk  # noqa: E402
import config  # noqa: E402


def levels_table(user):
    """Exposure per visit, unblocked and under each tier, with ID bounds."""
    rows = []
    for measure in config.MEASURES:
        base = user[f"bl_{measure}_rate"].mean()
        row = {
            "measure": blk.MEASURE_LABELS[measure],
            "unblocked": base,
            "assumed": measure in blk.ASSUMED,
        }
        for tier in config.TIER_ORDER:
            hi = user[f"bl_{measure}_resid_{tier}_rate"].mean()
            lo = user[f"bl_{measure}_resid_{tier}_lo_rate"].mean()
            row[f"{tier}_resid"] = hi
            row[f"{tier}_lo"] = lo
            row[f"{tier}_pct_left"] = 100 * hi / base if base else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def gap_table(user):
    """65+ coefficient and log-ratio gap, unblocked and under each tier."""
    rows = []
    for measure in config.MEASURES:
        y_pre = f"bl_{measure}_rate"
        specs = [("unblocked", y_pre)] + [
            (f"tier_{t}", f"bl_{measure}_resid_{t}_rate") for t in config.TIER_ORDER
        ]
        for name, yvar in specs:
            model = blk.fit(yvar, user)
            coef = model.loc["Age: 65+"]
            entry = {
                "measure": blk.MEASURE_LABELS[measure],
                "measure_key": measure,
                "assumed": measure in blk.ASSUMED,
                "spec": name,
                "coef": coef.b,
                "se": coef.se,
                "p": coef.p,
                "stars": blk.stars(coef.p),
                "mean": user[yvar].mean(),
                "log_ratio": blk.log_ratio(user, yvar),
            }
            if name != "unblocked":
                shift = blk.gap_shift(user, y_pre, yvar)
                lo, hi, valid = blk.bootstrap_ci(
                    user, lambda d, a=y_pre, b=yvar: blk.gap_shift(d, a, b)
                )
                entry.update(
                    {"gap_shift": shift, "shift_lo": lo, "shift_hi": hi, "valid": valid}
                )
            rows.append(entry)
    return pd.DataFrame(rows)


def main():
    user = blk.load_user()
    print(f"Panelists: {len(user):,}\n")

    levels = levels_table(user)
    print("Exposure per visit, unblocked and after each defense")
    print("(residual shown as point [identification bound]; the bound covers what")
    print(" a hostname test cannot adjudicate, and is not sampling uncertainty)\n")
    show = ["measure", "unblocked"] + [
        c for t in config.TIER_ORDER for c in (f"{t}_resid", f"{t}_lo", f"{t}_pct_left")
    ]
    print(levels[show].to_string(index=False, float_format="%.4f"))

    gaps = gap_table(user)

    print("\n\n65+ versus under-25, before and after blocking")
    print("(ratio = how many times the 65+ mean exceeds the under-25 mean;")
    print(" shift = change in log-ratio, 95% bootstrap interval over panelists)\n")
    for measure in blk.HEADLINE_MEASURES:
        sub = gaps[gaps["measure_key"] == measure]
        print(f"  {blk.MEASURE_LABELS[measure]}")
        for _, r in sub.iterrows():
            line = (
                f"    {r['spec']:10s} coef {r['coef']:8.4f}{r['stars']:<3s} "
                f"(se {r['se']:.4f})  mean {r['mean']:7.4f}  "
                f"ratio {_exp(r['log_ratio']):5.2f}x"
            )
            if pd.notna(r.get("gap_shift")):
                line += (
                    f"  shift {r['gap_shift']:+.3f} "
                    f"[{r['shift_lo']:+.3f}, {r['shift_hi']:+.3f}]"
                )
            print(line)
        print()

    tier = blk.HEADLINE_TIER
    headline = gaps[(gaps["spec"] == f"tier_{tier}") & (~gaps["assumed"])]
    print(f"Change in the age gap under tier {tier} ({blk.TIER_LABELS[tier]})")
    print("An interval covering zero means the data cannot distinguish any change.\n")
    verdict = headline[
        ["measure", "log_ratio", "gap_shift", "shift_lo", "shift_hi", "valid"]
    ].copy()
    pre = gaps[gaps["spec"] == "unblocked"].set_index("measure")["log_ratio"]
    verdict.insert(1, "ratio_before", verdict["measure"].map(pre).apply(_exp))
    verdict["ratio_after"] = verdict["log_ratio"].apply(_exp)
    verdict = verdict.drop(columns="log_ratio")
    print(verdict.to_string(index=False, float_format="%.3f"))

    blk.bonferroni_report(
        [
            (f"{r.measure} / {r.spec}", r.p)
            for r in gaps[gaps["spec"] != "unblocked"].itertuples()
        ]
    )

    os.makedirs(config.TABLES_DIR, exist_ok=True)
    levels.to_csv(
        os.path.join(config.BLOCKING_DATA_DIR, "residual_levels.csv"), index=False
    )
    gaps.to_csv(os.path.join(config.BLOCKING_DATA_DIR, "residual_gaps.csv"), index=False)
    verdict.to_csv(
        os.path.join(config.BLOCKING_DATA_DIR, "residual_gap_verdict.csv"), index=False
    )

    tex_levels = pd.DataFrame(
        {
            "Measure": levels["measure"],
            "Unblocked": levels["unblocked"].map(lambda x: f"{x:,.3f}"),
            "Firefox ETP": levels.apply(_bounded("A"), axis=1),
            "EasyPrivacy": levels.apply(_bounded("B"), axis=1),
            "EasyList+EasyPrivacy": levels.apply(_bounded("C"), axis=1),
            "\\% left": levels["C_pct_left"].map(lambda x: f"{x:,.1f}"),
        }
    )
    blk.pandas_to_tex(tex_levels, blk.table_path("residual_levels.tex"))

    tex_gaps = pd.DataFrame(
        {
            "Measure": headline["measure"],
            "Ratio before": headline["measure"]
            .map(pre)
            .apply(_exp)
            .map("{:,.2f}".format),
            "Ratio after": headline["log_ratio"].apply(_exp).map("{:,.2f}".format),
            "$\\Delta$ log-ratio": headline.apply(
                lambda r: f"{r['gap_shift']:+,.3f} [{r['shift_lo']:+,.3f}, "
                f"{r['shift_hi']:+,.3f}]",
                axis=1,
            ),
        }
    )
    blk.pandas_to_tex(tex_gaps, blk.table_path("residual_age_gap.tex"))
    print("\nWrote tables/residual_levels.tex, tables/residual_age_gap.tex")


def _exp(x):
    """Log-ratio back to a plain multiplier, for reading."""
    return math.exp(x) if pd.notna(x) else float("nan")


def _bounded(tier):
    def fmt(row):
        return f"{row[f'{tier}_resid']:,.3f} [{row[f'{tier}_lo']:,.3f}]"

    return fmt


if __name__ == "__main__":
    sys.exit(main())
