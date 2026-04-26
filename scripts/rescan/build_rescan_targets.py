import os
import pandas as pd

N        = 1000
YG       = "../../data/yg/yg_ind_domain.csv"
JAN_DIR  = "../../data/blacklight_json"
OUT      = "../../data/rescan_targets_2026.csv"

scan_files = {f for f in os.listdir(JAN_DIR) if f.endswith(".json")}

agg = (pd.read_csv(YG)
         .groupby("private_domain")
         .agg(reach=("caseid", "nunique"),
              visits=("visits", "sum"),
              duration=("duration", "sum"))
         .reset_index())

agg["has_jan_scan"] = agg["private_domain"].apply(
    lambda d: d.replace(".", "_") + ".json" in scan_files
)

ranked = (agg.query("has_jan_scan and reach >= 2")
             .nlargest(N, "reach")
             .reset_index(drop=True))
ranked["rank_by_reach"] = ranked.index + 1

(ranked[["rank_by_reach", "private_domain", "reach", "visits", "duration"]]
    .to_csv(OUT, index=False))

print(f"Wrote {OUT}  ({len(ranked)} rows, reach range {ranked.reach.min()}–{ranked.reach.max()})")
