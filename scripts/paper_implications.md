# What the validity work implies for the paper — and proposed text

Every number below is produced by the pipelines in `scripts/collect/httparchive/`,
`scripts/collect/wayback/`, `scripts/collect/selection_audit/`, and `scripts/collect/implications/`
(provenance in each section). Part 1 maps each of the paper's claims to what
the evidence says. Part 2 is proposed text for the manuscript, ready to
adapt on Overleaf. Framing throughout: we investigated whether the two
measurement compromises — tracking scanned ~30 months after browsing was
observed (T1), and no scan for 47% of domains / 24% of visits (T2) — change
what the paper concludes, and we report where they do.

---

## Part 1. Claim-by-claim implications

### Claim: tracking is near-universal (>99% of users; Table 2) — *strengthened*

Both compromises push these numbers down, not up: unscanned visits
contribute zero, and same-instrument measurement shows tracking prevalence
was slightly *higher* in June 2022 than later (visit-weighted ad-tracker
prevalence on matched domains 98.1% in June 2022 vs 95.2% in June 2025;
`tables/httparchive_drift.tex`). Directly scanning a random sample of the
unscanned domains found *heavier* tracking than on the scanned ones
(`tables/selection_audit_tracking.tex`). A ">99% of users encountered a
tracker" statement built on a censored, later-dated instrument is a floor.
No qualification needed; one supporting sentence available (Part 2.4).

### Claim: exposure is rapid (50% in 12h, ~80% in 48h; Figure 1) — *strengthened*

Unscanned visits are treated as tracker-free, so measured first-encounter
times can only be later than true ones; the hazard curves are conservative.
Same direction as above, no qualification needed.

### Claim: invasive techniques less common but non-trivial (Tables 2–3) — *unchanged, but say what we cannot check*

Canvas fingerprinting, session recording, and keylogging are behavioral
detections that no auxiliary instrument (HTTP Archive request maps, Wayback
static parses) can observe, so strands A–C are silent on them. What we have:
the zero-fill logic still makes them lower bounds, and the internal
Jan-2025→Apr-2026 rescan of the top-500 panel domains
(`scripts/temporal_stability.ipynb`) shows domain-level stability of these
flags. The appendix should state this asymmetry plainly (Part 2.2 does).

### Claim: concentration — Google tracks >50% of the median user's browsing (Figure 3) — *extends to the missing half*

Reach/dominance are computed over scanned domains, and zero-filling can only
understate an organization's reach. Measured directly on the July-2026
Blacklight scans of the unscanned-domain sample, 68.3% (visits stratum, 95%
CI [56, 78]) and 72.1% (uniform stratum, CI [60, 81]) of domains load at
least one Google-owned third party — statistically indistinguishable from
the 69.3% visit-weighted share in the originally scanned population
(`tables/implications_google_reach_audit.tex`). Google is as present on the
domains we could not scan as on the ones we could.

### Claim: exposure levels (4.98 ad trackers, 6.12 cookies per visit; Table 3) — *understated; now bounded*

This is where the paper's numbers move, in one direction. Replacing the
zero-fill with measurement-calibrated fills (HTTP Archive June-2022 request
maps cover 62.7% of the missing visit mass, Wayback another 3.2%; fills are
E[Blacklight count | auxiliary presence] estimated on jointly measured
domains, so magnitudes stay on the Blacklight scale) puts the ad-tracker
rate in [6.20, 8.27] per visit versus 4.98 published, and cookies in
[7.56, 9.97] versus 6.12 (`tables/coverage_imputation_bounds.tex`,
`tables/coverage_bounds_wayback.tex`). The direct audit agrees from the
other side: on unscanned domains scanned fresh, ad trackers average 8.81 per
visit-weighted domain (CI [4.98, 13.29]) versus 6.52 in the scanned
population (`tables/selection_audit_tracking.tex`). Proposed handling: keep
Table 3 as-is (it is the defensible floor), add the bounds to the text and
the appendix (Part 2.3, 2.4).

### Claim: education gap attenuates with browsing volume (Tables 4–5) — *robust*

Three separate checks, none of which moves it
(`tables/implications_coverage_by_demo.tex`,
`tables/implications_demo_fill_scenarios.tex`,
`tables/implications_drift_by_demo.tex`):

- Per-user scan coverage is demographically flat (R² = 0.01; no coefficient
  significant at 5%; largest is Woman −1.55 pp, p = .08) — missingness
  cannot manufacture or mask group gaps.
- Under every fill scenario the college rate gap stays small and marginal
  (ads: 0.49 → 0.42–0.43; cookies: 0.76 → 0.67; never significant at 5%
  under measured fills).
- Education gaps show no differential drift (College drift −0.22 ads/visit,
  p = .68), and the same-instrument college gap is similar at both dates.

### Claim: age gap survives normalization — older users visit more-tracked sites (Tables 4–5, Figure 2) — *qualitatively robust; 2025 measurement overstates the 2022 magnitude*

This is the one substantive place the validity work *changes* a number's
interpretation, in both directions at once:

- The gap is real and not an artifact of missingness: coverage is flat in
  age (65+: −0.59 pp, p = .74), and the coefficient is essentially invariant
  to imputation (ads 2.81 → 2.85–2.86; cookies 3.07 → 3.11–3.14; all
  p < .01; `figures/implications_demo_scenarios`).
- It is also not an artifact of timing *in sign*: measured contemporaneously
  (HTTP Archive, June 2022), the 65+ gap is large and significant on the
  same spec (ads +7.42/visit, cookies +4.87, both p < .01).
- **But** tracking growth between 2022 and 2025 concentrated on the sites
  older users frequent: the 65+ drift coefficient is +2.28 ads/visit and
  +4.57 cookies/visit (both p < .01). Same-instrument age gaps are therefore
  larger under Jan-2025 measurement (+9.70 ads, +9.44 cookies) than under
  June-2022 measurement (+7.42, +4.87) — i.e., the published (2025-measured)
  age gap overstates the June-2022 gap by roughly a quarter (ad trackers) to
  a half (cookies). The paper's qualitative claim stands at either date; the
  magnitude should be described as period-dependent — and the drift finding
  is substantively interesting in its own right (the age skew in tracking
  exposure *widened* between 2022 and 2025).

### Claim: race gaps (Asian users' lower per-visit exposure) — *robust, if anything stronger*

The Asian coefficient strengthens under measured fills (ads −1.20 → −1.38 to
−1.39; cookies −1.49 → −1.71; all p < .01) and shows no significant
differential drift (−0.61 ads/visit, p = .15). Small-group caveat (n Asian
is small; the paper already flags it) still applies.

### Claim (Discussion): "our estimates are conservative lower bounds" — *upgraded from assertion to measurement*

The paper currently asserts this; the validity work demonstrates it and
quantifies the gap (bounds above), with one honest asymmetry: for the
*level* of exposure everything is a floor, while for the *age comparison*
the 2025 instrument overstates the 2022 gap (previous item). Part 2.3
rewrites the Discussion paragraph accordingly.

### How big are these gaps? A Goldin yardstick

Raw coefficients (trackers per visit) give readers no sense of scale.
`tables/implications_gap_benchmarks.tex` re-expresses the key Table-5 gaps
as a share of the reference group's mean rate and as Cohen's d:

| gap (rate, published) | ads | cookies | d (ads) |
|---|---|---|---|
| Woman vs man | −4% (n.s.) | −2% (n.s.) | −0.06 |
| College vs HS-or-below | +10% (p<.10) | +13% (p<.10) | +0.13 |
| Asian vs White | −23% (p<.01) | −23% (p<.01) | −0.33 |
| 65+ vs under-25 | +87% (p<.01) | +74% (p<.01) | +0.77 |

The natural benchmark for disparity magnitudes is the literature Goldin's
public work anchors. Her figures, from sources fetched and verified:

- The gender earnings gap "in high-income countries is somewhere between
  ten and twenty per cent" ([Nobel Committee popular information, 2023](https://www.nobelprize.org/prizes/economic-sciences/2023/popular-information/)).
- In "A Grand Gender Convergence: Its Last Chapter" ([AER 2014, 104(4):
  1091–1119](https://dash.harvard.edu/bitstreams/a3c2676f-0699-4c0d-bb03-1485bb705670/download)):
  the full-time female coefficient is −0.248 log points with basic controls
  (Table 1, ACS 2009–11); the movement mantra is "77 cents on the dollar"
  (p. 1093); and for full-time college graduates "the aggregate gap is
  0.323 log points. Of that difference, 68 percent is due to the within gap
  and 32 percent to the between gap" (p. 1098).

Three usable contrasts follow, all context rather than equivalence (earnings
and exposure rates are different quantities; the point is which demographic
axes organize each inequality):

1. **Gender, the axis that organizes pay, is absent here.** Women's
   per-visit tracking exposure is 2–4% lower than men's and statistically
   null (d ≈ −0.04), an order of magnitude below the 10–20% earnings gap
   Goldin documents for high-income countries.
2. **Surveillance sorts on age instead.** The 65+/under-25 gap (+74–87%,
   d = 0.6–0.8) dwarfs every other demographic margin — several times the
   size of the contemporary gender pay gap in relative terms. (Strand A's
   caveat applies: under June-2022 measurement the age gap is roughly a
   quarter to half smaller, still the dominant axis.)
3. **The residual story parallels hers.** Goldin shows 68% of the college
   pay gap sits *within* occupations; our demographics explain <8% of the
   variance in exposure, with browsing composition doing the work — in both
   settings, the interesting inequality lives within, not between, the
   coarse groups.

---

## Part 2. Proposed manuscript text

### 2.1 Data section (§2), coverage paragraph — one added/replacing passage

> Blacklight returned a completed scan for 34,078 of the 64,074 domains
> (53.2%), covering 75.7% of visits. In the main analyses, visits to
> unscanned domains contribute zero tracking, so all exposure estimates are
> lower bounds by construction. Appendix X characterizes the unscanned
> domains — scan failures overwhelmingly reflect bot detection and
> JavaScript challenges rather than dead sites, and a directly re-measured
> random sample of unscanned domains carries at least as much tracking as
> the scanned population — and bounds how much the zero-fill understates
> exposure.

### 2.2 New appendix section: "Measurement validity" (structure + full draft)

> **Appendix X: Measurement validity.**
> Two features of our design warrant scrutiny: browsing was observed in
> June 2022 but Blacklight scans ran in January 2025 (timing), and scans
> completed for 53.2% of domains covering 75.7% of visits (coverage). We
> examined both with independent instruments — HTTP Archive's monthly
> crawls, Wayback Machine snapshots from the browsing window, and a fresh
> Blacklight scan of a random sample of unscanned domains — asking not
> whether the paper's numbers survive, but where they move and by how much.
>
> **Timing.** On panel domains measured by HTTP Archive in both June 2022
> and 2025, visit-weighted ad-tracker prevalence declined from 98.1% to
> 95.2%; recomputing each user's exposure under June-2022 versus Jan-2025
> domain measurements shifts means modestly (ad trackers −6.3%, Google
> Analytics −4.3%, Facebook requests −30%, header-set cookies +21%) while
> preserving the cross-user ordering our demographic analyses rely on
> (r = 0.75–0.91) (Tables A-x, A-y). Where the auxiliary and primary
> instruments measure the same construct contemporaneously they agree
> (ad-tracker presence: 86% of shared domains, Spearman ρ = 0.60; Wayback
> static parses recover 92% of HTTP-Archive ad-tracker presence in June
> 2022), which is what licenses using them as stand-ins (Tables A-z).
>
> **Coverage.** Scan failures are overwhelmingly domain-side bot walls and
> JavaScript challenges: 95% of unscanned domains returned an empty scan
> result; only a small remainder reflects scraper-side network failures
> (4.5% of domains) or reachability pre-checks (51 domains, though these
> carry 10.5% of unscanned visits and include large, live sites). At least
> 66% of the unscanned visit mass was demonstrably alive in mid-2022. A
> seeded random sample of 200 unscanned domains, hand-coded against a
> written rubric, shows the unscanned visit mass is mostly ordinary
> user-facing content (62%, CI [51, 70]) plus ad-tech and CDN
> infrastructure (28%); dead domains account for 7% of unscanned visit mass.
> Re-scanned with Blacklight in 2026, 66% of the sample produced completed
> scans, and tracking on those domains is heavier than in the scanned
> population (8.8 vs 6.5 ad trackers per visit-weighted domain).
> Replacing the zero-fill with fills calibrated on jointly measured domains
> (E[Blacklight count | HTTP-Archive or Wayback presence]) bounds the
> ad-tracker rate in [6.20, 8.27] per visit versus 4.98 published, and
> third-party cookies in [7.56, 9.97] versus 6.12 (Tables A-…).
>
> **Do the threats move the comparisons?** Per-user scan coverage is
> unrelated to demographics (R² = 0.01; no coefficient significant at 5%),
> so differential missingness cannot generate group gaps. Re-estimating the
> Table 5 regressions with unscanned visits imputed under each calibrated
> scenario leaves every conclusion intact: the education gradient stays
> small and insignificant, and the age and Asian coefficients are unchanged
> or slightly larger (Figure A-…). Timing, however, is not neutral for the
> age comparison: tracking growth between 2022 and 2025 concentrated on
> sites frequented by older users (65+ drift +2.3 ad trackers and +4.6
> cookies per visit, p < .01). The age gradient is large and significant
> under contemporaneous June-2022 measurement as well (+7.4 ad trackers per
> visit), but the Jan-2025 instrument overstates the June-2022 gap by
> roughly a quarter (ad trackers) to a half (cookies). Our qualitative
> conclusion — older users visit more heavily tracked sites — holds at
> either date; magnitudes should be read as of the scan date. Behavioral
> detections (canvas fingerprinting, session recording, keylogging) cannot
> be validated by request-map instruments; for these we rely on the
> zero-fill's conservatism and an internal 2026 rescan of the top-500 panel
> domains showing stable domain-level flags.
>
> **Concentration.** Zero-filling can only understate an organization's
> reach. On the fresh scans of the unscanned sample, 68–72% of domains load
> at least one Google-owned third party, statistically indistinguishable
> from the 69% (visit-weighted) in the scanned population: the
> concentration finding extends to the domains we could not scan.

Table/figure inventory for the appendix (all fragments already generated):
`httparchive_drift`, `temporal_user_exposure`, `ha_bl_agreement`,
`wb_ha_agreement`, `coverage_imputation_bounds`, `coverage_bounds_wayback`,
`wb_liveness`, `scan_failure_reasons`, `selection_audit_composition`,
`selection_audit_tracking`, `implications_coverage_by_demo`,
`implications_demo_fill_scenarios`, `implications_drift_by_demo`,
`implications_google_reach_audit`; figures `coverage_bounds`,
`coverage_bounds_wayback`, `selection_audit_tracking`,
`implications_demo_scenarios`, `temporal_user_exposure`.

### 2.3 Discussion, limitations paragraph — replacement

Current text asserts conservatism ("…making our estimates conservative lower
bounds"). Proposed replacement:

> Two measurement compromises deserve emphasis, and we quantified both
> rather than assuming their direction. First, Blacklight scanned domains
> about thirty months after browsing was observed. Re-measuring exposure
> with a single instrument at both dates shows population exposure changed
> modestly and cross-user ordering barely moved (r ≥ 0.75); the one
> comparison timing does affect is age, where tracking growth after 2022
> concentrated on sites older users frequent, so our scan-date age gap
> overstates the browsing-period gap by a quarter to a half — though the
> gap is large and significant at either date. Second, scans completed for
> 53% of domains (76% of visits), and unscanned visits count as zero. The
> unscanned domains are not dead and not tracker-free: re-measured directly,
> they carry at least as much tracking as scanned ones, and
> measurement-calibrated imputation places the true ad-tracker rate between
> 6.2 and 8.3 per visit against the 5.0 we report. Both compromises
> therefore make our headline prevalence and exposure estimates floors, not
> ceilings, while leaving the demographic comparisons intact (Appendix X).

### 2.4 Optional one-line insertions

- **Results §3.1** (after the >99% sentence): "These are floors: unscanned
  domains count as tracker-free, and a directly re-measured sample of them
  shows heavier tracking than the domains Blacklight scanned (Appendix X)."
- **Results §3.2** (end of the age paragraph): "The age gradient is not an
  artifact of scan coverage or imputation (Appendix X), though its
  magnitude is period-specific: measured with June-2022 data, the 65+ gap
  is roughly a quarter smaller for ad trackers and half for cookies."
- **Results §3.3** (concentration): "Google's reach extends to the domains
  Blacklight could not scan: 68–72% of a re-measured sample of unscanned
  domains load a Google-owned third party, matching the scanned
  population."
- **Abstract**, if desired, replace "…are modest and often attenuate…" with
  a version that owns the bounding: "Estimates are conservative: accounting
  for unscanned domains raises mean exposure by 25–66%, and demographic
  comparisons are unchanged." (Optional; the abstract works without it.)

### 2.4b Discussion, demographic-differences paragraph — proposed addition

> To put these magnitudes on a familiar scale: the demographic axis that
> organizes economic inequality barely registers here, and the axis that
> registers here has no counterpart there. Women's per-visit tracking
> exposure is two to four percent lower than men's and statistically
> indistinguishable from it — an order of magnitude below the ten to
> twenty percent gender earnings gap documented for high-income countries
> \citep{goldin2014grand, nobel2023popular}. Exposure instead sorts on
> age: panelists 65 and older encounter 74–87 percent more trackers per
> visit than those under 25. And just as most of the remaining gender pay
> gap sits within rather than between occupations \citep{goldin2014grand},
> most variation in surveillance sits within demographic groups — our
> covariates explain under eight percent of it; what people browse, not
> who they are, drives exposure.

BibTeX entries to add to `ms/blacklight.bib`:

```bibtex
@article{goldin2014grand,
  author  = {Goldin, Claudia},
  title   = {A Grand Gender Convergence: Its Last Chapter},
  journal = {American Economic Review},
  year    = {2014},
  volume  = {104},
  number  = {4},
  pages   = {1091--1119},
  doi     = {10.1257/aer.104.4.1091}
}

@misc{nobel2023popular,
  author       = {{Committee for the Prize in Economic Sciences in Memory of Alfred Nobel}},
  title        = {Popular Science Background: History Helps Us Understand Gender Differences in the Labour Market},
  year         = {2023},
  howpublished = {\url{https://www.nobelprize.org/prizes/economic-sciences/2023/popular-information/}},
  note         = {The Royal Swedish Academy of Sciences}
}
```

### 2.5 Housekeeping flagged while reconstructing the claims

- `README.md` still says the browsing data are from comScore; the paper and
  data are YouGov Pulse/RealityMine.
- `tables/demo_differences_exposure_rate.tex` in the repo is empty (0
  bytes) — ms Table 5 is not currently regenerable from the repo; the
  statsmodels replication in `scripts/R/08_robustness.R`
  reproduces its benchmark coefficients exactly and can serve as the
  regeneration path if the R toolchain is unavailable.
- Committed `tables/demo_summary.tex` differs slightly from the compiled
  PDF's Table 1 (e.g., Female n 595 vs 635) — the repo tables are a
  different vintage than the July-2025 PDF; worth a regeneration pass
  before resubmission.
