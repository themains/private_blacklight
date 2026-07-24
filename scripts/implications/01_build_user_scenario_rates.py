"""Step 01: per-user coverage, scenario exposure rates, and drift deltas.

One row per analytical-sample panelist (caseid) with:

  coverage        share of the user's visits on Blacklight-scanned domains
                  (construction from scripts/per_user_coverage.ipynb)
  {k}_{scenario}  per-user visit-weighted exposure rate for measure k under
                  each unscanned-visit fill scenario (constructions lifted
                  verbatim from httparchive/07_coverage_bounds and
                  wayback/06_coverage_bounds_wayback; fills are calibrated,
                  visit-weighted E[Blacklight | aux presence] on jointly
                  measured domains, always on the Blacklight scale)
  ha22_{k}, ha25_{k}, drift_{k}
                  same-instrument per-user rates with domain-level tracking
                  measured by HTTP Archive June 2022 vs Jan 2025 (matched
                  domains, construction from httparchive/
                  06_temporal_user_exposure), and their difference

Validation printed: the zero scenario must correlate ~1.000 with the
published bl_*_rate columns, and coverage must reproduce the pooled 76.4% /
mean 0.742 from per_user_coverage.ipynb.

Writes: data/implications/user_scenario_rates.csv
"""

import os

import numpy as np
import pandas as pd

import config

KEYS = ["ddg_join_ads", "third_party_cookies", "fb_pixel", "google_analytics"]


def wmean(vals, w):
    return np.average(vals, weights=w) if len(vals) else 0.0


def main():
    os.makedirs(config.IMPL_DATA_DIR, exist_ok=True)

    yg = pd.read_csv(config.FP_YG_IND_DOMAIN)
    yg["filename"] = yg["private_domain"].str.replace(".", "_", regex=False)

    bl = pd.read_csv(config.FP_BLACKLIGHT)
    ha = pd.read_csv(config.FP_HA_DOMAIN_MEASURES)
    ha22 = ha.query("crawl == 'panel'").groupby("private_domain")[KEYS].mean()
    ha25 = (
        ha.query("crawl == 'blacklight_match'").groupby("private_domain")[KEYS].mean()
    )
    wb = (
        pd.read_csv(config.FP_WB_DOMAIN_MEASURES)
        .drop_duplicates("private_domain")
        .set_index("private_domain")
    )

    merged = (
        yg.merge(
            bl.rename(columns={k: f"bl_{k}" for k in bl.columns if k != "filename"}),
            on="filename",
            how="left",
        )
        .merge(
            ha22.add_prefix("ha_"),
            left_on="private_domain",
            right_index=True,
            how="left",
        )
        .merge(
            wb[[k for k in config.WB_KEYS]].add_prefix("wb_"),
            left_on="private_domain",
            right_index=True,
            how="left",
        )
    )

    comb = pd.read_csv(
        config.FP_COMBINED,
        usecols=["caseid"] + [f"bl_{k}_rate" for k in KEYS],
    ).set_index("caseid")
    sample = comb.index

    scanned = merged["bl_ddg_join_ads"].notna()
    ha_measured = merged["ha_ddg_join_ads"].notna()
    wb_measured = merged["wb_ddg_join_ads"].notna()
    w_all = merged["visits"]
    tt_visits = merged.groupby("caseid")["visits"].sum()

    def user_rate(counts):
        return (counts * merged["visits"]).groupby(merged["caseid"]).sum() / tt_visits

    out = pd.DataFrame(index=tt_visits.index)
    out["coverage"] = (
        merged.loc[scanned]
        .groupby("caseid")["visits"]
        .sum()
        .reindex(tt_visits.index)
        .fillna(0)
        / tt_visits
    )

    # ------------------- fill scenarios, per measure ------------------- #
    for k in config.MEASURES:
        c_bl = merged[f"bl_{k}"]
        fill_mean = wmean(c_bl[scanned], w_all[scanned])

        ha_present = merged[f"ha_{k}"] > 0
        calib = scanned & ha_measured
        ha_fill = np.where(
            ha_present,
            wmean(c_bl[calib & ha_present], w_all[calib & ha_present]),
            wmean(c_bl[calib & ~ha_present], w_all[calib & ~ha_present]),
        )

        scen = {
            "zero": c_bl.fillna(0),
            "mean": c_bl.fillna(fill_mean),
        }

        c = c_bl.copy()
        c[~scanned & ha_measured] = ha_fill[~scanned & ha_measured]
        c[~scanned & ~ha_measured] = fill_mean
        scen["ha_mean"] = c

        c = c_bl.copy()
        c[~scanned & ha_measured] = ha_fill[~scanned & ha_measured]
        if k in config.WB_KEYS:
            wb_present = merged[f"wb_{k}"] > 0
            calib_wb = scanned & wb_measured
            wb_fill = np.where(
                wb_present,
                wmean(c_bl[calib_wb & wb_present], w_all[calib_wb & wb_present]),
                wmean(c_bl[calib_wb & ~wb_present], w_all[calib_wb & ~wb_present]),
            )
            wb_only = ~scanned & ~ha_measured & wb_measured
            c[wb_only] = wb_fill[wb_only]
            c[~scanned & ~ha_measured & ~wb_measured] = fill_mean
        else:
            # no Wayback visibility for this measure: hawb falls back to ha
            c[~scanned & ~ha_measured] = fill_mean
        scen["hawb_mean"] = c

        for name, counts in scen.items():
            out[f"{k}_{name}"] = user_rate(counts)

    # ------------------- same-instrument drift (strand A) -------------- #
    matched = ha22.index.intersection(ha25.index)
    dom = (
        ha22.loc[matched].add_prefix("h22_").join(ha25.loc[matched].add_prefix("h25_"))
    )
    m2 = yg.merge(dom, left_on="private_domain", right_index=True, how="left")
    tt2 = m2.groupby("caseid")["visits"].sum()
    for k in config.MEASURES:
        r22 = (m2[f"h22_{k}"].fillna(0) * m2["visits"]).groupby(
            m2["caseid"]
        ).sum() / tt2
        r25 = (m2[f"h25_{k}"].fillna(0) * m2["visits"]).groupby(
            m2["caseid"]
        ).sum() / tt2
        out[f"ha22_{k}"] = r22
        out[f"ha25_{k}"] = r25
        out[f"drift_{k}"] = r25 - r22

    out = out.reindex(sample)
    out.to_csv(config.FP_USER_RATES)
    print(f"Wrote {config.FP_USER_RATES}  ({len(out):,} users)")

    # ------------------- validation ------------------------------------ #
    pooled = merged.loc[scanned, "visits"].sum() / merged["visits"].sum()
    print(f"pooled coverage: {pooled:.1%} (per_user_coverage.ipynb: 76.4%)")
    print(f"mean per-user coverage: {out['coverage'].mean():.3f} (target 0.742)")
    for k in config.MEASURES:
        r = out[f"{k}_zero"].corr(comb[f"bl_{k}_rate"])
        print(f"corr(zero scenario, published rate) {k:22}: {r:.4f}")
    means = out[[f"{k}_{s}" for k in config.MEASURES for s in config.SCENARIOS]].mean()
    print(means.round(3).to_string())


if __name__ == "__main__":
    main()
