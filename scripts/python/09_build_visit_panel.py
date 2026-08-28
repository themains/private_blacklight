"""Assemble the visit-level panel used by the category and device analyses.

The paper's exposure estimates run off yg_ind_domain.csv, which aggregates a
panelist's visits to each domain and carries no category or device. Three
questions need what that aggregation drops:

  - which categories a person browsed, to ask about sensitive browsing
  - how their category mix compares with other people's, to decompose the age gap
  - which device the browsing came from

Categories must be read per visit, not per domain. The meter labels pages, and
collapsing to the domain gives a portal every label any of its pages ever
carried: at domain level all 986,722 google.com visits look "Job Related",
while at visit level 0.02% of them are. The domain-level map
(data/yg/domain_categories.csv) is kept only for reference.

Coverage: the two device files together cover all 1,134 panelists but 29.5% of
their visits, the rest sitting in a third RealityMine file that is restricted on
Dataverse. Category results are therefore about the visits that can be
categorised, and say so.

Device is a person-level attribute in this panel. The desktop and mobile files
partition the sample -- 695 and 454 panelists, only 15 in both -- so there is no
within-person device comparison to be had here.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocking"))

import config as blk_config  # noqa: E402

FP_DESKTOP = os.path.join(
    blk_config.DATA_DIR, "yg", "realityMine_web_desktop_2022-06-01_2022-06-30.csv"
)
FP_MOBILE = os.path.join(
    blk_config.DATA_DIR, "yg", "realityMine_web_mobile_2022-06-01_2022-06-30.csv"
)
FP_VISIT_PANEL = os.path.join(blk_config.BLOCKING_DATA_DIR, "visit_panel.parquet")

USECOLS = ["caseid", "private_domain", "category", "device_type", "visit_duration"]


def load(fp, source):
    if not os.path.exists(fp):
        raise FileNotFoundError(
            f"{fp} not found. The desktop file is public on Harvard Dataverse:\n"
            "  curl -L -o data/yg/realityMine_web_desktop_2022-06-01_2022-06-30.csv "
            '"https://dataverse.harvard.edu/api/access/datafile/6797142"'
        )
    df = pd.read_csv(fp, usecols=USECOLS, low_memory=False)
    return df.assign(source=source)


def main():
    visits = pd.concat(
        [load(FP_DESKTOP, "desktop"), load(FP_MOBILE, "mobile")], ignore_index=True
    ).dropna(subset=["private_domain"])

    print(f"Visit-level rows: {len(visits):,}  panelists: {visits.caseid.nunique():,}")
    print(
        f"  with a category label: {visits.category.notna().sum():,} "
        f"({visits.category.notna().mean():.1%})"
    )

    panel_visits = pd.read_csv(blk_config.FP_YG_IND_DOMAIN)["visits"].sum()
    print(
        f"  share of the panel's {panel_visits:,.0f} visits: "
        f"{len(visits) / panel_visits:.1%}"
    )

    # Device is fixed per person here, so record it as one, and keep the raw
    # per-visit value for the handful of people seen on both.
    by_person = visits.groupby("caseid")["source"].agg(["nunique", "first"])
    both = int((by_person["nunique"] > 1).sum())
    print(
        f"\nPanelists on both devices: {both} of {len(by_person):,} "
        "-- device is effectively a person-level attribute"
    )
    visits["person_device"] = visits["caseid"].map(by_person["first"])
    visits.loc[
        visits["caseid"].isin(by_person.index[by_person["nunique"] > 1]), "person_device"
    ] = "both"

    resid = pd.read_csv(blk_config.FP_DOMAIN_RESIDUAL)
    resid["private_domain"] = resid["filename"].str.replace("_", ".", regex=False)
    keep = [c for c in resid.columns if c not in ("filename",)]
    visits = visits.merge(resid[keep], on="private_domain", how="left")

    scanned = visits["ddg_join_ads"].notna()
    print(
        f"\nVisits on Blacklight-scanned domains: {scanned.sum():,} "
        f"({scanned.mean():.1%})"
    )
    print("  unscanned domains contribute zero, as in the paper")
    measure_cols = [c for c in keep if c != "private_domain"]
    visits[measure_cols] = visits[measure_cols].fillna(0)

    os.makedirs(blk_config.BLOCKING_DATA_DIR, exist_ok=True)
    visits.to_parquet(FP_VISIT_PANEL, index=False)
    print(f"\nWrote {FP_VISIT_PANEL}")

    print("\nPanelists by device:")
    print(visits.groupby("person_device")["caseid"].nunique().to_string())


if __name__ == "__main__":
    sys.exit(main())
