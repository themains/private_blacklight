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

import argparse
import os
import urllib.request
import zipfile

import pandas as pd
from scipy import stats

import constants
from utilities import pandas_to_tex

ASEC_URL = (
    "https://www2.census.gov/programs-surveys/cps/datasets/2022/march/" "asecpub22csv.zip"
)
# Resolved from this file, not the working directory. Run from the wrong place,
# the old relative paths silently created an empty scripts/data/ instead of
# finding the real one.
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

# Live output: the CPS margins the R pipeline rakes onto. Everything below it is
# superseded -- R generates the demo-summary tables now, and FP_COMBINED names a
# person-level file removed as superseded because it carried the double-counted
# visit aggregate. Run this with --refresh to rebuild the margins; the
# table-building path will not find its input.
FP_ASEC_ZIP = os.path.join(REPO_ROOT, "data", "cps", "asecpub22csv.zip")
FP_CPS_MARGINS = os.path.join(REPO_ROOT, "data", "cps", "cps_asec_2022_margins.csv")
FP_COMBINED = os.path.join(REPO_ROOT, "data",
                           "combined_yg_bl_who_derived_hist_tracking.csv")
FP_TABLE = os.path.join(REPO_ROOT, "tables", "demo_summary")
FP_NOTE = os.path.join(REPO_ROOT, "tables", "demo_summary_note.tex")
FP_TABLE_N = os.path.join(REPO_ROOT, "tables", "demo_summary_n.tex")

ASEC_COLS = ["A_AGE", "A_SEX", "PEHSPNON", "PRDTRACE", "A_HGA", "MARSUPWT"]

variable_order = ["gender", "race", "educ", "agegroup"]

variable_names = {
    "gender": "gender",
    "race": "race",
    "educ": "education",
    "agegroup": "age",
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
    # PRDTRACE 1 White, 2 Black, 4 Asian, everything else "Other"; PEHSPNON == 1
    # is Hispanic and takes precedence, matching Table 1's mutually exclusive
    # race categories.
    df["race_lab"] = (
        df["PRDTRACE"]
        .map({1: "White", 2: "Black", 4: "Asian"})
        .fillna("Other")
        .where(df["PEHSPNON"] != 1, "Hispanic")
    )
    assert df["A_HGA"].between(31, 46).all()
    # ASEC 2022 data dictionary, A_HGA (educational attainment): 31-38 less than
    # high school, 39 high school graduate, 40-42 some college / associate,
    # 43 bachelor's, 44-46 master's / professional / doctorate. pd.cut is
    # right-closed, so these edges reproduce those four groups exactly.
    df["educ_lab"] = pd.cut(
        df["A_HGA"],
        bins=[30, 39, 42, 43, 46],
        labels=["HS or Below", "Some college", "College", "Postgrad"],
    )
    # Table 1's age groups cut birthyr (constants.AGE_BINS) against a June-2022
    # field period, and those edges land on the nominal age brackets: "<25" is
    # birthyr 1998-2003, i.e. ages 18-24 (the youngest panelists, born 2003, turn
    # 19 during the field period), then 25-34, 35-49, 50-64 and 65+. So the CPS
    # side is cut at the nominal brackets with no cohort adjustment.
    df["agegroup_lab"] = pd.cut(
        df["A_AGE"],
        bins=[17, 24, 34, 49, 64, 200],
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

    panel_b = constants.demo_counts(df_ind)
    df_demo = panel_b.merge(margins, on="cat", how="left", validate="1:1").assign(
        # from the rounded shares, so the column is consistent with the
        # displayed percentages
        diff=lambda df_: df_["perc"].round(1) - df_["cps_perc"].round(1)
    )

    # The only thing this step may do to Panel B is append columns to it, so
    # compare against the frame built a moment ago rather than against
    # transcribed literals, which only test whether someone retyped them.
    # (the merge demotes `cat` from Categorical to string, so compare as string)
    cols = ["cat", "n", "perc"]
    pd.testing.assert_frame_equal(
        df_demo[cols].astype({"cat": "string"}),
        panel_b[cols].astype({"cat": "string"}),
    )
    assert df_demo["cps_perc"].notna().all(), df_demo.loc[
        df_demo["cps_perc"].isna(), "cat"
    ].tolist()
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
        f"{dev.max():.1f} ({constants.DEMO_CAT_LABELS.get(worst, worst)})."
    )
    with open(FP_NOTE, "w") as f:
        f.write(note + "\n")
    print(f"\n{note}")


def format_table(df_demo: pd.DataFrame) -> pd.DataFrame:
    return df_demo.assign(
        perc=lambda df_: df_["perc"].round(1).astype(str).apply(lambda x: f"{x}\\%"),
        cps_perc=lambda df_: df_["cps_perc"]
        .round(1)
        .astype(str)
        .apply(lambda x: f"{x}\\%"),
        diff=lambda df_: df_["diff"].round(1).apply(lambda d: f"${d:+.1f}$"),
        cat=lambda df_: df_["cat"].map(lambda x: constants.DEMO_CAT_LABELS.get(x, x)),
    )[["cat", "n", "perc", "cps_perc", "diff"]]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="re-derive the CPS margins from the 157MB ASEC file instead of "
        "reading the committed data/cps/cps_asec_2022_margins.csv",
    )
    args = ap.parse_args()

    # The margins are a committed 350-byte artefact. Deriving them needs the
    # ASEC public-use file, which is gitignored, so a normal replication run
    # reads the artefact and never touches census.gov.
    if args.refresh or not os.path.exists(FP_CPS_MARGINS):
        asec = recode_asec(load_asec())
        margins = cps_margins(asec)
        os.makedirs(os.path.dirname(FP_CPS_MARGINS), exist_ok=True)
        margins.round(3).to_csv(FP_CPS_MARGINS, index=False)
        # The unweighted person count is the manuscript's CPS denominator; it
        # was hand-typed into the table header. Persist it beside the margins so
        # it cannot drift.
        with open(FP_TABLE_N, "w") as f:
            f.write(f"{len(asec):,}".replace(",", "{,}"))
        print(f"Derived and wrote {FP_CPS_MARGINS} and {FP_TABLE_N}")
    else:
        margins = pd.read_csv(FP_CPS_MARGINS)
        print(f"Read {FP_CPS_MARGINS} (pass --refresh to re-derive from ASEC)")

    df_demo = build_table(margins)

    print("\nPanel vs. CPS ASEC 2022 (adults 18+, weighted):")
    print(
        df_demo[["cat", "n", "perc", "cps_perc", "diff"]].round(1).to_string(index=False)
    )
    tests = gof_tests(df_demo)
    write_note(df_demo, tests)
    print(f"Wrote {FP_NOTE}")

    # \addlinespace between gender / race / education / age, so the fragment
    # drops into the manuscript with the spacing the table had when its rows
    # were typed by hand.
    breaks = (
        df_demo.reset_index(drop=True)
        .groupby("variable", sort=False)
        .apply(lambda g: g.index[-1])
        .tolist()[:-1]
    )
    pandas_to_tex(format_table(df_demo), FP_TABLE, group_breaks=breaks)
    print(f"Wrote {FP_TABLE}.tex")

