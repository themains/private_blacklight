"""Step 02: draw the seeded audit sample of unscanned domains.

Two draws from the same unscanned pool, without replacement:
  visits  stratum: P(domain) proportional to panel visits -- what a typical
                   unscanned *visit* lands on.
  uniform stratum: equal probability -- what a typical unscanned *domain* is.

A domain drawn by both keeps both stratum flags (analyzed per stratum).
Evidence columns are pre-filled from existing artifacts so coding (step 04)
and analysis (step 05) never re-derive them.

Writes: data/selection_audit/audit_sample.csv
"""

import os

import numpy as np
import pandas as pd

import config


def main():
    pool = pd.read_csv(config.FP_FAILURE_REASONS)  # unscanned domains only

    # Invariant: nothing in the pool has a Jan-2025 scan on disk.
    scanned_files = {
        f for f in os.listdir(config.FP_BL_JSON_DIR) if f.endswith(".json")
    }
    files = pool["private_domain"].str.replace(".", "_", regex=False) + ".json"
    assert not files.isin(scanned_files).any(), "sample pool contains scanned domains"

    rng = np.random.default_rng(config.SAMPLE_SEED)
    n = config.N_PER_STRATUM

    p = pool["visits"] / pool["visits"].sum()
    visits_idx = rng.choice(len(pool), size=n, replace=False, p=p.values)
    uniform_idx = rng.choice(len(pool), size=n, replace=False)

    pool["in_visits_stratum"] = False
    pool["in_uniform_stratum"] = False
    pool.loc[pool.index[visits_idx], "in_visits_stratum"] = True
    pool.loc[pool.index[uniform_idx], "in_uniform_stratum"] = True
    sample = pool.query("in_visits_stratum or in_uniform_stratum").copy()

    # ---------------- evidence columns ---------------- #
    ddg = pd.read_csv(config.FP_DDG_CATEGORIES).set_index("domain")
    sample["is_ddg_tracker"] = sample["private_domain"].isin(ddg.index)
    sample["ddg_categories"] = sample["private_domain"].map(ddg["categories"])
    sample["ddg_owner"] = sample["private_domain"].map(ddg["owner"])

    ha22 = set(
        pd.read_csv(config.FP_HA_DOMAIN_MEASURES)
        .query("crawl == 'panel'")["private_domain"]
        .unique()
    )
    sample["ha22_measured"] = sample["private_domain"].isin(ha22)

    wb = pd.read_csv(config.FP_WB_MANIFEST).drop_duplicates("private_domain")
    wb = wb.set_index("private_domain")
    sample["wb_2022_capture"] = (
        sample["private_domain"].map(wb["cdx_hit"]).fillna(False).astype(bool)
    )
    sample["wb_snapshot_ts"] = sample["private_domain"].map(wb["snapshot_ts"])
    sample["wb_html_cached"] = sample["private_domain"].map(
        lambda d: os.path.exists(config.wb_html_path(d))
    )

    sample = sample.sort_values(
        ["in_visits_stratum", "visits"], ascending=[False, False]
    )
    sample.to_csv(config.FP_AUDIT_SAMPLE, index=False)

    n_both = int((sample["in_visits_stratum"] & sample["in_uniform_stratum"]).sum())
    print(f"Wrote {config.FP_AUDIT_SAMPLE}")
    print(f"  pool (unscanned domains)   : {len(pool):,}")
    print(
        f"  unique sampled domains     : {len(sample):,} "
        f"(overlap between strata: {n_both})"
    )
    for col in ["is_ddg_tracker", "ha22_measured", "wb_2022_capture", "wb_html_cached"]:
        v = sample.loc[sample.in_visits_stratum, col].mean()
        u = sample.loc[sample.in_uniform_stratum, col].mean()
        print(f"  {col:18}: visits-stratum {v:.0%} | uniform-stratum {u:.0%}")


if __name__ == "__main__":
    main()
