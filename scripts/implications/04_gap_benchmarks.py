"""Step 04: express the paper's demographic gaps on comparable scales.

ms Tables 4-5 report gaps in raw units (trackers per visit). To benchmark
them against disparities reported elsewhere -- e.g., the gender earnings
gaps in Goldin's public work -- re-express each key coefficient as (i) a
percentage of its reference group's mean rate and (ii) Cohen's d against
the pooled user-level SD. Uses the published (zero-fill) rates and the same
gate-validated specification as step 02.

Writes: tables/implications_gap_benchmarks.tex
"""

import importlib
import os
import sys

import pandas as pd

import config

sys.path.insert(0, os.path.abspath(".."))
from utilities import pandas_to_tex  # noqa: E402

demo_robustness = importlib.import_module("02_demo_robustness")

GROUPS = [
    ("Woman", "gender_lab", "Male"),
    ("Educ: College", "educ_lab", "HS or Below"),
    ("Educ: Postgraduate", "educ_lab", "HS or Below"),
    ("Age: 65+", "agegroup_lab", "<25"),
    ("Race: Asian", "race_lab", "White"),
]
OUTCOMES = [
    ("bl_ddg_join_ads_rate", "Ad trackers / visit"),
    ("bl_third_party_cookies_rate", "Third-party cookies / visit"),
]


def main():
    data = pd.read_csv(
        config.FP_COMBINED,
        usecols=["caseid", "gender_lab", "race_lab", "educ_lab", "agegroup_lab"]
        + [y for y, _ in OUTCOMES],
    )
    print(f"analysis rows: {len(data)}")

    rows = []
    for yvar, ylabel in OUTCOMES:
        res = demo_robustness.fit(yvar, data)
        pooled_sd = data[yvar].std()
        print(f"\n{ylabel}: overall mean {data[yvar].mean():.2f}, SD {pooled_sd:.2f}")
        for term, col, ref in GROUPS:
            b, p = res.loc[term, "b"], res.loc[term, "p"]
            ref_mean = data.loc[data[col] == ref, yvar].mean()
            rows.append(
                {
                    "measure": ylabel,
                    "group": term,
                    "coef": b,
                    "ref_group_mean": ref_mean,
                    "pct_of_ref": 100 * b / ref_mean,
                    "cohens_d": b / pooled_sd,
                    "stars": demo_robustness.stars(p),
                }
            )

    bench = pd.DataFrame(rows)
    show = bench.copy()
    for c in ["coef", "ref_group_mean", "cohens_d"]:
        show[c] = show[c].map("{:.2f}".format)
    show["pct_of_ref"] = show["pct_of_ref"].map("{:+.0f}".format)
    show["coef"] = show["coef"] + show.pop("stars")
    print()
    print(show.to_string(index=False))

    pandas_to_tex(show, os.path.join(config.TABLES_DIR, "implications_gap_benchmarks"))
    print("wrote tables/implications_gap_benchmarks.tex")


if __name__ == "__main__":
    main()
