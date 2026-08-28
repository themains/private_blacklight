"""Is the age gap in exposure an artifact of which device people were metered on?

Older and younger panelists do not use the same devices, and mobile and desktop
browsing are tracked differently, so the age gap could in principle be a device
effect wearing a demographic costume.

The clean test would be within-person: the same individual on both devices, every
personal characteristic differenced out. This panel cannot support it. The two
RealityMine device files partition the sample exactly -- 695 panelists metered on
desktop, 454 on mobile, 15 on both, summing to the 1,134 analytic sample. Device
here is a person-level attribute, not something that varies within a person, and
15 people is no basis for a within-person estimate.

What the data does support is three between-person checks, which together bound
the concern:

  1. the age gradient estimated separately within each device group -- if it
     holds in both, device mix is not producing it
  2. device added to the Table 5 specification -- does the 65+ coefficient move?
  3. how much of the pooled gap device composition can arithmetically account for

None identifies a device effect free of selection. They do establish whether the
age gap survives conditioning on device, which is the question actually at issue.
"""

import os
import sys

import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocking"))

import common as blk  # noqa: E402
import config as blk_config  # noqa: E402

FP_VISIT_PANEL = os.path.join(blk_config.BLOCKING_DATA_DIR, "visit_panel.parquet")

AGE_TERM = blk.AGE_TERM
MEASURES = [(m, blk.MEASURE_LABELS[m]) for m in blk.HEADLINE_MEASURES]
stars = blk.stars


def fit_raw(yvar, data, rhs=None):
    """Table 5's specification, optionally with extra right-hand-side terms."""
    rhs = rhs or blk.FORMULA_RHS
    return smf.ols(f"{yvar} ~ {rhs}", data=data).fit(cov_type="HC1")


def main():
    user = pd.read_csv(blk_config.FP_USER_RESIDUAL)
    visits = pd.read_parquet(FP_VISIT_PANEL)

    device = visits.groupby("caseid")["person_device"].first().rename("device")
    user = user.merge(device, on="caseid", how="left")

    print("Panelists by metered device")
    print(user["device"].value_counts().to_string())
    print("\nAge composition by device (%)")
    print(
        pd.crosstab(user["agegroup_lab"], user["device"], normalize="columns")
        .mul(100)
        .to_string(float_format="%.1f")
    )

    # Exclude the 15 seen on both: they belong to neither group cleanly, and
    # there are too few to form a third.
    single = user[user["device"].isin(["desktop", "mobile"])].copy()
    print(f"\nSingle-device panelists used below: {len(single):,}")

    rows = []
    for measure, label in MEASURES:
        yvar = f"bl_{measure}_rate"

        pooled = fit_raw(yvar, user)
        with_device = fit_raw(yvar, single, rhs=blk.FORMULA_RHS + " + C(device)")

        row = {
            "measure": label,
            "pooled_coef": pooled.params[AGE_TERM],
            "pooled_p": pooled.pvalues[AGE_TERM],
            "device_adj_coef": with_device.params[AGE_TERM],
            "device_adj_p": with_device.pvalues[AGE_TERM],
        }
        for dev in ("desktop", "mobile"):
            sub = single[single["device"] == dev]
            model = fit_raw(yvar, sub)
            row[f"{dev}_coef"] = model.params[AGE_TERM]
            row[f"{dev}_p"] = model.pvalues[AGE_TERM]
            row[f"{dev}_n"] = len(sub)
        rows.append(row)

    out = pd.DataFrame(rows)

    print("\n\n65+ vs under-25 coefficient, pooled and conditioned on device\n")
    for _, r in out.iterrows():
        print(f"  {r['measure']}")
        print(f"    pooled            {r['pooled_coef']:8.4f}{stars(r['pooled_p']):<3s}")
        print(
            f"    + device control  {r['device_adj_coef']:8.4f}"
            f"{stars(r['device_adj_p']):<3s}  "
            f"({100 * r['device_adj_coef'] / r['pooled_coef']:.0f}% of pooled)"
        )
        for dev in ("desktop", "mobile"):
            print(
                f"    {dev:<17s} {r[f'{dev}_coef']:8.4f}"
                f"{stars(r[f'{dev}_p']):<3s}  (n={r[f'{dev}_n']:,.0f})"
            )
        print()

    # How much of the pooled gap could device composition alone explain? Take
    # the between-device difference in mean exposure and multiply by the
    # difference in device mix across the two age groups.
    print("Arithmetic ceiling on the device-composition channel\n")
    ceiling = []
    for measure, label in MEASURES:
        yvar = f"bl_{measure}_rate"
        means = single.groupby("device")[yvar].mean()
        mix = pd.crosstab(single["agegroup_lab"], single["device"], normalize="index")
        if "65+" not in mix.index or "<25" not in mix.index:
            continue
        share_diff = mix.loc["65+"] - mix.loc["<25"]
        contribution = float((share_diff * means).sum())
        gap = (
            single[single["agegroup_lab"] == "65+"][yvar].mean()
            - single[single["agegroup_lab"] == "<25"][yvar].mean()
        )
        ceiling.append(
            {
                "measure": label,
                "raw_gap": gap,
                "device_composition": contribution,
                "share_of_gap_pct": 100 * contribution / gap if gap else float("nan"),
            }
        )
    ceiling = pd.DataFrame(ceiling)
    print(ceiling.to_string(index=False, float_format="%.4f"))

    out.to_csv(
        os.path.join(blk_config.BLOCKING_DATA_DIR, "device_age_gradient.csv"), index=False
    )
    ceiling.to_csv(
        os.path.join(blk_config.BLOCKING_DATA_DIR, "device_composition_ceiling.csv"),
        index=False,
    )

    tex = pd.DataFrame(
        {
            "Measure": out["measure"],
            "Pooled": out.apply(
                lambda r: f"{r['pooled_coef']:,.3f}{stars(r['pooled_p'])}", axis=1
            ),
            "+ Device": out.apply(
                lambda r: f"{r['device_adj_coef']:,.3f}{stars(r['device_adj_p'])}", axis=1
            ),
            "Desktop only": out.apply(
                lambda r: f"{r['desktop_coef']:,.3f}{stars(r['desktop_p'])}", axis=1
            ),
            "Mobile only": out.apply(
                lambda r: f"{r['mobile_coef']:,.3f}{stars(r['mobile_p'])}", axis=1
            ),
        }
    )
    blk.pandas_to_tex(tex, blk.table_path("device_age_gradient.tex"))
    print("\nWrote tables/device_age_gradient.tex")


if __name__ == "__main__":
    sys.exit(main())
