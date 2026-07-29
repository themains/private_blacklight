# Implications: do the validity threats change the paper's conclusions?

The validity strands (see `../validity_strands.md`) established how much the
two measurement threats — scan timing (T1) and scan coverage (T2) — move
*population-level* exposure. This module asks whether they move the paper's
*comparative* conclusions, above all the demographic gaps in ms Tables 4–5,
and whether the concentration claim (Figure 3) extends to the unscanned
mass. The write-up that turns these results into proposed paper text is
[`../paper_implications.md`](../paper_implications.md).

## Design

Regressions share the Table 5/6 specification with `scripts/07_demo_differences.py` (OLS on
gender/race/education/age-group dummies, references Male / White /
HS-or-Below / <25, Huber–White HC1) in statsmodels, and a **replication
gate** must reproduce ms Table 5's benchmark coefficients (65+: +2.81 ad
trackers/visit, +3.07 cookies/visit; Asian: −1.20, −1.49) before any new
quantity is interpreted.

1. **Differential missingness** — per-user scan coverage regressed on
   demographics. If coverage is demographically flat, zero-filling cannot
   manufacture or mask group gaps.
2. **Fill-scenario robustness** — per-user rates rebuilt under strand B's
   calibrated fill scenarios (`zero`/`mean`/`ha_mean`/`hawb_mean`,
   constructions identical to `httparchive/07` and `wayback/06`) and the
   Table-5 spec re-estimated under each.
3. **Drift patterning** — the same spec on same-instrument (HTTP Archive)
   per-user rates measured June 2022 and Jan 2025, plus their difference:
   how much of each 2025-measured gap already existed in 2022?
4. **Concentration reach** — share of domains loading any Google-owned third
   party: original scanned population (visit-weighted) vs the July-2026
   scans of the unscanned audit sample.

## Run order

```bash
python 01_build_user_scenario_rates.py   # per-user coverage, scenario + drift rates
python 02_demo_robustness.py             # gate, then the three regression blocks
python 03_google_reach_audit.py          # Google reach on scanned vs unscanned
python 04_gap_benchmarks.py              # gaps as % of reference mean + Cohen's d
```

## Outputs

| artifact | content |
|---|---|
| `data/implications/user_scenario_rates.csv` | per-user coverage, scenario rates, HA-2022/2025 rates |
| `tables/implications_coverage_by_demo.tex` | scan coverage (pp) by demographics |
| `tables/implications_demo_fill_scenarios.tex` | Table-5 coefficients under each fill scenario |
| `tables/implications_drift_by_demo.tex` | same-instrument gaps at each date + drift |
| `tables/implications_google_reach_audit.tex` | Google third-party reach, scanned vs unscanned |
| `tables/implications_gap_benchmarks.tex` | key gaps as % of reference-group mean and Cohen's d |
| `figures/implications_demo_scenarios.{pdf,png}` | coefficient stability across scenarios |

Validation baked in: step 01 prints coverage (must equal per_user_coverage's
76.4% pooled / 0.742 mean) and zero-scenario correlations with published
rates (must be ~1.000); step 02 hard-stops if the replication gate fails.
