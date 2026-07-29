"""Tracking on the sites where being tracked matters most.

Site-level audits report how many health sites carry a session recorder. The
panel supports the question users actually care about: of the people who went
looking for health information, how many were recorded doing it -- and how many
still would be behind a blocker.

Categories are read per visit from the meter's own labels, never collapsed to the
domain. The field is multi-label and comma separated, so a page labelled
"Business, Health" counts as health. See 09_build_visit_panel.py for why the
domain-level collapse is unusable and what visit coverage this buys.

A person counts as exposed in a category if any visit they made to a page in that
category met the behavior. That is a reach measure, not an intensity one: one
session recorder on one health visit is the thing worth knowing about.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocking"))

import common as blk  # noqa: E402
import config as blk_config  # noqa: E402

FP_VISIT_PANEL = os.path.join(blk_config.BLOCKING_DATA_DIR, "visit_panel.parquet")

# Categories where the browsing itself discloses something: a health condition,
# money trouble, a job search, sexual interest, dealings with the state.
SENSITIVE = [
    "Health",
    "Economy and Finance",
    "Job Related",
    "Adult",
    "Government",
]

BEHAVIORS = [
    ("session_recording", "Session Recording"),
    ("key_logging", "Keylogging"),
    ("canvas_fingerprinting", "Canvas Fingerprinting"),
]

TIER = blk.HEADLINE_TIER
MIN_VISITORS = 30


def main():
    visits = pd.read_parquet(FP_VISIT_PANEL)
    n_panel = visits["caseid"].nunique()

    labelled = visits[visits["category"].notna()].copy()
    print(f"Visit panel: {len(visits):,} visits, {n_panel:,} panelists")
    print(f"  categorisable: {len(labelled):,} ({len(labelled) / len(visits):.1%})")

    labelled["label"] = labelled["category"].str.split(", ")
    exploded = labelled.explode("label")
    exploded["label"] = exploded["label"].str.strip()
    print(f"  distinct labels: {exploded['label'].nunique():,}")

    rows = []
    for category in SENSITIVE:
        sub = exploded[exploded["label"] == category]
        visitors = sub["caseid"].nunique()
        if visitors < MIN_VISITORS:
            print(f"  skipping {category}: only {visitors} visitors")
            continue
        row = {
            "category": category,
            "visits": len(sub),
            "domains": sub["private_domain"].nunique(),
            "visitors": visitors,
            "visitor_share": 100 * visitors / n_panel,
        }
        for measure, _ in BEHAVIORS:
            met = sub.groupby("caseid")[measure].max() > 0
            met_r = sub.groupby("caseid")[f"{measure}_resid_{TIER}"].max() > 0
            row[f"{measure}_pct"] = 100 * met.mean()
            row[f"{measure}_pct_resid"] = 100 * met_r.mean()
        rows.append(row)

    out = pd.DataFrame(rows).sort_values("visitors", ascending=False)

    print(
        "\nShare of each category's visitors who met the behavior *on that "
        "category's pages*"
    )
    print("(pct = unblocked; resid = still exposed behind EasyList+EasyPrivacy)\n")
    show = ["category", "visitors", "visitor_share", "domains"] + [
        c for m, _ in BEHAVIORS for c in (f"{m}_pct", f"{m}_pct_resid")
    ]
    print(out[show].to_string(index=False, float_format="%.1f"))

    out.to_csv(
        os.path.join(blk_config.BLOCKING_DATA_DIR, "sensitive_categories.csv"),
        index=False,
    )

    tex = pd.DataFrame(
        {
            "Category": out["category"],
            "Visitors": out["visitors"].map(lambda x: f"{x:,}"),
            "\\% of panel": out["visitor_share"].map(lambda x: f"{x:,.1f}"),
        }
    )
    for measure, label in BEHAVIORS:
        tex[label] = out.apply(
            lambda r, m=measure: f"{r[f'{m}_pct']:,.1f} ({r[f'{m}_pct_resid']:,.1f})",
            axis=1,
        )
    blk.pandas_to_tex(tex, blk.table_path("sensitive_category_exposure.tex"))
    print("\nWrote tables/sensitive_category_exposure.tex")


if __name__ == "__main__":
    sys.exit(main())
