"""Figures for the residual-exposure analysis.

Plotting is kept out of the analysis scripts so every figure reads the same
result files the tables do, and a restyle never risks changing a number.

House style, matching the rest of the repo: grayscale, no grid, no top or right
spine, both PDF and PNG from one save_mpl_fig call, legends without frames. The
one saturated color is reserved for reference lines, as in coefplot.R.

Where a quantity has both kinds of uncertainty, they are drawn differently. Bars
and caps are sampling uncertainty. The lighter open marker on the levels figure
is the identification bound from path rules, which is not sampling uncertainty
at all and must not be read as an interval around the estimate.
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as blk  # noqa: E402
import config  # noqa: E402

D = config.BLOCKING_DATA_DIR
TIER = blk.HEADLINE_TIER


def _read(name):
    return pd.read_csv(os.path.join(D, name))


def fig_levels():
    """Exposure per visit, unblocked and under each defense."""
    levels = _read("residual_levels.csv")
    levels = levels[~levels["assumed"]].reset_index(drop=True)

    # Counts per visit and per-visit rates differ by two orders of magnitude, so
    # they get separate panels rather than a shared axis nothing reads well on.
    panels = [
        (levels.iloc[:2], "Trackers per visit", "Counts"),
        (levels.iloc[2:], "Share of visits", "Behaviors"),
    ]
    series = [("unblocked", "Unblocked", None)] + [
        (f"{t}_resid", blk.TIER_LABELS[t], f"{t}_lo") for t in config.TIER_ORDER
    ]

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
    for ax, (rows, xlabel, title) in zip(axes, panels):
        yy = np.arange(len(rows))
        for j, (col, label, lo_col) in enumerate(series):
            off = (j - (len(series) - 1) / 2) * 0.16
            ax.scatter(
                rows[col],
                yy + off,
                marker=blk.MARKERS[j],
                color=blk.SHADES[j],
                s=28,
                label=label,
                zorder=3,
            )
            if lo_col:
                # Tick to the left: where the residual would sit if every path
                # rule fired. An identification bound, not a confidence interval.
                ax.hlines(
                    yy + off,
                    rows[lo_col],
                    rows[col],
                    color=blk.SHADES[j],
                    lw=0.8,
                    zorder=2,
                )
        ax.set_yticks(yy)
        ax.set_yticklabels(rows["measure"], fontsize=9)
        ax.set_ylim(len(rows) - 0.5, -0.5)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel(xlabel)
        ax.set_xlim(left=0)
        blk.style_axis(ax)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=8)
    plt.tight_layout(rect=(0, 0.09, 1, 1))
    blk.save_mpl_fig(blk.figure_path("residual_levels"))
    plt.close()
    return "residual_levels"


def fig_age_gap():
    """The 65+ gap in absolute terms and as a ratio, before and after blocking."""
    gaps = _read("residual_gaps.csv")
    gaps = gaps[~gaps["assumed"]]
    measures = gaps["measure"].unique()
    y = np.arange(len(measures))

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.0))

    ax = axes[0]
    for j, spec in enumerate(["unblocked"] + [f"tier_{t}" for t in config.TIER_ORDER]):
        sub = gaps[gaps["spec"] == spec].set_index("measure").reindex(measures)
        ax.errorbar(
            sub["coef"],
            y + (j - 1.5) * 0.18,
            xerr=1.96 * sub["se"],
            fmt=blk.MARKERS[j],
            color=blk.SHADES[j],
            ms=4,
            lw=1,
            capsize=2,
            label="Unblocked" if spec == "unblocked" else blk.TIER_LABELS[spec[-1]],
        )
    ax.set_xscale("symlog", linthresh=0.01)
    ax.set_xlabel("65+ coefficient (trackers per visit)")
    blk.style_axis(ax, zero_line="v")
    ax.set_yticks(y)
    ax.set_yticklabels(measures)
    ax.invert_yaxis()
    ax.set_title("Absolute gap", fontsize=10)
    handles, labels = ax.get_legend_handles_labels()

    ax = axes[1]
    sub = gaps[gaps["spec"] == f"tier_{TIER}"].set_index("measure").reindex(measures)
    ax.errorbar(
        sub["gap_shift"],
        y,
        xerr=[sub["gap_shift"] - sub["shift_lo"], sub["shift_hi"] - sub["gap_shift"]],
        fmt="o",
        color=blk.BLACK,
        ms=4,
        lw=1,
        capsize=2,
    )
    blk.style_axis(ax, zero_line="v")
    ax.set_yticks(y)
    ax.set_yticklabels([])
    ax.invert_yaxis()
    ax.set_xlabel("Change in log-ratio gap (95% bootstrap)\nright of 0 = gap widened")
    ax.set_title(f"Relative gap, {blk.TIER_LABELS[TIER]}", fontsize=10)

    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=8)
    plt.tight_layout(rect=(0, 0.09, 1, 1))
    blk.save_mpl_fig(blk.figure_path("residual_age_gap"))
    plt.close()
    return "residual_age_gap"


def fig_decomposition():
    dec = _read("age_gap_decomposition.csv")
    dec = dec[dec["base"] == "young"].reset_index(drop=True)
    parts = [
        ("composition", "Category mix"),
        ("site_choice", "Site choice within category"),
        ("interaction", "Interaction"),
    ]
    y = np.arange(len(dec))

    fig, ax = plt.subplots(figsize=(8, 3.6))
    for j, (col, label) in enumerate(parts):
        share = 100 * dec[col] / dec["gap"]
        ax.barh(y + (j - 1) * 0.26, share, height=0.24, color=blk.SHADES[j], label=label)
    ax.set_yticks(y)
    ax.set_yticklabels(dec["measure"])
    ax.invert_yaxis()
    ax.set_xlabel("Share of the 65+ minus <25 gap (%)")
    blk.style_axis(ax, zero_line="v")
    fig.legend(loc="lower center", ncol=3, frameon=False, fontsize=8)
    plt.tight_layout(rect=(0, 0.09, 1, 1))
    blk.save_mpl_fig(blk.figure_path("age_gap_decomposition"))
    plt.close()
    return "age_gap_decomposition"


def fig_sensitive():
    cat = _read("sensitive_categories.csv")
    measures = [
        ("session_recording", "Session Recording"),
        ("key_logging", "Keylogging"),
        ("canvas_fingerprinting", "Canvas Fingerprinting"),
    ]
    x = np.arange(len(cat))
    width = 0.38

    # One panel per behavior. Overlaying three behaviors on shared bars made the
    # tallest one look like the blocked residual of another; separate panels
    # keep before and after unambiguously paired.
    fig, axes = plt.subplots(1, len(measures), figsize=(10, 3.6), sharey=True)
    for ax, (key, label) in zip(axes, measures):
        ax.bar(x - width / 2, cat[f"{key}_pct"], width, color=blk.MID, label="Unblocked")
        ax.bar(
            x + width / 2,
            cat[f"{key}_pct_resid"],
            width,
            color=blk.BLACK,
            label=f"Behind {blk.TIER_LABELS[TIER].split(' (')[0]}",
        )
        ax.set_xticks(x)
        ax.set_xticklabels(cat["category"], fontsize=7, rotation=30, ha="right")
        ax.set_title(label, fontsize=10)
        blk.style_axis(ax)
    axes[0].set_ylabel("% of the category's visitors\nexposed there", fontsize=9)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False, fontsize=8)
    plt.tight_layout(rect=(0, 0.08, 1, 1))
    blk.save_mpl_fig(blk.figure_path("sensitive_category_exposure"))
    plt.close()
    return "sensitive_category_exposure"


def fig_device():
    dev = _read("device_age_gradient.csv")
    y = np.arange(len(dev))
    specs = [
        ("pooled", "Pooled"),
        ("device_adj", "+ device control"),
        ("desktop", "Desktop only"),
        ("mobile", "Mobile only"),
    ]

    fig, ax = plt.subplots(figsize=(8, 3.6))
    for j, (key, label) in enumerate(specs):
        se = dev[f"{key}_se"] if f"{key}_se" in dev else None
        ax.errorbar(
            dev[f"{key}_coef"],
            y + (j - 1.5) * 0.18,
            xerr=None if se is None else 1.96 * se,
            fmt=blk.MARKERS[j],
            color=blk.SHADES[j],
            ms=4,
            lw=1,
            capsize=2,
            label=label,
        )
    ax.set_xscale("symlog", linthresh=0.01)
    ax.set_yticks(y)
    ax.set_yticklabels(dev["measure"])
    ax.invert_yaxis()
    ax.set_xlabel("65+ coefficient (trackers per visit)")
    blk.style_axis(ax, zero_line="v")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    plt.tight_layout()
    blk.save_mpl_fig(blk.figure_path("device_age_gradient"))
    plt.close()
    return "device_age_gradient"


def fig_projection():
    proj = _read("population_projection.csv")
    y = np.arange(len(proj))

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.barh(y - 0.19, proj["projected_m"], height=0.34, color=blk.MID, label="Unblocked")
    ax.errorbar(
        proj["projected_m"],
        y - 0.19,
        xerr=[
            proj["projected_m"] - proj["projected_m_lo"],
            proj["projected_m_hi"] - proj["projected_m"],
        ],
        fmt="none",
        ecolor="black",
        capsize=2,
        lw=1,
    )
    ax.barh(
        y + 0.19,
        proj["projected_m_resid"],
        height=0.34,
        color=blk.BLACK,
        label=f"Behind {blk.TIER_LABELS[TIER]}",
    )
    ax.errorbar(
        proj["projected_m_resid"],
        y + 0.19,
        xerr=[
            proj["projected_m_resid"] - proj["projected_m_resid_lo"],
            proj["projected_m_resid_hi"] - proj["projected_m_resid"],
        ],
        fmt="none",
        ecolor="0.6",
        capsize=2,
        lw=1,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(proj["measure"])
    ax.invert_yaxis()
    ax.set_xlabel("US adults encountering the behavior in a month (millions)")
    blk.style_axis(ax)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    plt.tight_layout()
    blk.save_mpl_fig(blk.figure_path("population_projection"))
    plt.close()
    return "population_projection"


def fig_placebo():
    """Where the real blocklist falls among random removals of the same size."""
    plac = _read("placebo.csv")
    n = len(plac)
    fig, axes = plt.subplots(1, n, figsize=(2.1 * n, 3.0), sharey=True)
    for ax, (_, r) in zip(np.atleast_1d(axes), plac.iterrows()):
        draws = np.load(os.path.join(D, f"placebo_draws_{r['measure_key']}.npy"))
        ax.hist(draws, bins=24, color=blk.LIGHT, edgecolor="0.6", linewidth=0.4)
        ax.axvline(r["observed_shift"], color=blk.ACCENT, lw=1.4)
        ax.set_title(f"{r['measure']}\np = {r['p_value']:.3f}", fontsize=8)
        ax.set_xlabel("shift", fontsize=8)
        ax.tick_params(labelsize=7)
        blk.style_axis(ax)
    np.atleast_1d(axes)[0].set_ylabel("Placebo draws", fontsize=8)
    fig.suptitle(
        "Change in the age gap: random removals (bars) vs the real blocklist (line)",
        fontsize=9,
    )
    plt.tight_layout(rect=(0, 0, 1, 0.94))
    blk.save_mpl_fig(blk.figure_path("blocking_placebo"))
    plt.close()
    return "blocking_placebo"


def main():
    os.makedirs(config.FIGURES_DIR, exist_ok=True)
    for builder in (
        fig_levels,
        fig_age_gap,
        fig_decomposition,
        fig_sensitive,
        fig_device,
        fig_projection,
        fig_placebo,
    ):
        stem = builder()
        print(f"  wrote figures/{stem}.pdf and .png")


if __name__ == "__main__":
    sys.exit(main())
