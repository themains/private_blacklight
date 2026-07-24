"""Step 01 (free): build the Wayback target list, one row per domain x group.

Three groups (see config.py):
  remainder : never-measured domains (no Blacklight scan, no HA June-2022 row),
              reach >= 2, top-N by panel visits -- the tail only Wayback can
              still observe for June 2022.
  calib_bl  : visit-stratified sample of Blacklight-scanned domains, for the
              E[BL count | WB status] calibration in the bounds notebook.
  calib_ha  : sample of HA-June-2022-measured domains, for the contemporaneous
              WB-vs-HA agreement check.

A domain can appear in more than one group; it is fetched once and the groups
are resolved at analysis time.

Reads : data/httparchive/ha_targets.csv, data/blacklight_domain.csv,
        data/httparchive/ha_domain_measures.csv
Writes: data/wayback/wb_targets.csv
"""

import os

import config
import numpy as np
import pandas as pd


def stratified_sample(df, n, seed):
    """Sample n rows stratified by visits quartile (deterministic)."""
    rng = np.random.default_rng(seed)
    df = df.copy()
    df["stratum"] = pd.qcut(df["visits"].rank(method="first"), 4, labels=False)
    per = n // 4
    picks = []
    for _, grp in df.groupby("stratum"):
        take = min(per, len(grp))
        picks.append(grp.iloc[rng.permutation(len(grp))[:take]])
    return pd.concat(picks)


def main():
    os.makedirs(config.WB_DATA_DIR, exist_ok=True)

    targets = pd.read_csv(config.FP_HA_TARGETS)  # all panel domains + visits
    bl = pd.read_csv(config.FP_BLACKLIGHT)
    ha22_domains = set(
        pd.read_csv(config.FP_HA_DOMAIN_MEASURES)
        .query("crawl == 'panel'")["private_domain"]
        .unique()
    )
    bl_filenames = set(bl["filename"])

    targets["filename"] = targets["private_domain"].str.replace(".", "_", regex=False)
    targets["has_bl"] = targets["filename"].isin(bl_filenames)
    targets["has_ha22"] = targets["private_domain"].isin(ha22_domains)

    total_visits = targets["visits"].sum()
    never = targets.query("reach >= 2 and not has_bl and not has_ha22")
    remainder = never.nlargest(config.N_REMAINDER, "visits")

    calib_bl = stratified_sample(
        targets.query("has_bl"), config.N_CALIB_BL, config.SAMPLE_SEED
    )
    calib_ha = stratified_sample(
        targets.query("has_ha22"), config.N_CALIB_HA, config.SAMPLE_SEED + 1
    )

    frames = [
        remainder.assign(group="remainder"),
        calib_bl.assign(group="calib_bl"),
        calib_ha.assign(group="calib_ha"),
    ]
    out = pd.concat(frames, ignore_index=True)[
        ["group", "private_domain", "reach", "visits", "has_bl", "has_ha22"]
    ]
    out.to_csv(config.FP_WB_TARGETS, index=False)

    never_visits = never["visits"].sum()
    print(f"Wrote {config.FP_WB_TARGETS}  ({len(out):,} rows)")
    print(f"  never-measured domains (reach>=2)    : {len(never):,}")
    never_pct = 100 * never_visits / total_visits
    print(f"  their share of all visits            : {never_pct:.1f}%")
    print(
        f"  remainder targets (top {config.N_REMAINDER:,} by visits): "
        f"{100 * remainder['visits'].sum() / never_visits:.1f}% of that mass"
    )
    print(f"  calib_bl sample: {len(calib_bl):,}   calib_ha sample: {len(calib_ha):,}")
    print(
        f"  unique domains to fetch              : {out['private_domain'].nunique():,}"
    )


if __name__ == "__main__":
    main()
