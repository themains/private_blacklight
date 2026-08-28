# Archive

Superseded material, kept rather than deleted so results can be traced back.
Nothing here is read by the pipeline. Retired 2026-08-27.

## `tables_2025/`, `figures_2025/`

The tables and figures produced by the Python pipeline, which the R pipeline in
`scripts/R/` replaced. During the port these were the acceptance target: every R
output was diffed against its counterpart here until it reproduced. That check
is finished, so they are no longer needed to verify anything.

Where the two disagree, the R output is the correct one. The differences are
documented and each has a cause: the bootstrap and placebo draws use our own
seed rather than the frozen numpy stream; the population projection reflects the
CPS age-bracket fix; two rows of `bl_top_contributors_domain` swap on a genuine
tie; and everything downstream of the visit panel moved when the double-counted
visit aggregate was corrected (see `scripts/missing_data.md`).

## Four analyses have since been reinstated

These four were rebuilt in R from source and now appear in the manuscript
appendix (`sm:decomposition`, `sm:blocking`, `sm:robustness`). The copies here
are the superseded Python outputs, kept only as a reference point. All four
moved slightly when the double-counted visit aggregate was corrected, and the
decomposition moved more because it now runs on the whole panel rather than the
device-file subsample -- site choice is 80% of the ad-tracker gap, not the 87%
recorded here.

- **`age_gap_decomposition`** — the split of the age gap into within- versus
  between-content-category components (87% within, for ad trackers). The
  abstract's claim that exposure reflects "where people browse, and not only how
  much" currently rests on this, and the manuscript shows no evidence for it.
- **`age_spline_tests`** — F-tests for any age effect and for nonlinearity. The
  manuscript shows the LOWESS curve but not the tests behind the sentence about
  the gradient running smoothly across cohorts.
- **`device_age_gradient`** — the age gap holding under device controls.
- **`robustness_age_coding`** — sensitivity to the age binning, which became
  load-bearing after the bins were re-cut on true age.

The remaining eight tables here are diagnostics or superseded variants and stay
retired: WhoTracksMe summaries (no
manuscript estimate depends on WhoTracksMe), `coverage_imputation_bounds`
(superseded by `coverage_bounds_wayback`), top-contributor variants, and the
per-measure spline figures.

## `pinned/`

`cum_exposure_by_hour.tex` and its figure, pinned from a run that had access to
the restricted `realityMine_web` visit file. Obsolete: that file is now
downloaded and the pipeline rebuilds both from source, reproducing these values
exactly.
