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

# The cookie extract is rank-capped while the request extract is not, so a
# domain can be present in HTTP Archive and still never have been asked about
# cookies. `cookies_queried` carries that distinction through the aggregation;
# without it, "not asked" joins the "asked, found none" arm of the calibration
# and inverts it.
HA_COLS = KEYS + ["cookies_queried"]


def wmean(vals, w):
    return np.average(vals, weights=w) if len(vals) else 0.0


def main():
    os.makedirs(config.IMPL_DATA_DIR, exist_ok=True)

    yg = pd.read_csv(config.FP_YG_IND_DOMAIN)
    yg["filename"] = yg["private_domain"].str.replace(".", "_", regex=False)

    bl = pd.read_csv(config.FP_BLACKLIGHT)
    ha = pd.read_csv(config.FP_HA_DOMAIN_MEASURES)
    ha22 = ha.query("crawl == 'panel'").groupby("private_domain")[HA_COLS].mean()
    ha25 = (
        ha.query("crawl == 'blacklight_match'").groupby("private_domain")[HA_COLS].mean()
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

    def measured_for(key):
        """Which domains HTTP Archive actually interrogated for this measure."""
        if key == "third_party_cookies":
            return ha_measured & (merged["ha_cookies_queried"].fillna(0) > 0)
        return ha_measured

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

        k_measured = measured_for(k)
        ha_present = merged[f"ha_{k}"] > 0
        calib = scanned & k_measured
        m_present = wmean(c_bl[calib & ha_present], w_all[calib & ha_present])
        m_absent = wmean(c_bl[calib & ~ha_present], w_all[calib & ~ha_present])

        # The whole point of the calibrated fill is that an auxiliary sighting
        # predicts more Blacklight tracking than its absence. If it does not,
        # the "absent" arm is contaminated with domains that were never looked
        # at and the fill is worse than the assumption it replaces.
        if not (m_present > m_absent):
            raise ValueError(
                f"{k}: calibration is inverted -- HA-present predicts {m_present:.3f} "
                f"but HA-absent predicts {m_absent:.3f}. The absent arm is not a "
                "measurement of absence; check which domains were actually queried."
            )
        print(
            f"  {k:22s} calib: present {m_present:6.3f}  absent {m_absent:6.3f}  "
            f"(n_calib={int(calib.sum()):,})"
        )
        ha_fill = np.where(ha_present, m_present, m_absent)

        scen = {
            "zero": c_bl.fillna(0),
            "mean": c_bl.fillna(fill_mean),
        }

        c = c_bl.copy()
        c[~scanned & k_measured] = ha_fill[~scanned & k_measured]
        c[~scanned & ~k_measured] = fill_mean
        scen["ha_mean"] = c

        c = c_bl.copy()
        c[~scanned & k_measured] = ha_fill[~scanned & k_measured]
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
    dom = ha22.loc[matched].add_prefix("h22_").join(ha25.loc[matched].add_prefix("h25_"))
    m2 = yg.merge(dom, left_on="private_domain", right_index=True, how="left")
    for k in config.MEASURES:
        # Matching on domain is not enough for cookies: a domain can be inside
        # the rank cap at one date and outside it at the other, and the capped
        # share grows over time, so filling the uncapped side with zero would
        # read a change in what was queried as a change in what sites do.
        if k == "third_party_cookies":
            both = (m2["h22_cookies_queried"].fillna(0) > 0) & (
                m2["h25_cookies_queried"].fillna(0) > 0
            )
        else:
            both = m2[f"h22_{k}"].notna() & m2[f"h25_{k}"].notna()

        w2 = m2["visits"].where(both, 0)
        denom = w2.groupby(m2["caseid"]).sum().replace(0, np.nan)
        r22 = (m2[f"h22_{k}"].fillna(0) * w2).groupby(m2["caseid"]).sum() / denom
        r25 = (m2[f"h25_{k}"].fillna(0) * w2).groupby(m2["caseid"]).sum() / denom
        print(
            f"  drift {k:22s} on {int(both.sum()):,} domain-visits "
            f"measured at both dates ({both.mean():.1%} of rows)"
        )
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
