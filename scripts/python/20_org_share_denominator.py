"""20_org_share_denominator.py
Put the organization shares on the same denominator as every other rate.

`06_browsing_history.ipynb` divided each organization's captured visits by
`df_visits.groupby("caseid").size()` -- a count taken on the *unfiltered* visit
frame. That frame contains 60,547 visits with no `private_domain`. Such a visit
cannot be attributed to any organization by construction, so counting it below
the line can only push the share down; and `tt_visits`, the denominator every
other rate in the paper uses, is itself built after `dropna(subset=
["private_domain"])` in `02`. The result was the one denominator in the paper
that differed from all the others, on 963 of the 1,134 panelists.

The notebook is fixed, but it cannot be re-run here: it needs all three
RealityMine visit files and `realityMine_web` is restricted on Dataverse. This
script applies the same correction to the derived analytic file, which is what
every downstream script actually reads.

Only the denominator moves. The numerators -- `top_org_visits` and the captured
visit count -- are correct as committed and are not recomputed. Rebuilding them
would mean re-deriving the organization mapping, and the committed
`ddg_domain_map.json` is a slightly different Tracker Radar vintage from the one
the notebook used (38,267 domains against 38,210), so a rebuild would change
numbers that are not wrong. That is re-estimation, not a fix.

The old denominator is recoverable exactly as `top_org_visits / top_org_share`,
which is what makes this a correction rather than an approximation, and what
makes the script idempotent: once corrected, that ratio *is* `tt_visits` and a
second run changes nothing.

Not corrected here: `top_org_share_duration`. Its denominator was total dwell
time over the unfiltered frame, which is not recoverable from the committed
columns. It feeds one appendix figure
(`figures/dist_maxshare_hist_duration_summtable.pdf`, ms Fig. A.6) and carries
the same downward bias of roughly one percent. Re-running `06` with the raw
visit files is the only fix.

Input:  data/combined_yg_bl_who_derived_hist_tracking.csv
Output: data/combined_yg_bl_who_derived_hist_tracking.csv  (top_org_share,
        captured_visits)
"""

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

REPO = os.path.abspath(os.path.join(_HERE, ".."))
FP_COMBINED = os.path.join(REPO, "data", "combined_yg_bl_who_derived_hist_tracking.csv")
FP_VISITS = os.path.join(REPO, "data", "yg", "yg_ind_domain.csv")

# The domain-less visits, counted once when 06 last ran. Used only as a gate.
EXPECTED_EXCESS = 60_547


def main():
    print("=== Organization shares: denominator correction ===")
    data = pd.read_csv(FP_COMBINED)
    if len(data) != 1134:
        raise ValueError(f"expected the 1,134-panelist analytic sample, got {len(data)}")

    # Gate: yg_ind_domain.csv is the domain-attributable visit set, so it must
    # reproduce tt_visits exactly. If it does not, tt_visits is not the
    # denominator this correction assumes it is.
    visits = pd.read_csv(FP_VISITS)
    rebuilt = visits.groupby("caseid")["visits"].sum().reindex(data["caseid"])
    worst = float(np.abs(rebuilt.to_numpy() - data["tt_visits"].to_numpy()).max())
    if worst > 1e-6:
        raise ValueError(
            f"yg_ind_domain does not reproduce tt_visits (max diff {worst:,.4f}); "
            "the attributable visit set is not what tt_visits counts"
        )
    print(f"gate: yg_ind_domain reproduces tt_visits exactly ({len(data):,} panelists)")

    has_org = data["top_org_share"] > 0
    old_denom = pd.Series(np.nan, index=data.index)
    old_denom[has_org] = (
        data.loc[has_org, "top_org_visits"] / data.loc[has_org, "top_org_share"]
    )
    excess = (old_denom - data["tt_visits"]).round()

    if (excess.dropna() < -0.5).any():
        raise ValueError(
            "the recovered denominator is smaller than tt_visits for some panelists; "
            "it is not the unfiltered visit count this correction assumes"
        )

    total_excess = int(excess.sum())
    affected = int((excess > 0.5).sum())
    if total_excess == 0:
        print("already corrected: the denominator is tt_visits; nothing to do.")
        return 0
    if total_excess != EXPECTED_EXCESS:
        print(
            f"  note: excess is {total_excess:,}, not the {EXPECTED_EXCESS:,} recorded "
            "when 06 last ran -- 06 has been re-run against different data."
        )
    print(
        f"domain-less visits in the old denominator: {total_excess:,} "
        f"across {affected:,} panelists (max {int(excess.max()):,})"
    )

    before = {
        "top_org_share": data["top_org_share"].copy(),
        "captured_visits": data["captured_visits"].copy(),
    }

    data["top_org_share"] = data["top_org_visits"] / data["tt_visits"]
    # captured_visits is already a share, so rescale it by the ratio of the two
    # denominators rather than trying to recover its numerator separately.
    scale = (old_denom / data["tt_visits"]).fillna(1.0)
    data["captured_visits"] = data["captured_visits"] * scale

    print("\n              published -> corrected")
    for col, old in before.items():
        print(
            f"  {col:16s} mean {old.mean():.4f} -> {data[col].mean():.4f}   "
            f"median {old.median():.4f} -> {data[col].median():.4f}   "
            f"p75 {old.quantile(0.75):.4f} -> {data[col].quantile(0.75):.4f}"
        )

    if (data["captured_visits"] > 1.0 + 1e-9).any():
        raise ValueError("corrected captured_visits exceeds 1; the rescale is wrong")
    if (data["top_org_share"] > 1.0 + 1e-9).any():
        raise ValueError("corrected top_org_share exceeds 1; the rescale is wrong")

    data.to_csv(FP_COMBINED, index=False)
    print(f"\nSaved: {os.path.relpath(FP_COMBINED, REPO)}")
    print("=== Denominator Correction Complete ===")


if __name__ == "__main__":
    sys.exit(main())
