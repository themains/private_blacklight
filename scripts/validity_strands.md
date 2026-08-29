# Validity strands: bounding the core estimand

**Core estimand.** A panelist's true tracking exposure during their June-2022
browsing — per measure, the visit-weighted rate (trackers per visit) and
cumulative count — and its distribution across panelists.

**How it is estimated in the paper.** June-2022 visits (`data/yg/yg_ind_domain.csv`)
× per-domain tracking from Blacklight scans run ~Jan 2025
(`data/blacklight_domain.csv`); unscanned domains contribute zero.

Two measurement threats, each attacked by a separate strand; two supporting
strands establish what the checks can and cannot claim. Each strand lives in
its own clearly named script/notebook and emits its own table/figure fragments.

| Strand | Threat / question | Design | Artifacts |
|---|---|---|---|
| **A. Temporal** | T1: tracking measured ~Jan 2025, browsing June 2022 | Same instrument (HTTP Archive) at both dates; matched domains. Domain level: prevalence change. User level: exposure recomputed under each date's measurements. | `httparchive/05_temporal_domain_drift.ipynb` → `tables/httparchive_drift.tex`, `figures/ha_drift`; `httparchive/06_temporal_user_exposure.ipynb` → `tables/temporal_user_exposure.tex`, `figures/temporal_user_exposure` |
| **B. Coverage** | T2: 47% of domains (23.6% of visits) unscanned, imputed zero | Interval per estimate: assumption-only (zero/mean/p90), then HA-2022 calibrated fill (measures ~63% of missing visit mass), then Wayback fill for part of the rest. Fills always calibrated to the Blacklight scale via jointly measured domains. | `httparchive/07_coverage_bounds.ipynb` → `tables/coverage_imputation_bounds.tex`, `figures/coverage_bounds`; `wayback/06_coverage_bounds_wayback.ipynb` → `tables/coverage_bounds_wayback.tex`, `figures/coverage_bounds_wayback` |
| **C. Instrument** | Are the auxiliary instruments valid stand-ins where strands A and B use them? | Contemporaneous cross-instrument agreement: HA vs Blacklight (Jan 2025, mobile both sides); Wayback vs HA (June 2022, same crawl month). Construct-honest labels. | `httparchive/08_instrument_agreement_ha_bl.ipynb` → `tables/ha_bl_agreement.tex`; `wayback/04_wb_ha_agreement.ipynb` → `tables/wb_ha_agreement.tex` |
| **D. Missingness mechanism** | Why did scans fail — dead domains or blocking domains? (Interprets strand B; dead-by-2025 also compounds T1.) | Wayback CDX liveness in June 2022 for Blacklight-unscanned domains. **Deepened by a direct audit**: the scraper's error log parsed into per-domain failure causes; a seeded 2×100 sample of unscanned domains (∝ visits + uniform) hand-coded against `selection_audit/CODING_RUBRIC.md`, probed, and freshly Blacklight-scanned (July 2026) — direct tracking measurements checked against strand B's calibrated fills. | `wayback/05_liveness_2022.ipynb` → `tables/wb_liveness.tex`; `selection_audit/01–04_*.py`, `selection_audit/05_selection_audit.ipynb` → `tables/scan_failure_reasons.tex`, `tables/selection_audit_composition.tex`, `tables/selection_audit_tracking.tex`, `figures/selection_audit_tracking` |

**Implications for the paper's conclusions** (`scripts/R/10_validity.R`,
write-up in `scripts/paper_implications.md`): the strands above bound the
*levels*; a final module tests whether the threats move the paper's
*comparisons* — per-user scan coverage regressed on demographics
(differential missingness), ms Table 5 re-estimated under strand B's fill
scenarios, same-instrument demographic gaps at June-2022 vs Jan-2025
measurement (drift patterning), and Google third-party reach on the audited
unscanned domains vs the scanned population. →
`tables/implications_coverage_by_demo.tex`,
`tables/implications_demo_fill_scenarios.tex`,
`tables/implications_drift_by_demo.tex`,
`tables/implications_google_reach_audit.tex`,
`figures/implications_demo_scenarios`.

**Sample representativeness.** Distinct from the measurement strands: does the
analytic sample (n = 1,134) resemble the US adult population?
`scripts/collect/08_cps_benchmark.py` computes weighted CPS ASEC 2022 margins (adults
18+, `MARSUPWT`) under the same category definitions as Table 1 and appends a
CPS column to `tables/demo_summary.tex`; margins saved to
`data/cps/cps_asec_2022_margins.csv`. Table 1 gets a signed difference column
(computed from the displayed rounded shares, so the column is internally
consistent) and `tables/demo_summary_note.tex` carries per-variable χ²
goodness-of-fit tests plus magnitude metrics — the two conventions in the
benchmarking literature (magnitude per Yeager & Krosnick 2011 POQ / Pew 2023;
per-variable χ² per applied-paper sample-vs-census tables). Result: gender
χ²(1)=0.7, p=.40; education χ²(3)=4.3, p=.24; age χ²(4)=11.7, p=.02; race
χ²(4)=40.5, p<.001. Mean absolute deviation 1.5 pp; max 3.2 pp
(18–24-year-olds, 8.2% vs 11.4%); all other margins within 2.6 pp. The race
rejection is driven largely by "Other" (+2.4 pp on a 2.5% CPS base), partly a
construct mismatch: YouGov's "Other" bundles Middle Eastern / Native American /
multiracial differently than the CPS `PRDTRACE` recode. Caveat: Table 1's age
groups cut `birthyr`, so its brackets are birth cohorts, while the CPS side
uses nominal age brackets.

Related, pre-existing checks (internal to Blacklight): `scripts/temporal_stability.ipynb`
(Jan-2025 → Apr-2026 rescan of top-500 domains), `scripts/scan_success.ipynb`
(scan failure vs domain reach), `scripts/per_user_coverage.ipynb` (per-user
visit-weighted coverage), `scripts/desktop_only_sensitivity.ipynb`.

**Interpretation discipline.** Every comparison states its construct
differences in the row labels (e.g., header-set vs all third-party cookies;
GA/GTM presence vs GA remarketing); signed deltas are reported so the
direction of any bias is explicit; behavioral measures (canvas fingerprinting,
session recording, key logging) are outside what request maps or static
snapshots can observe and rely on the internal rescan only.
