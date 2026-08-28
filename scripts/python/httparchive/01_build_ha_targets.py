"""Step 01 (free): build the panel-domain target list for HTTP Archive.

Aggregates the panel to one row per registered domain with reach / visits /
duration, ranks by reach, and records the cumulative visit share. The
cumulative curve grounds both validity checks: it shows how much of
visit-weighted exposure is concentrated in a small head of domains, so
measuring (or re-measuring) tracking on that head pins down most of the
estimate.

Reads : data/yg/yg_ind_domain.csv   (caseid, private_domain, duration, visits)
Writes: data/httparchive/ha_targets.csv
"""

import os

import config
import pandas as pd


def main():
    os.makedirs(config.HA_DATA_DIR, exist_ok=True)

    yg = pd.read_csv(config.FP_YG_IND_DOMAIN)

    agg = (
        yg.groupby("private_domain")
        .agg(
            reach=("caseid", "nunique"),
            visits=("visits", "sum"),
            duration=("duration", "sum"),
        )
        .reset_index()
        .sort_values("reach", ascending=False)
        .reset_index(drop=True)
    )
    agg["rank_by_reach"] = agg.index + 1

    total_visits = agg["visits"].sum()
    agg["visit_share"] = agg["visits"] / total_visits
    agg["cum_visit_share"] = agg["visit_share"].cumsum()

    cols = [
        "rank_by_reach",
        "private_domain",
        "reach",
        "visits",
        "duration",
        "visit_share",
        "cum_visit_share",
    ]
    agg[cols].to_csv(config.FP_HA_TARGETS, index=False)

    targeted = agg[agg["reach"] >= config.TARGET_MIN_REACH]
    print(f"Wrote {config.FP_HA_TARGETS}")
    print(f"  unique domains total          : {len(agg):,}")
    print(
        f"  targets (reach >= {config.TARGET_MIN_REACH})          : {len(targeted):,}"
    )
    print(f"  targets' share of all visits  : {targeted['visit_share'].sum():.1%}")
    for n in (100, 500, 1000, 5000):
        if n <= len(agg):
            cov = agg["cum_visit_share"].iloc[n - 1]
            print(f"  top {n:>5} domains cover        : {cov:.1%} of visits")


if __name__ == "__main__":
    main()
