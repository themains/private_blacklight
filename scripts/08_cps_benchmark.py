"""Benchmark the analytic sample's demographics against the CPS ASEC 2022.

Downloads the 2022 ASEC person file from census.gov (cached under
data/cps/), computes weighted shares among adults 18+ using the same
category definitions as Table 1, writes
data/cps/cps_asec_2022_margins.csv, and regenerates
tables/demo_summary.tex with CPS and difference columns appended.
Per-variable chi-square goodness-of-fit tests and mean/max absolute
deviations go into tables/demo_summary_note.tex.

Run from scripts/: python 08_cps_benchmark.py
"""

import os
import urllib.request
import zipfile

import pandas as pd
from scipy import stats
from utilities import pandas_to_tex

ASEC_URL = (
    "https://www2.census.gov/programs-surveys/cps/datasets/2022/march/" "asecpub22csv.zip"
)
FP_ASEC_ZIP = "../data/cps/asecpub22csv.zip"
FP_CPS_MARGINS = "../data/cps/cps_asec_2022_margins.csv"
FP_COMBINED = "../data/combined_yg_bl_who_derived_hist_tracking.csv"
FP_TABLE = "../tables/demo_summary"
FP_NOTE = "../tables/demo_summary_note.tex"

ASEC_COLS = ["A_AGE", "A_SEX", "PEHSPNON", "PRDTRACE", "A_HGA", "MARSUPWT"]

variable_order = ["gender", "race", "educ", "agegroup"]

variable_names = {
    "gender": "gender",
    "race": "race",
    "educ": "education",
    "agegroup": "age",
}

custom_order = [
    "Female",
    "Male",
    "White",
    "Hispanic",
    "Black",
    "Other",
    "Asian",
    "HS or Below",
    "Some college",
    "College",
    "Postgrad",
    "<25",
    "25-34",
    "35-49",
    "50-64",
    "65+",
]

demo_cat_labels = {
    "<25": "$<$ 25 years old",
    "25-34": "25--34 years old",
    "35-49": "35--49 years old",
    "50-64": "50--64 years old",
    "65+": "65+ years old",
    "HS or Below": "High school diploma or below",
    "Some college": "Some College education",
    "College": "College Graduate",
    "Postgrad": "Postgraduate",
}

# Committed Table 1 Panel B values (analytic sample, n = 1,134); the CPS
# columns must be appended without disturbing these.
expected_panel = {
    "Female": (595, 52.5),
    "Male": (539, 47.5),
    "White": (720, 63.5),
    "Hispanic": (168, 14.8),
    "Black": (144, 12.7),
    "Other": (56, 4.9),
    "Asian": (46, 4.1),
    "HS or Below": (411, 36.2),
    "Some college": (326, 28.7),
    "College": (255, 22.5),
    "Postgrad": (142, 12.5),
    "<25": (93, 8.2),
    "25-34": (200, 17.6),
    "35-49": (285, 25.1),
    "50-64": (288, 25.4),
    "65+": (268, 23.6),
}


def load_asec() -> pd.DataFrame:
    if not os.path.exists(FP_ASEC_ZIP):
        os.makedirs(os.path.dirname(FP_ASEC_ZIP), exist_ok=True)
        print(f"Downloading {ASEC_URL} ...")
        urllib.request.urlretrieve(ASEC_URL, FP_ASEC_ZIP)
    with zipfile.ZipFile(FP_ASEC_ZIP) as zf:
        with zf.open("pppub22.csv") as f:
            return pd.read_csv(f, usecols=ASEC_COLS)


def recode_asec(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["A_AGE"] >= 18].copy()

    # MARSUPWT in some vintages carries two implied decimals; the weighted
    # count of adults must land near the ~258M 2022 adult population.
    if df["MARSUPWT"].sum() > 1e9:
        df["MARSUPWT"] = df["MARSUPWT"] / 100
    assert 2.3e8 < df["MARSUPWT"].sum() < 2.8e8, df["MARSUPWT"].sum()

    df["gender_lab"] = df["A_SEX"].map({1: "Male", 2: "Female"})
    df["race_lab"] = (
        df["PRDTRACE"]
        .map({1: "White", 2: "Black", 4: "Asian"})
        .fillna("Other")
        .where(df["PEHSPNON"] != 1, "Hispanic")
    )
    assert df["A_HGA"].between(31, 46).all()
    df["educ_lab"] = pd.cut(
        df["A_HGA"],
        bins=[30, 39, 42, 43, 46],
        labels=["HS or Below", "Some college", "College", "Postgrad"],
    )
    # Table 1's age groups cut birthyr, so its brackets are birth cohorts, and
    # the CPS side has to be cut to the same cohorts rather than to the nominal
    # brackets the labels suggest.
    #
    # The sample cuts birthyr at [1929, 1958, 1973, 1988, 1998, 2003] against a
    # June-2022 field period, so "<25" is birthyr 1999-2003, i.e. ages 19-23 --
    # five single-year cohorts. Cutting CPS at A_AGE 18-24 gives seven. That
    # alone predicts a sample share of 11.354 x 5/7 = 8.11% against an observed
    # 8.2%, which is essentially the whole of the deviation the age chi-square
    # was picking up. Matching the cohorts removes the artefact.
    df["agegroup_lab"] = pd.cut(
        df["A_AGE"],
        bins=[17, 23, 33, 48, 63, 200],
        labels=["<25", "25-34", "35-49", "50-64", "65+"],
    )
    return df


def cps_margins(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for var in ["gender_lab", "race_lab", "educ_lab", "agegroup_lab"]:
        shares = 100 * df.groupby(var, observed=True)["MARSUPWT"].sum()
        shares = shares / df["MARSUPWT"].sum()
        assert abs(shares.sum() - 100) < 0.1, (var, shares.sum())
        out.append(
            shares.rename("cps_perc")
            .reset_index()
            .rename(columns={var: "cat"})
            .assign(variable=var.replace("_lab", ""))
        )
    return pd.concat(out)[["variable", "cat", "cps_perc"]]


def build_table(margins: pd.DataFrame) -> pd.DataFrame:
    df_ind = pd.read_csv(FP_COMBINED)
    assert len(df_ind) == 1134, len(df_ind)

    df_demo = (
        pd.concat(
            [
                df_ind["gender_lab"].value_counts(),
                df_ind["race_lab"].value_counts(),
                df_ind["educ_lab"].value_counts(),
                df_ind["agegroup_lab"].value_counts(),
            ]
        )
        .reset_index(name="n")
        .rename(columns={"index": "cat"})
        .assign(
            cat=lambda df_: pd.Categorical(
                df_["cat"], categories=custom_order, ordered=True
            )
        )
        .sort_values("cat")
        .reset_index(drop=True)
        .assign(perc=lambda df_: 100 * df_["n"] / len(df_ind))
        .merge(margins, on="cat", how="left", validate="1:1")
        # from the rounded shares, so the column is consistent with the
        # displayed percentages
        .assign(diff=lambda df_: df_["perc"].round(1) - df_["cps_perc"].round(1))
    )

    for _, row in df_demo.iterrows():
        assert (row["n"], round(row["perc"], 1)) == expected_panel[row["cat"]], row["cat"]
    return df_demo


def gof_tests(df_demo: pd.DataFrame) -> dict:
    tests = {}
    for var, grp in df_demo.groupby("variable"):
        f_obs = grp["n"].to_numpy()
        f_exp = (grp["cps_perc"] / 100 * f_obs.sum()).to_numpy()
        f_exp = f_exp * f_obs.sum() / f_exp.sum()
        chi2, p = stats.chisquare(f_obs, f_exp)
        tests[var] = {"chi2": chi2, "df": len(grp) - 1, "p": p}
    return tests


def fmt_p(p: float) -> str:
    if p < 0.001:
        return "p<.001"
    return f"p={p:.2f}".replace("=0.", "=.")


def write_note(df_demo: pd.DataFrame, tests: dict) -> None:
    dev = df_demo["diff"].abs()
    worst = df_demo.loc[dev.idxmax(), "cat"]
    tests_tex = "; ".join(
        f"{variable_names[v]} $\\chi^2({tests[v]['df']})={tests[v]['chi2']:.1f}$, "
        f"${fmt_p(tests[v]['p'])}$"
        for v in variable_order
    )
    note = (
        "$\\chi^2$ goodness-of-fit tests of the sample against the CPS "
        f"shares: {tests_tex}. Mean absolute deviation across the 16 "
        f"categories is {dev.mean():.1f} percentage points; the maximum is "
        f"{dev.max():.1f} ({demo_cat_labels.get(worst, worst)})."
    )
    with open(FP_NOTE, "w") as f:
        f.write(note + "\n")
    print(f"\n{note}")


def format_table(df_demo: pd.DataFrame) -> pd.DataFrame:
    return df_demo.assign(
        perc=lambda df_: df_["perc"].round(1).astype(str).apply(lambda x: f"({x}\\%)"),
        cps_perc=lambda df_: df_["cps_perc"]
        .round(1)
        .astype(str)
        .apply(lambda x: f"{x}\\%"),
        diff=lambda df_: df_["diff"].round(1).apply(lambda d: f"${d:+.1f}$"),
        cat=lambda df_: df_["cat"].map(lambda x: demo_cat_labels.get(x, x)),
    )[["cat", "n", "perc", "cps_perc", "diff"]]


if __name__ == "__main__":
    asec = recode_asec(load_asec())
    margins = cps_margins(asec)
    os.makedirs(os.path.dirname(FP_CPS_MARGINS), exist_ok=True)
    margins.round(3).to_csv(FP_CPS_MARGINS, index=False)
    print(f"Wrote {FP_CPS_MARGINS}")

    df_demo = build_table(margins)

    print("\nPanel vs. CPS ASEC 2022 (adults 18+, weighted):")
    print(
        df_demo[["cat", "n", "perc", "cps_perc", "diff"]].round(1).to_string(index=False)
    )
    tests = gof_tests(df_demo)
    write_note(df_demo, tests)
    print(f"Wrote {FP_NOTE}")

    pandas_to_tex(format_table(df_demo), FP_TABLE)
    print(f"Wrote {FP_TABLE}.tex")
