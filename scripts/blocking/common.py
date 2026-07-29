"""Shared definitions for the residual-exposure analysis.

Everything here exists once so it cannot drift. In particular the regression
specification is *not* redefined: `fit`, `stars` and `cell` are re-exported from
`implications/02_demo_robustness.py`, so this module and the paper's own
robustness work run the identical Table 5 model rather than two copies of it.

The estimand, stated once and inherited by every module that imports this:

    Residual exposure is the tracking a panelist would have met had a given
    blocklist been enforced on their observed browsing.

It is an accounting counterfactual, not the causal effect of installing a
blocker. Three assumptions make it one, each a real way it could be wrong:

  1. No behavioral response. Browsing is held fixed, though blocking changes
     load times, breaks pages, and trips anti-adblock walls.
  2. No site adaptation. Publishers do not respond -- no first-party proxying,
     no CNAME cloaking.
  3. Deterministic rule application. The list fires as the hostname test says.

Two kinds of uncertainty appear downstream and must never be merged. The
`_lo`/`_hi` range from path rules is a *partial-identification bound* on what a
list would have blocked; bootstrap intervals are *sampling* uncertainty over
panelists. Reported as `point [ID bounds] (sampling CI)`.
"""

import importlib
import os
import sys

import numpy as np

# --------------------------------------------------------------------------- #
# Import plumbing
#
# scripts/ must be on the path for `constants`, `utilities` and the implications
# module. `utilities` imports `constants`, which resolves its paths relative to
# scripts/, so the import happens from there.
# --------------------------------------------------------------------------- #
_HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.abspath(os.path.join(_HERE, ".."))
IMPLICATIONS_DIR = os.path.join(SCRIPTS_DIR, "implications")

for _p in (SCRIPTS_DIR, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# constants resolves its own paths relative to scripts/, so import from there.
_cwd = os.getcwd()
os.chdir(SCRIPTS_DIR)
try:
    import constants
    from utilities import pandas_to_tex, save_mpl_fig  # noqa: F401
finally:
    os.chdir(_cwd)

import config  # noqa: E402


def _load_demo_robustness():
    """Import implications/02_demo_robustness with *its* config, not ours.

    Three directories in this repo each ship a module named `config`, and that
    module does a bare `import config` expecting the one beside it. Loading it
    while ours is bound would silently hand it the wrong paths, so the name is
    swapped out for the duration and restored afterwards.
    """
    saved_path, saved_config = list(sys.path), sys.modules.pop("config", None)
    sys.path.insert(0, IMPLICATIONS_DIR)
    try:
        return importlib.import_module("02_demo_robustness")
    finally:
        sys.path[:] = saved_path
        sys.modules.pop("config", None)
        if saved_config is not None:
            sys.modules["config"] = saved_config


_demo = _load_demo_robustness()

# The paper's specification, borrowed rather than re-implemented.
fit = _demo.fit
stars = _demo.stars
cell = _demo.cell

# The Table 5 right-hand side and its label map, for the rare case that needs to
# extend the specification rather than reuse it as-is.
FORMULA_RHS = _demo.config.FORMULA_RHS
COEF_LABELS = _demo.config.COEF_LABELS
TABLE5_BENCHMARKS = _demo.config.TABLE5_BENCHMARKS
GATE_TOLERANCE = _demo.config.GATE_TOLERANCE

# --------------------------------------------------------------------------- #
# Measures and tiers
# --------------------------------------------------------------------------- #
AGE_TERM = "C(agegroup_lab, Treatment('<25'))[T.65+]"
OLD, YOUNG = "65+", "<25"
HEADLINE_TIER = "C"

# Labels come from constants.var_labels so the residual tables say exactly what
# the paper's tables say.
MEASURE_LABELS = {m: constants.var_labels[f"bl_{m}"] for m in config.MEASURES}

# Facebook Pixel and Google Analytics cards carry no responsible-domain list, so
# their attribution is assumed, and the lists happen to block both largely
# through path rules a hostname cannot trigger. Reported, never headlined.
ASSUMED = {"fb_pixel", "google_analytics"}
HEADLINE_MEASURES = [m for m in config.MEASURES if m not in ASSUMED]

TIER_LABELS = {t: config.TIERS[t][0] for t in config.TIER_ORDER}

# Declared test family for the multiplicity check: every measure crossed with
# every tier. Stated so the Bonferroni denominator is not left to inference.
N_FAMILY = len(config.MEASURES) * len(config.TIER_ORDER)

# --------------------------------------------------------------------------- #
# Inference
# --------------------------------------------------------------------------- #
BOOTSTRAP_REPS = 1000
BOOTSTRAP_SEED = 20250110  # the repo's existing bootstrap seed
MIN_VALID_FRACTION = 0.5
PCTILES = (2.5, 97.5)


def log_ratio(data, ycol, group_col="agegroup_lab", old=OLD, young=YOUNG):
    """log(mean_old / mean_young).

    Preferred to the coefficient-over-mean ratio used earlier. That quantity
    divides one noisy estimate by another whose denominator is tiny for the
    behavioral measures, so it both blows up and, when selected because it
    cleared a significance threshold, overstates its own magnitude. A log-ratio
    is scale-free, symmetric in the two groups, and better behaved in the tail.
    """
    a = data.loc[data[group_col] == old, ycol].mean()
    b = data.loc[data[group_col] == young, ycol].mean()
    if not (a > 0 and b > 0):
        return np.nan
    return float(np.log(a / b))


def gap_shift(data, y_pre, y_post, **kw):
    """Change in the log-ratio gap after blocking. Positive = gap widened."""
    return log_ratio(data, y_post, **kw) - log_ratio(data, y_pre, **kw)


def bootstrap_ci(data, statistic, reps=BOOTSTRAP_REPS, seed=BOOTSTRAP_SEED):
    """Percentile interval from resampling panelists.

    Returns (lo, hi, valid_fraction). Panelists are the unit of independent
    variation, so they are the unit resampled. Draws that cannot be evaluated
    (an empty age group, a zero mean) are dropped and counted rather than
    silently treated as zero.
    """
    rng = np.random.default_rng(seed)
    n = len(data)
    draws = []
    for _ in range(reps):
        sample = data.iloc[rng.integers(0, n, size=n)]
        try:
            value = statistic(sample)
        except (KeyError, ValueError, ZeroDivisionError, IndexError):
            continue
        if value is not None and np.isfinite(value):
            draws.append(value)

    valid = len(draws) / reps
    if valid < MIN_VALID_FRACTION:
        return float("nan"), float("nan"), valid
    lo, hi = np.percentile(draws, PCTILES)
    return float(lo), float(hi), valid


def bonferroni_report(rows, n_family=None, alpha=0.05, label="residual age gap"):
    """Print unadjusted and Bonferroni verdicts side by side.

    Follows the convention in 07_demo_differences.R: the correction is a
    console-side check against a lowered threshold, shown next to the
    unadjusted verdict, and deliberately kept out of the published fragment so
    the tables stay comparable with the paper's. What differs here is the
    family -- not that script's 12 demographic coefficients within one outcome,
    but every measure crossed with every tier.

    `rows` is an iterable of (name, p_value).
    """
    n_family = n_family or N_FAMILY
    threshold = alpha / n_family
    print(f"\nMultiplicity check -- family = {n_family} tests ({label})")
    print(f"  Bonferroni threshold: {alpha}/{n_family} = {threshold:.5f}")
    print(f"  {'test':44s} {'p':>10s}  unadj  bonf")
    n_unadj = n_bonf = n_degenerate = 0
    for name, p in rows:
        if not np.isfinite(p):
            n_degenerate += 1
            print(f"  {name:44s} {'--':>10s}  (no residual variation)")
            continue
        u = "yes" if p < alpha else ""
        b = "yes" if p < threshold else ""
        n_unadj += bool(u)
        n_bonf += bool(b)
        print(f"  {name:44s} {p:10.6f}  {u:5s}  {b}")
    print(f"  surviving: {n_unadj}/{n_family} unadjusted, {n_bonf}/{n_family} Bonferroni")
    if n_degenerate:
        # The family is declared in advance, so the denominator stays at
        # n_family even where a tier removes a measure entirely and leaves
        # nothing to test. Counting those as passes would be the mistake.
        print(
            f"  ({n_degenerate} of the {n_family} had no residual variation to test;"
            " the denominator is the declared family, not the evaluable subset)"
        )
    return threshold


# --------------------------------------------------------------------------- #
# Figures
#
# The repo is grayscale: no rcParams, no style sheet, no seaborn in new code.
# A saturated accent is allowed only for a reference line.
# --------------------------------------------------------------------------- #
BLACK, DARK, MID, LIGHT = (
    constants.palette7[0],
    constants.palette7[1],
    constants.palette7[4],
    constants.palette7[6],
)
SHADES = ["0.0", "0.35", "0.6", "0.8"]
MARKERS = ["o", "s", "^", "D"]
ACCENT = "#800000"  # reference lines only, as in coefplot.R

FIGSIZE_1 = (8, 3.6)
FIGSIZE_2 = (9.5, 4.6)


def style_axis(ax, zero_line=None):
    """The house axis: no top/right spines, no grid."""
    ax.spines[["top", "right"]].set_visible(False)
    if zero_line is not None:
        if zero_line == "v":
            ax.axvline(0, color="0.8", lw=1, zorder=0)
        else:
            ax.axhline(0, color="0.8", lw=1, zorder=0)
    return ax


def figure_path(stem):
    return os.path.join(config.FIGURES_DIR, stem)


def table_path(stem):
    return os.path.join(config.TABLES_DIR, stem)


def load_user():
    """Person-level residual exposure, one row per panelist."""
    import pandas as pd

    return pd.read_csv(config.FP_USER_RESIDUAL)
