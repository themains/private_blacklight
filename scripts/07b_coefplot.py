"""07b_coefplot.py
Coefficient plots for the demographic-difference regressions: Figures 4 and 5.

Port of coefplot.R, which was sourced from 07_demo_differences.R and was left
orphaned when that script became 07_demo_differences.py. The estimates are the
same objects that fill Tables 5 and 6 -- both scripts call fit() from
implications/02_demo_robustness.py, so the figure and the table cannot drift
apart the way two separate model fits can.

Three defects in the R version are fixed here, all of them in the labelling and
geometry rather than the estimates:

  - coefplot.R saved 16x10 inches and the manuscript includes the result at
    \\textwidth, a 0.41 scale, so its 13-14 pt fonts reached the page at about
    5.3 pt -- the smallest type in the paper by a wide margin. Saving near the
    printed size puts them at 8-9 pt.
  - Term labels were passed through from the LaTeX vocabulary, so the age
    brackets rendered on the page as "Age: 25--34" with two literal dashes. A
    plot device is not LaTeX; the figure now carries a real en dash.
  - The cumulative panel labelled top-organisation *visits* "Max share", which
    is the rate-panel quantity. The manuscript caption for Figure 4 says "the
    number of visits observed by the top tracking organization", so the figure
    contradicted its own caption. Ad trackers, cookies and top-organisation
    visits are also divided by 100 in the cumulative models and nothing on the
    figure said so; those panels are now marked "(00s)" as the table is.

The caption states that black markers are significant at p < .05. The R used
gray30, which is not black; significant markers are now actually black.

Input:  data/combined_yg_bl_who_derived_hist_tracking.csv
Output: figures/coefplot_demo_differences_rate.{pdf,png}        (Figure 5)
        figures/coefplot_demo_differences_cumulative.{pdf,png}  (Figure 4)
"""

import os
import sys
import textwrap

import matplotlib

matplotlib.use("Agg")

import importlib  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import constants  # noqa: E402

# The estimates are whatever fills Tables 5 and 6; taking the model list from
# 07_demo_differences rather than refitting is what keeps the two in step.
_demo_differences = importlib.import_module("07_demo_differences")
_load_demo = _demo_differences._load_demo

REPO = os.path.abspath(os.path.join(_HERE, ".."))
FP_COMBINED = os.path.join(REPO, "data", "combined_yg_bl_who_derived_hist_tracking.csv")
FIGURES = os.path.join(REPO, "figures")

RESCALE_100 = _demo_differences.RESCALE_100
MEASURES = _demo_differences.MEASURES

# Panel titles. The seven tracking measures come from the shared vocabulary in
# constants.py so the figure, the tables and the residual module cannot drift;
# the top-organisation panel is not a tracking measure and is named for what
# each model actually regresses.
PANEL_EXTRA_RATE = "Top organization share"
PANEL_EXTRA_CUM = "Top organization visits (00s)"

# Grays from the shared palette. Significant markers are black because the
# manuscript caption says they are.
C_SIGNIFICANT = constants.palette7[0]
C_NULL = constants.palette7[5]
C_INTERVAL = constants.palette7[6]
C_REFERENCE = "#800000"

NCOL = 4
# 16x10 in the R, so the manuscript's \textwidth include scaled it to 0.41 and
# its 13-14 pt type reached the page near 5.3 pt. Same 1.6 aspect, so the float
# occupies the same block of the page, but drawn near print size: the 0.72
# scale puts 11 pt titles at about 8 pt and 10 pt labels at about 7 pt.
FIGSIZE = (9.0, 5.63)
FS_TITLE = 11
FS_LABEL = 10
# Four panels across nine inches, so the longest measure names do not fit on
# one line and would run into the neighbouring panel. Wrapped rather than
# abbreviated, because the names are the shared vocabulary from constants.py.
TITLE_WRAP = 17
DPI = 300


def panel_titles(cumulative):
    """One title per model, in the order the models are fit."""
    titles = []
    for measure in MEASURES:
        label = constants.var_labels[f"bl_{measure}_rate"]
        if cumulative and f"bl_{measure}" in RESCALE_100:
            label += " (00s)"
        titles.append(label)
    return titles + [PANEL_EXTRA_CUM if cumulative else PANEL_EXTRA_RATE]


def term_labels(index):
    """Coefficient names for a plot device rather than for LaTeX."""
    return [t.replace("--", "–") for t in index]


def draw(estimates, titles, fp):
    """One figure: a panel per outcome, coefficients on a shared vertical axis."""
    nrow = -(-len(titles) // NCOL)
    fig, axes = plt.subplots(
        nrow, NCOL, figsize=FIGSIZE, sharey=True, constrained_layout=True
    )
    axes = axes.ravel()

    # ggplot's factor levels put the first coefficient at the top of the panel;
    # matplotlib counts upward, so invert the axis rather than the data.
    terms = list(estimates[0].index)
    ypos = range(len(terms))

    for ax, res, title in zip(axes, estimates, titles):
        lo = res["b"] - 1.96 * res["se"]
        hi = res["b"] + 1.96 * res["se"]
        ax.hlines(list(ypos), lo, hi, color=C_INTERVAL, linewidth=1.6, zorder=1)
        significant = res["p"] < 0.05
        ax.scatter(
            res["b"],
            list(ypos),
            s=16,
            zorder=2,
            color=[C_SIGNIFICANT if s else C_NULL for s in significant],
        )
        ax.axvline(0, linestyle="--", color=C_REFERENCE, alpha=0.6, linewidth=0.8)
        ax.set_title(
            textwrap.fill(title, TITLE_WRAP),
            fontsize=FS_TITLE,
            fontweight="bold",
        )
        ax.tick_params(labelsize=FS_LABEL)
        ax.grid(axis="x", color=constants.palette7[6], linewidth=0.4, alpha=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        # Only the leftmost panel is labelled, so tick marks elsewhere are
        # orphaned dashes against a shared axis.
        ax.tick_params(axis="y", length=0)

    for ax in axes[len(titles) :]:
        ax.set_visible(False)

    axes[0].set_yticks(list(ypos))
    axes[0].set_yticklabels(term_labels(terms), fontsize=FS_LABEL)
    axes[0].invert_yaxis()
    fig.supxlabel("Estimate and 95% conf. int.", fontsize=FS_TITLE)

    for ext in ("pdf", "png"):
        out = f"{fp}.{ext}"
        fig.savefig(out, dpi=DPI)
        print(f"  Saved: figures/{os.path.basename(out)}")
    plt.close(fig)


def build(data, yvars, cumulative, stem):
    label = "cumulative exposure" if cumulative else "exposure rate"
    print(f"\n--- Coefficient plot: {label} ---")
    estimates = [_load_demo().fit(y, data) for y in yvars]
    n_significant = sum(int((r["p"] < 0.05).sum()) for r in estimates)
    print(f"  {len(estimates)} outcomes, {n_significant} coefficients at p < .05")
    draw(estimates, panel_titles(cumulative), os.path.join(FIGURES, stem))
    return estimates


def main():
    print("=== Coefficient plots: demographic differences ===")
    data = pd.read_csv(FP_COMBINED)
    if len(data) != 1134:
        raise ValueError(f"expected the 1,134-panelist analytic sample, got {len(data)}")

    # Same rescaling as 07_demo_differences, so the figure and Table 6 are on
    # one scale. Applied here rather than imported so this script runs alone.
    data = data.copy()
    for col in RESCALE_100:
        data[col] = data[col] / 100

    build(
        data,
        [f"bl_{m}_rate" for m in MEASURES] + ["top_org_share"],
        False,
        "coefplot_demo_differences_rate",
    )
    build(
        data,
        [f"bl_{m}" for m in MEASURES] + ["top_org_visits"],
        True,
        "coefplot_demo_differences_cumulative",
    )
    print("\n=== Coefficient Plots Complete ===")


if __name__ == "__main__":
    sys.exit(main())
